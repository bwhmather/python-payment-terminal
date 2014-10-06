import concurrent.futures
from threading import Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import PaymentSession
from nm_payment.exceptions import (
    SessionCompletedError, SessionCancelledError, CancelFailedError,
)


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

    def _start_reversal(self):
        try:
            self._state = REVERSING
            self._connection.request_reversal().result()
        except Exception as e:
            # XXX This is really really bad
            raise CancelFailedError() from e

    def _on_local_mode_running(self, result, **kwargs):
        if result == 'success':
            if (self._commit_callback and
                    not self._commit_callback(result)):
                try:
                    self._start_reversal()
                except Exception as e:
                    self._state = BROKEN
                    self._future.set_exception(e)
                    raise
            else:
                self._future.set_result(None)
        else:
            # TODO interpret errors from ITU
            self._state = FINISHED
            self._future.set_exception(Exception())

    def _on_local_mode_cancelling(self, result, **kwargs):
        if result == 'success':
            self._start_reversal()
        else:
            self._state = FINISHED
            self._future.set_exception(SessionCancelledError())

    def _on_local_mode_reversing(self, result, **kwargs):
        if result == 'success':
            self._state = FINISHED
            self._future.set_exception(SessionCancelledError())
        else:
            # XXX
            self._state = BROKEN

    def on_req_local_mode(self, *args, **kwargs):
        """
        .. note:: Internal use only
        """
        with self._lock:
            if self._state == RUNNING:
                return self._on_local_mode_running(*args, **kwargs)
            elif self._state == CANCELLING:
                return self._on_local_mode_cancelling(*args, **kwargs)
            elif self._state == REVERSING:
                return self._on_local_mode_reversing(*args, **kwargs)
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
            if self._state == RUNNING:
                self._state == CANCELLING
                # non-blocking, don't wait for result
                self._connection.request_cancel()
        try:
            self.result()
        except SessionCancelledError:
            # this is what we want
            return
        else:
            raise CancelFailedError()


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
