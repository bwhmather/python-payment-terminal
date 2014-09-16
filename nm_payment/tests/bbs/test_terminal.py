import io
import unittest
import threading

from nm_payment.drivers.bbs import read_frame, BBSMsgRouterTerminal


class TestBBSTerminal(unittest.TestCase):
    def test_read_frame(self):
        port = io.BytesIO(b'\x00\x0512345')
        self.assertEqual(read_frame(port), b'12345')

        port = io.BytesIO(b'\x00\x0512345\x00\x06123456')
        self.assertEqual(read_frame(port), b'12345')
        self.assertEqual(read_frame(port), b'123456')

        port = io.BytesIO(b'\x00\x09trunca')
        try:
            read_frame(port)
        except Exception:  # TODO more specific
            pass
        else:
            self.fail()

    def test_startup_shutdown(self):
        class CloseableFile(object):
            def __init__(self):
                self._closed = threading.Event()

            def read(self, *args, **kwargs):
                self._closed.wait()
                raise ValueError()

            def close(self):
                self._closed.set()

        terminal = BBSMsgRouterTerminal(CloseableFile())
        terminal.shutdown()
