import socket
from urllib.parse import urlparse
import concurrent.futures
from threading import Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import Terminal, PaymentSession
from nm_payment.exceptions import SessionCompletedError, SessionCancelledError

from .connection import _BBSMsgRouterConnection


class CancelFailedError(Exception):
    """ Really bad
    """
    # TODO
    pass


class _BBSSession(object):
    def __init__(self, connection):
        super(_BBSSession, self).__init__()
        self._connection = connection
        self._connection._set_current_session(self)

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


class _BBSPaymentSession(_BBSSession, PaymentSession):
    def __init__(self, connection, amount, commit_callback):
        super(_BBSPaymentSession, self).__init__(connection)
        self._future = concurrent.futures.Future()
        self._lock = Lock()

        self._commit_callback = commit_callback

        self._connection.request_transfer_amount(amount).result()

    def _rollback(self):
        try:
            self._connection.request_rollback().wait()
        except Exception as e:
            # XXX This is really really bad
            raise CancelFailedError() from e

    def on_req_local_mode(self, result, **kwargs):
        """
        .. note:: Internal use only
        """
        with self._lock:
            if self._future.set_running_or_notify_cancel():
                if result == 'success':
                    if (self._commit_callback and
                            not self._commit_callback(result)):
                        try:
                            self._rollback()
                        except Exception as e:
                            self._future.set_exception(e)
                            raise
                        else:
                            self._future.set_exception(SessionCancelledError())
                    else:
                        self._future.set_result(None)
                else:
                    # TODO interpret errors from ITU
                    self._future.set_exception(Exception())
            else:
                if result == 'success':
                    # An attempt was made to cancel but local mode message was
                    # already in flight
                    # TODO
                    self._rollback()

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

            self._connection.request_cancel().wait()

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


class BBSMsgRouterTerminal(Terminal):
    def __init__(self, port):
        self._connection = _BBSMsgRouterConnection(port)

    def start_payment(self, amount, *, before_commit=None):
        return _BBSPaymentSession(
            self._connection, amount, before_commit=before_commit
        )

    def shutdown(self):
        self._connection.shutdown()


def open_tcp(uri, *args, **kwargs):
    uri_parts = urlparse(uri)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((uri_parts.hostname, uri_parts.port))
    port = s.makefile(mode='r+b', buffering=True)

    return BBSMsgRouterTerminal(port)
