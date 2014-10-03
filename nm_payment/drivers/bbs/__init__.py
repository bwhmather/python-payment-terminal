import queue
import struct
import socket
from urllib.parse import urlparse
import concurrent.futures
from threading import Thread, Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import Terminal, PaymentSession
from nm_payment.stream import Stream
from nm_payment.exceptions import SessionCompletedError, SessionCancelledError

from . import messages


def read_frame(port):
    header = port.read(2)
    if len(header) == 0:
        raise Exception("end of file")
    size, = struct.unpack('>H', header)
    assert size > 1
    frame = port.read(size)
    if len(frame) < size:
        raise Exception("unexpected end of file")
    return frame


def write_frame(port, data):
    port.write(struct.pack('>H', len(data)))
    port.write(data)
    port.flush()


class TerminalError(Exception):
    """ Base class for error messages responses from the ITU
    """
    pass


class ResponseInterruptedError(Exception):
    """ Request was sent but connection was closed before receiving a response
    """
    pass


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


class _Message(concurrent.futures.Future):
    def __init__(self, data):
        super(_Message, self).__init__()
        self.data = data


class _Response(_Message):
    expects_response = False


class _Request(_Message):
    expects_response = True


class _BBSMsgRouterConnection(object):
    def __init__(self, port):
        super(_BBSMsgRouterConnection, self).__init__()

        self._REQUEST_CODES = {
            messages.DisplayTextMessage: self._on_req_display_text,
            messages.PrintTextMessage: self._on_req_print_text,
            messages.ResetTimerMessage: self._on_req_reset_timer,
            messages.LocalModeMessage: self._on_req_local_mode,
            messages.KeyboardInputRequestMessage: self._on_req_keyboard_input,
            messages.SendDataMessage: self._on_req_send_data,
            messages.DeviceAttributeRequestMessage: self._on_req_device_attr,
            messages.StatusMessage: self._on_req_status,
        }

        self._port = port

        self._shutdown = False
        self._shutdown_lock = Lock()

        self._current_session = None
        self._current_session_lock = Lock()

        self._status = Stream()

        # A queue of Message futures to be sent from the send thread
        self._send_queue = queue.Queue()
        # A queue of futures expecting a response from the card reader
        self._response_queue = queue.Queue()

        self._send_thread = Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()

        self._receive_thread = Thread(target=self._receive_loop, daemon=True)
        self._receive_thread.start()

    def _set_current_session(self, session):
        with self._current_session_lock:
            if self._current_session is not None:
                self._current_session.unbind()
            self._current_session = session

    def _request(self, message):
        """ Send a request to the card reader

        :param message: bytestring to send to the ITU

        :return: a Future that will yield the response
        """
        request = _Request(message)
        self._send_queue.put(request)
        return request

    def request_transfer_amount(self):
        """ Start a payment Bank Mode session.

        Maps directly to a single H51 request to the ITU

        .. note:: Should only be called by the current session.
        """
        message = messages.TransferAmmountMessage()
        return self._request(message.pack())

    def request_abort(self):
        """ Request that the ITU exit Bank Mode.  A successful response does
        not indicate that a request was cancelled.  Session should wait for
        the Local Mode request to determine the result.

        Maps directly to a single H53 request to the ITU

        .. note:: Should only be called by the current session.
        """
        # TODO
        raise NotImplementedError()

    def request_reversal(self):
        """ Request that the ITU reverse the most recent payment.

        Maps directly to a single H53 request to the ITU

        .. note:: Should only be called by the current session.
        """
        # TODO
        raise NotImplementedError()

    def _respond(self, message, *, async=False):
        """ Respond to a request from the card reader

        :param bytes message: bytestring to send to the ITU
        :param bool async:
            If ``True``, :py:meth:`_respond` will block until the response has
            been sent.
            If ``False`` it will return a future that will yield ``None`` on
            completion
        :return:
            If ``async`` is ``False``, a :py:class:`concurrent.futures.Future`
            that will yield ``None`` once the response has been sent.
            Otherwise nothing.
        """
        response = _Response(message)
        self._send_queue.put(response)
        if async:
            return response
        else:
            response.result()

    def _send_loop(self):
        """ Thread responsible for output to the card reader.

        The send thread reads messages from send queue and writes them to port.
        Futures for messages expecting a response are pushed onto the response
        queue in order that the requests were sent.
        """
        try:
            while not self._shutdown:
                message = self._send_queue.get()
                if message is None:
                    # shutdown will push None onto the send queue to stop send
                    # loop from blocking on get forever
                    return
                log.debug("sending message: %r" % message)
                if message.set_running_or_notify_cancel():
                    write_frame(self._port, message.data)

                    if message.expects_response:
                        self._response_queue.put(message)
                    else:
                        message.set_result(None)
        except Exception:
            if not self._shutdown:
                log.exception("error sending data")
                self._shutdown_async()

    def _on_req_display_text(self, message):
        return self._current_session.on_req_display_text(
            message.text,
            prompt_customer=message.prompt_customer,
            expects_input=message.expects_input
        )

    def _on_req_print_text(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_reset_timer(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_local_mode(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_keyboard_input(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_send_data(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_device_attr(self, message):
        # TODO
        raise NotImplementedError()

    def _on_req_status(self, message):
        # TODO
        raise NotImplementedError()

    def _handle_request(self, message):
        # TODO XXX hacky XXX
        handler = self._REQUEST_CODES[message.__class__]

        try:
            response = handler(message)
            if response is None:
                response = messages.ResponseMessage()

        except TerminalError as e:
            # exception is intended for the ITU and shouldn't cause
            # the driver to shut down
            log.warning(
                "error handling message from terminal",
                exc_info=True
            )
            response = self._ack_exception(e)

        except Exception:
            # log and break
            log.exception("critical error while handling message")
            raise

        self._respond(response)

    def _handle_response(self, message):
        try:
            request = self._response_queue.get_nowait()
        except queue.Empty:
            log.error("response has no corresponding request")
            raise

        request.set_result(message)

    def _receive_loop(self):
        """ Thread responsible for receiving input from the card reader.

        Reads frames one at a time and either links them to a response or
        dispatches them to a request handler.
        """
        try:
            while not self._shutdown:
                frame = read_frame(self._port)
                log.debug("message recieved: %r" % frame)
                message = messages.unpack_itu_message(frame)

                if message.is_response:
                    self._handle_response(message)
                else:
                    self._handle_request(message)
        except Exception:
            if not self._shutdown:
                log.exception("error receiving data")
                self._shutdown_async()

    def shutdown(self):
        """ Closes connection to the ITU and cancels all requests.
        Threadsafe and can be called multiple times safely.
        Will block until everything has been cleaned up.
        """
        with self._shutdown_lock:
            if not self._shutdown:
                log.debug("shutting down")
                self._shutdown = True
                # send loop will block trying to fetch items from it's queue
                # forever unless we push something onto it
                self._send_queue.put(None)
                # response queue could hang if the send and receive sides have
                # got out of sync.  Shouldn't happen but best to make sure
                self._response_queue.put(None)

                self._port.close()

                self._send_thread.join()
                self._receive_thread.join()

                while not self._send_queue.empty():
                    message = self._send_queue.get()
                    if message is not None:
                        message.cancel()

                while not self._response_queue.empty():
                    message = self._response_queue.get()
                    if message is not None:
                        message.set_exception(ResponseInterruptedError())
                log.debug("successfully shut down")

    def _shutdown_async(self):
        """ Shutdown without blocking.
        """
        Thread(target=self.shutdown).start()


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
