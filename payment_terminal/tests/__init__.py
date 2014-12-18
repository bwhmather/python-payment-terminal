import unittest

from payment_terminal.tests.bbs import (
    TestBBSFields, TestBBSMessages,
    TestBBSTerminal, TestBBSConnection,
    TestBBSPaymentSession,
)


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(TestBBSFields),
    loader.loadTestsFromTestCase(TestBBSMessages),
    loader.loadTestsFromTestCase(TestBBSTerminal),
    loader.loadTestsFromTestCase(TestBBSConnection),
    loader.loadTestsFromTestCase(TestBBSPaymentSession),
))
