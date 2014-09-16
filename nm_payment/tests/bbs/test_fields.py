import io
import unittest

import nm_payment.drivers.bbs.fields as f


class TestBBSFields(unittest.TestCase):
    def test_text_field(self):
        self.assertEqual(f.TextField().size, None)
        self.assertEqual(f.TextField(4).size, 4)

    def test_write_text(self):
        buf = io.BytesIO()
        f.TextField().write("hello", buf)
        self.assertEqual(buf.getvalue(), b'hello')

        buf = io.BytesIO()
        f.TextField(10).write("padded", buf)
        self.assertEqual(buf.getvalue(), b'padded    ')

        buf = io.BytesIO()
        self.assertRaises(
            ValueError,
            f.TextField(4).write, "loooonnnngggg", buf
        )

    def test_read_text(self):
        buf = io.BytesIO(b'hello')
        self.assertEqual(f.TextField().read(buf), "hello")

        buf = io.BytesIO(b'loooonnnngggg')
        self.assertEqual(f.TextField(5).read(buf), "loooo")
        self.assertEqual(buf.read(), b"nnnngggg")

        buf = io.BytesIO(b'short')
        self.assertRaises(ValueError, f.TextField(120).read, buf)
