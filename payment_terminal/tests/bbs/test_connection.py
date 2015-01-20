import io
import threading
import unittest

from payment_terminal.drivers.bbs.connection import (
    read_frame, BBSMsgRouterConnection,
)


class TestBBSConnection(unittest.TestCase):
    def test_read_one(self):
        port = io.BytesIO(b'\x00\x0512345')
        self.assertEqual(read_frame(port), b'12345')

    def test_read_two(self):
        port = io.BytesIO(b'\x00\x0512345\x00\x06123456')
        self.assertEqual(read_frame(port), b'12345')
        self.assertEqual(read_frame(port), b'123456')

    def test_end_of_file(self):
        port = io.BytesIO(b'')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_truncated_header(self):
        port = io.BytesIO(b'a')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_truncated_body(self):
        port = io.BytesIO(b'\x00\x09trunca')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_startup_shutdown(self):
        class CloseableFile(object):
            def __init__(self):
                self._closed = threading.Event()

            def read(self, *args, **kwargs):
                self._closed.wait()
                raise ValueError()

            def close(self):
                self._closed.set()

        terminal = BBSMsgRouterConnection(CloseableFile())
        terminal.shutdown()
