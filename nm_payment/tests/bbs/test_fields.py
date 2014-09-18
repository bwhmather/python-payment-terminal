import unittest

import nm_payment.drivers.bbs.fields as f


class TestBBSFields(unittest.TestCase):
    def test_delimited_field(self):
        self.assertEqual(f.DelimitedField(f.TextField()).size, None)
        self.assertEqual(f.DelimitedField(f.TextField(4)).size, 5)
        self.assertEqual(
            f.DelimitedField(f.TextField(4), optional=True).size, None
        )
        self.assertEqual(
            f.DelimitedField(f.TextField(4), delimiter=b'EOF').size, 7
        )

    def test_pack_delimited_field(self):
        self.assertEqual(
            f.DelimitedField(f.TextField()).pack("hello"), b'hello\n'
        )
        self.assertEqual(
            f.DelimitedField(f.TextField(), optional=True).pack(None), b'\n'
        )
        self.assertEqual(
            f.DelimitedField(f.TextField(), delimiter=b'EOF').pack("hello"),
            b'helloEOF'
        )

    def test_unpack_delimited(self):
        self.assertEqual(
            f.DelimitedField(f.TextField()).unpack(b'hello\n'), ("hello", 6)
        )
        self.assertEqual(
            f.DelimitedField(
                f.TextField(), delimiter=b'EOF'
            ).unpack(b'helloEOF'),
            ("hello", 8)
        )
        self.assertRaises(
            ValueError,
            f.DelimitedField(f.TextField(3)).unpack, b'loooonnnngggg\n'
        )

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
