from concurrent.futures import Future
import unittest

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

    def _set_current_session(self, session):
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

        self.assertTrue(commit_callback_called)
