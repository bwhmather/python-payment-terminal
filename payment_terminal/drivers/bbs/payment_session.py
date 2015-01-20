import concurrent.futures
from threading import Lock

import logging
log = logging.getLogger('payment_terminal')

from payment_terminal.base import PaymentSession, Payment
from payment_terminal.exceptions import (
    SessionCompletedError, SessionCancelledError, CancelFailedError,
)

from .session import BBSSession


RUNNING = 'RUNNING'
CANCELLING = 'CANCELLING'
REVERSING = 'REVERSING'
FINISHED = 'FINISHED'
BROKEN = 'BROKEN'


class BBSPaymentSession(BBSSession, PaymentSession):
    def __init__(
            self, connection, amount, *, before_commit=None,
            on_print=None, on_display=None):
        super(BBSPaymentSession, self).__init__(connection)
        self._future = concurrent.futures.Future()
        self._lock = Lock()

        self._state = RUNNING

        self.amount = amount

        self._commit_callback = before_commit
        self._print_callback = on_print
        self._display_callback = on_display

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
            commit = True
            self._state = CANCELLING

            # TODO populate properly
            result_object = Payment(self.amount)
            if self._commit_callback is not None:
                # TODO can't decide on commit callback api
                try:
                    commit = self._commit_callback(result_object)
                except Exception:
                    log.exception("error in commit callback")
                    commit = False

            if commit:
                self._state = FINISHED
                self._future.set_result(result_object)
            else:
                self._start_reversal()
        else:
            # TODO interpret errors from ITU
            self._state = FINISHED
            self._future.set_exception(SessionCancelledError("itu error"))

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
        if self._display_callback is not None:
            self._display_callback(text)

    def on_print_text(self, commands):
        if self._print_callback is not None:
            self._print_callback(commands)

    def on_reset_timer(self, timeout):
        pass

    def cancel(self):
        """
        :raises SessionCompletedError:
            If session has already finished
        """
        with self._lock:
            if self._state == RUNNING:
                self._state = CANCELLING
                # non-blocking, don't wait for result
                self._connection.request_cancel()

        # block until session finishes
        try:
            self.result()
        except SessionCancelledError:
            # this is what we want
            return
        else:
            raise CancelFailedError()

    def cancelled(self):
        return self._future.cancelled()

    def running(self):
        return self._future.running()

    def result(self, timeout=None):
        try:
            return self._future.result(timeout=timeout)
        except concurrent.futures.CancelledError as e:
            raise SessionCancelledError() from e

    def add_done_callback(self, fn):
        return self._future.add_done_callback(fn)

    def unbind(self):
        try:
            self.cancel()
        except SessionCompletedError:
            pass
