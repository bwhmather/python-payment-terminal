import unittest

from payment_terminal import open_terminal, register_driver


class TestLoader(unittest.TestCase):
    def test_open_test_driver(self):
        handle = object()

        def test_driver(uri):
            return handle

        register_driver('opentestdriver', test_driver)

        self.assertIs(open_terminal('opentestdriver://'), handle)

    def test_no_scheme(self):
        self.assertRaises(ValueError, open_terminal, 'example.com')
