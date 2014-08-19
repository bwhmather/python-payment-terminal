import io
import unittest

from nm_payment.drivers.bbs import read_frame


class TestBBS(unittest.TestCase):
    def test_read_frame(self):
        port = io.BytesIO(b'\x0512345')
        self.assertEqual(read_frame(port), b'12345')

        port = io.BytesIO(b'\x0512345\x06123456')
        self.assertEqual(read_frame(port), b'12345')
        self.assertEqual(read_frame(port), b'123456')

        port = io.BytesIO(b'\x09trunca')
        try:
            read_frame(port)
        except Exception:  # TODO more specific
            pass
        else:
            self.fail()
