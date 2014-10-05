from time import sleep
from threading import Thread
from concurrent.futures import Future
import unittest

from nm_payment.exceptions import SessionCancelledError
from nm_payment.drivers.bbs import _BBSPaymentSession


def fulfilled_future(result=None):
    """ Shortcut to create a future with its result already set
    """
    f = Future()
    f.set_result(result)
    return f


class TerminalMockBase(object):
    def __init__(self, test):
        self.test = test
        self.state = 'bank'

    def set_current_session(self, session):
        pass

    def state_change(self, initial, final):
        self.test.assertEqual(self.state, initial)
        self.state = final


class TestBBSPaymentSession(unittest.TestCase):
    def test_normal(self):
        class TerminalMock(TerminalMockBase):
            def request_transfer_amount(self, amount):
                self.state_change('bank', 'local')
                return fulfilled_future()

        terminal = TerminalMock(self)

        def commit_callback(result):
            nonlocal commit_callback_called
            commit_callback_called = True
            return True
        commit_callback_called = False

        s = _BBSPaymentSession(terminal, 10, commit_callback)

        self.assertEqual(terminal.state, 'local')
        s.on_req_local_mode('success')

        # should not raise anything
        s.result()

        self.assertTrue(commit_callback_called)

    def test_cancel(self):
        class TerminalMock(TerminalMockBase):
            def request_transfer_amount(self, amount):
                self.state_change('bank', 'local')
                return fulfilled_future()

            def request_cancel(self):
                self.state_change('local', 'cancelling')
                return fulfilled_future()

        terminal = TerminalMock(self)

        def commit_callback(result):
            # cancel should succeed to this should never happen
            self.fail('commit callback called')

        s = _BBSPaymentSession(terminal, 10, commit_callback)
        self.assertEqual(terminal.state, 'local')

        # cancel blocks until payment is successfully cancelled so needs to run
        # in a separate thread
        t = Thread(target=s.cancel, daemon=True)
        t.start()

        # yield to cancel thread, cancel thread should have called
        # `request_cancel` but should not return until local mode message has
        # been received
        sleep(0)  # XXX might not actually yield
        self.assertEqual(terminal.state, 'cancelling')
        self.assertTrue(t.is_alive())

        s.on_req_local_mode('failure')

        t.join()

        self.assertRaises(SessionCancelledError, s.result)

    def test_late_cancel(self):
        class TerminalMock(TerminalMockBase):
            def request_transfer_amount(self, amount):
                self.state_change('bank', 'local')
                return fulfilled_future()

            def request_cancel(self):
                self.state_change('local', 'cancelling')
                return fulfilled_future()

            def request_reversal(self):
                self.state_change('success', 'reversing')
                return fulfilled_future()

        terminal = TerminalMock(self)

        def commit_callback(result):
            # cancel should succeed to this should never happen
            self.fail('commit callback called')

        s = _BBSPaymentSession(terminal, 10, before_commit=commit_callback)
        self.assertEqual(terminal.state, 'local')

        # cancel blocks until payment is successfully cancelled so needs to run
        # in a separate thread
        t = Thread(target=s.cancel, daemon=True)
        t.start()

        # yield to cancel thread, cancel thread should have called
        # `request_cancel` but should not return until local mode message has
        sleep(0)  # XXX might not actually yield
        self.assertTrue(t.is_alive())

        # too slow, transaction goes through anyway
        terminal.state_change('cancelling', 'success')
        s.on_req_local_mode('success')

        # session should try to reverse the transaction
        self.assertEqual(terminal.state, 'reversing')

        # cancel thread should still be blocked
        sleep(0)  # XXX might not actually yield
        self.assertTrue(t.is_alive())

        # local mode message to indicate reversal succeeded
        s.on_req_local_mode('success')

        t.join()

        self.assertRaises(SessionCancelledError, s.result)

    def test_too_late_cancel(self):
        # TODO cancel called after session completed
        pass

    def test_dont_commit(self):
        class TerminalMock(TerminalMockBase):
            def request_transfer_amount(self, amount):
                self.state_change('bank', 'local')
                return fulfilled_future()

            def request_reversal(self):
                self.state_change('success', 'reversing')
                return fulfilled_future()

        terminal = TerminalMock(self)

        def commit_callback(result):
            nonlocal commit_callback_called
            commit_callback_called = True
            return False
        commit_callback_called = False

        s = _BBSPaymentSession(terminal, 10, before_commit=commit_callback)
        self.assertEqual(terminal.state, 'local')

        terminal.state_change('local', 'success')
        s.on_req_local_mode('success')

        self.assertTrue(commit_callback_called)

        self.assertEqual(terminal.state, 'reversing')
        s.on_req_local_mode('success')

        self.assertRaises(SessionCancelledError, s.result)
