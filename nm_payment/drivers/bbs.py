import queue
import struct
import socket
from urllib.parse import urlparse
from concurrent.futures import Future
from threading import Thread, Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import Terminal, PaymentSession
from nm_payment.stream import Stream


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


def parse_response_code(message):
    return struct.unpack('B', message[:1])


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


class BBSSession(object):
    def __init__(self, terminal):
        super(BBSSession, self).__init__()
        self._terminal = terminal
        self._terminal._set_current_session(self)

    def on_req_display_text(self, data):
        raise NotImplementedError()

    def on_req_print_text(self, data):
        raise NotImplementedError()

    def on_req_reset_timer(self, data):
        raise NotImplementedError()

    def on_req_local_mode(self, data):
        raise NotImplementedError()

    def on_req_keyboard_input(self, data):
        raise NotImplementedError()

    def on_req_send_data(self, data):
        raise NotImplementedError()

    def on_req_device_attr(self, data):
        raise NotImplementedError()

    def unbind(self):
        pass


class BBSPaymentSession(BBSSession, PaymentSession):
    def __init__(self, terminal, amount):
        super(BBSPaymentSession, self).__init__(terminal)

        self._terminal.request("transfer_amount", amount).wait()

    def on_req_local_mode(self, data):
        pass

    def commit(self):
        pass

    def cancel(self):
        pass


class _Message(Future):
    def __init__(self, data):
        super(_Message, self).__init__()
        self.data = data


class _Response(_Message):
    expects_response = False


class _Request(_Message):
    expects_response = True


class BBSMsgRouterTerminal(Terminal):
    def __init__(self, port):
        super(BBSMsgRouterTerminal, self).__init__()

        self._REQUEST_CODES = {
            0x41: self._on_req_display_text,
            0x42: self._on_req_print_text,
            0x43: self._on_req_reset_timer,
            0x44: self._on_req_local_mode,
            0x46: self._on_req_keyboard_input,
            0x49: self._on_req_send_data,
            0x60: self._on_req_device_attr,
        }

        self._RESPONSE_CODES = {
            0x5b: self._parse_ack,
            0x62: self._parse_device_attr_ack,
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
        with self._session_lock:
            if self._current_session is not None:
                self._current_session.unbind()
            self._current_session = session

    def request(self, message):
        """ Send a request to the card reader

        :param message: bytestring to send to the ITU

        :return: a Future that will yield the response
        """
        request = _Request(message)
        self._send_queue.put(request)
        return request

    def _respond(self, message):
        """ Respond to a request from the card reader

        :param message: bytestring to send to the ITU

        :return: a future that will yield None once the response has been sent
        """
        response = _Response(message)
        self._send_queue.put(response)
        return response

    def _on_req_display_text(self, data):
        raise NotImplementedError()

    def _on_req_print_text(self, data):
        raise NotImplementedError()

    def _on_req_reset_timer(self, data):
        raise NotImplementedError()

    def _on_req_local_mode(self, data):
        raise NotImplementedError()

    def _on_req_keyboard_input(self, data):
        raise NotImplementedError()

    def _on_req_send_data(self, data):
        raise NotImplementedError()

    def _on_req_device_attr(self, data):
        raise NotImplementedError()

    def _handle_request(self, frame):
        header = parse_response_code(frame)
        try:
            response = self._REQUEST_CODES[header](frame)
            if response is None:
                response = self._ack_ok()

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

    def _parse_ack(self, data):
        response_code = struct.unpack('>I', data[1:3])
        if response_code == 0x3030:
            return None
        else:
            raise TerminalError(response_code)

    def _parse_device_attr_ack(self, data):
        return None

    def _is_response(self, frame):
        header = parse_response_code(frame)
        return header in self._RESPONSE_CODES

    def _handle_response(self, frame):
        header = parse_response_code(frame)
        try:
            request = self._response_queue.get_nowait()
        except queue.Empty:
            log.error("response has no corresponding request")
            raise

        try:
            # decode the response
            response = self._RESPONSE_CODES[header](frame)
        except TerminalError as e:
            # error from ITU.  No need to exit
            request.set_exception(e)
        except Exception as e:
            # other exception.  Need to close the request before
            # breaking from the loop
            request.set_exception(e)
            raise
        else:
            request.set_result(response)

    def _receive_loop(self):
        try:
            while not self._shutdown:
                frame = read_frame(self._port)
                log.debug("message recieved: %r" % frame)
                if self._is_response(frame):
                    self._handle_response(frame)
                else:
                    self._handle_request(frame)
        except Exception:
            if not self._shutdown:
                log.exception("error receiving data")
                self._shutdown_async()

    def _send_loop(self):
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
        Thread(target=self.shutdown)


def open_tcp(uri, *args, **kwargs):
    uri_parts = urlparse(uri)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((uri_parts.hostname, uri_parts.port))
    port = s.makefile(mode='r+b', buffering=True)

    return BBSMsgRouterTerminal(port)
