import unittest

import nm_payment.drivers.bbs.fields as f


class TestBBSFields(unittest.TestCase):
    def test_text_field(self):
        self.assertEqual(f.TextField().size, None)
        self.assertEqual(f.TextField(4).size, 4)

    def test_pack_text(self):
        self.assertEqual(f.TextField().pack("hello"), b'hello')

        self.assertEqual(f.TextField(10).pack("padded"), b'padded    ')

        self.assertRaises(
            ValueError,
            f.TextField(4).pack, "loooonnnngggg"
        )

    def test_unpack_text(self):
        self.assertEqual(f.TextField().unpack(b'hello'), ("hello", 5))

        self.assertEqual(f.TextField(5).unpack(b'loooonnnngggg'), ("loooo", 5))

        self.assertRaises(ValueError, f.TextField(120).unpack, b'short')
