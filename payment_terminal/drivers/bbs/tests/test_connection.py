import threading
import unittest

from payment_terminal.drivers.bbs.connection import BBSMsgRouterConnection


class TestBBSConnection(unittest.TestCase):
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
