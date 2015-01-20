import io
import unittest

from payment_terminal.drivers.bbs.connection import read_frame, write_frame


class TestBBSFrames(unittest.TestCase):
    def test_read_one(self):
        port = io.BytesIO(b'\x00\x0512345')
        self.assertEqual(read_frame(port), b'12345')

    def test_read_two(self):
        port = io.BytesIO(b'\x00\x0512345\x00\x06123456')
        self.assertEqual(read_frame(port), b'12345')
        self.assertEqual(read_frame(port), b'123456')

    def test_read_end_of_file(self):
        port = io.BytesIO(b'')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_read_truncated_header(self):
        port = io.BytesIO(b'a')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_read_truncated_body(self):
        port = io.BytesIO(b'\x00\x09trunca')
        # TODO more specific
        self.assertRaises(Exception, read_frame, port)

    def test_write_one(self):
        port = io.BytesIO()
        write_frame(port, b'hello world')
        self.assertEqual(port.getvalue(), b'\x00\x0bhello world')

    def test_write_two(self):
        port = io.BytesIO()
        write_frame(port, b'12345')
        write_frame(port, b'123456')
        self.assertEqual(port.getvalue(), b'\x00\x0512345\x00\x06123456')

    def test_write_too_much(self):
        port = io.BytesIO()
        # TODO more specific
        self.assertRaises(Exception, write_frame, port, b'x' * 2**16)
