import threading
import unittest

from nm_payment.drivers.bbs import BBSMsgRouterTerminal


class TestBBSTerminal(unittest.TestCase):
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
