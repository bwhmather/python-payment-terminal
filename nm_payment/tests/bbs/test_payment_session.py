from concurrent.futures import Future
import unittest

from nm_payment.drivers.bbs import _BBSPaymentSession


class TestBBSPaymentSession(unittest.TestCase):
    def test_normal(self):
        class TerminalMock(object):
            _state = 'bank'

            @classmethod
            def _set_current_session(self, session):
                pass

            @classmethod
            def request_transfer_amount(cls, amount):
                self.assertEqual(cls._state, 'bank')
                cls._state = 'local'
                f = Future()
                f.set_result(None)
                return f

        def commit_callback(result):
            nonlocal commit_callback_called
            commit_callback_called = True
            return True
        commit_callback_called = False

        s = _BBSPaymentSession(TerminalMock, 10, commit_callback)

        s.on_req_local_mode('success')

        self.assertTrue(commit_callback_called)
