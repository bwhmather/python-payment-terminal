import unittest

from nm_payment.drivers.bbs.fields import ConstantField
import nm_payment.drivers.bbs.messages as m


class TestBBSMessages(unittest.TestCase):
    def test_message_meta(self):
        class TestMessage(m.BBSMessage):
            normal_field = "nothing interesting"
            pitch_field = ConstantField(b'constant')

        self.assertTrue(hasattr(TestMessage, '_fields'))

        self.assertTrue(hasattr(TestMessage, 'pitch_field'))
        self.assertTrue(hasattr(TestMessage, 'normal_field'))

    def test_message_inheritance(self):
        class BaseMessage(m.BBSMessage):
            first = ConstantField(b'one')
            second = ConstantField(b'two')
            third = ConstantField(b'three')

        class ChildMessage(BaseMessage):
            second = ConstantField(b'overridden')
            fourth = ConstantField(b'four')

        self.assertEqual(
            list(ChildMessage._fields.keys()),
            ['first', 'second', 'third', 'fourth']
        )

        self.assertEqual(
            [field.value for field in ChildMessage._fields.values()],
            [b'one', b'overridden', b'three', b'four']
        )

    def test_pack_display_text(self):
        self.assertEqual(
            b'\x41100Hello World',
            m.DisplayTextMessage("Hello World").pack()
        )

        self.assertEqual(
            b'\x41000Prompt customer',
            m.DisplayTextMessage(
                "Prompt customer", prompt_customer=False
            ).pack()
        )

        self.assertEqual(
            b'\x41110Expects input',
            m.DisplayTextMessage(
                "Expects input", expects_input=True
            ).pack()
        )

    def test_unpack_display_text(self):
        message = m.DisplayTextMessage.unpack(b'\x41000Hello World')
        self.assertFalse(message.prompt_customer)
        self.assertFalse(message.expects_input)
        self.assertEqual(message.text, "Hello World")

        message = m.DisplayTextMessage.unpack(b'\x41100Prompt customer')
        self.assertTrue(message.prompt_customer)
        self.assertFalse(message.expects_input)
        self.assertEqual(message.text, "Prompt customer")

        message = m.DisplayTextMessage.unpack(b'\x41010Expects input')
        self.assertFalse(message.prompt_customer)
        self.assertTrue(message.expects_input)
        self.assertEqual(message.text, "Expects input")

    def test_pack_print_text(self):
        self.assertEqual(
            m.PrintTextMessage(commands=[
                ('write', "First"),
                ('cut-partial'),
                ('write', "Second"),
                ('cut-through'),
            ]).pack(),
            b'\x42\x20\x22\x2aFirst\x0eSecond\x0c'
        )

    def test_unpack_print_text(self):
        message = m.PrintTextMessage.unpack(
            b'\x42\x20\x22\x2aFirst\x0eSecond\x0c'
        )
        self.assertEqual(
            message.commands,
            [
                ('write', "First"),
                ('cut-partial'),
                ('write', "Second"),
                ('cut-through'),
            ]
        )

    def test_pack_reset_timer(self):
        self.assertEqual(m.ResetTimerMessage(60).pack(), b'\x43060')

        try:
            m.ResetTimerMessage(6000).pack()
        except ValueError:
            pass
        else:
            self.fail()

    def test_unpack_reset_timer(self):
        self.assertEqual(m.ResetTimerMessage.unpack(b'\x43060').seconds, 60)

        try:
            m.ResetTimerMessage.unpack(b'\x43abc')
        except:
            pass
        else:
            self.fail()
