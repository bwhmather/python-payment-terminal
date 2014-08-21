import queue
import struct
import socket
from urllib.parse import urlparse
from concurrent.futures import Future
from threading import Thread, Lock

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import Terminal


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


def parse_header(message):
    return struct.unpack('B', message[:1]), message[1:]


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

        self._RESPONSE_CODES = {
            0x41: self._on_req_display_text,
            0x42: self._on_req_print_text,
            0x43: self._on_req_reset_timer,
            0x44: self._on_req_local_mode,
            0x46: self._on_req_keyboard_input,
            0x49: self._on_req_send_data,
            0x5b: self._on_ack,
            0x60: self._on_req_device_attr,
            0x62: self._on_ack_device_attr,
        }

        self._port = port

        self._shutdown = False
        self._shutdown_lock = Lock()

        # A queue of Message futures to be sent from the send thread
        self._send_queue = queue.Queue()
        # A queue of futures expecting a response from the card reader
        self._response_queue = queue.Queue()

        self._send_thread = Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()

        self._receive_thread = Thread(target=self._receive_loop, daemon=True)
        self._receive_thread.start()

    def _request(self, message):
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

    def _on_ack(self, data):
        request = self._response_queue.get()
        if request is None:
            # terminal has been shut down. bail
            return
        response_code = struct.unpack('>I', data)
        if response_code == 0x3030:
            request.set_result(None)
        else:
            request.set_exception(TerminalError(response_code))

    def _on_req_device_attr(self, data):
        raise NotImplementedError()

    def _on_ack_device_attr(self, data):
        raise NotImplementedError()

    def _receive_loop(self):
        try:
            while not self._shutdown:
                frame = read_frame(self._port)
                header, body = parse_header(frame)

                log.debug("message recieved: %r" % body)
                try:
                    self._RESPONSE_CODES[header](body)
                except Exception:
                    # individual handlers can shut down the terminal on error
                    # no need to shut down as framing should still be intact
                    log.exception("error handling message from terminal")
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
