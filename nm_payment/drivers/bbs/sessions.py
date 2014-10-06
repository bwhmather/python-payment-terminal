import concurrent.futures
from threading import Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import PaymentSession
from nm_payment.exceptions import SessionCompletedError, SessionCancelledError

from .connection import _BBSMsgRouterConnection


class _BBSSession(object):
    def __init__(self, connection):
        super(_BBSSession, self).__init__()
        self._connection = connection
        self._connection.set_current_session(self)

    def on_req_display_text(
            self, data, *,
            expects_input=False, prompt_customer=False):
        # TODO
        pass

    def on_req_reset_timer(self, data):
        # TODO
        pass

    def on_req_local_mode(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def on_req_keyboard_input(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def on_req_send_data(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def unbind(self):
        pass


RUNNING = 'RUNNING'
CANCELLING = 'CANCELLING'
REVERSING = 'REVERSING'
FINISHED = 'FINISHED'


class _BBSPaymentSession(_BBSSession, PaymentSession):
    def __init__(self, connection, amount, before_commit):
        super(_BBSPaymentSession, self).__init__(connection)
        self._future = concurrent.futures.Future()
        self._lock = Lock()

        self._state = RUNNING

        self._commit_callback = before_commit

        self._connection.request_transfer_amount(amount).result()

    def _rollback(self):
        try:
            self._connection.request_reversal().result()
        except Exception as e:
            # XXX This is really really bad
            raise CancelFailedError() from e

    def _payment_local_mode(self, result, **kwargs):
        if result == 'success':
            if (self._commit_callback and
                    not self._commit_callback(result)):
                try:
                    self._rollback()
                except Exception as e:
                    self._state = FINSHED
                    self._future.set_exception(e)
                    raise
                else:
                    self._state = FINISHED
                    self._future.set_exception(SessionCancelledError())
            else:
                self._future.set_result(None)
        else:
            # TODO interpret errors from ITU
            self._future.set_exception(Exception())

    def _cancelling_local_mode(self, result, **kwargs):
        raise NotImplementedError()

    def _reversal_local_mode(self, result, **kwargs):
        raise NotImplementedError()

    def on_req_local_mode(self, *args, **kwargs):
        """
        .. note:: Internal use only
        """
        with self._lock:
            if self._state == RUNNING:
                return _payment_local_mode(*args, **kwargs)
            elif self._state == CANCELLING:
                return _cancelling_local_mode(*args, **kwargs)
            elif self._state == REVERSING:
                _reversal_local_mode(*args, **kwargs)
            else:
                raise Exception("invalid state")

    def on_display_text(self, text):
        pass

    def on_print_text(self, commands):
        pass

    def on_reset_timer(self, timeout):
        pass

    def cancel(self):
        """
        :raises SessionCompletedError:
            If session has already finished
        """
        with self._lock:
            if self._future.cancelled():
                return

            if not self._future.cancel():
                raise SessionCompletedError()

            self._connection.request_cancel().result()

    def result(self, timeout=None):
        try:
            return self._future.result()
        except concurrent.futures.CancelledError as e:
            raise SessionCancelledError() from e

    def add_done_callback(self, fn):
        return self._future.add_done_callback(fn)

    def unbind(self):
        try:
            self.cancel()
        except SessionCompletedError:
            pass
