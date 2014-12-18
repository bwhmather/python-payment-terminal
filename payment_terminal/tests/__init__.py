import unittest

from payment_terminal.tests.test_loader import TestLoader
from payment_terminal.tests.bbs import (
    TestBBSFields, TestBBSMessages,
    TestBBSTerminal, TestBBSConnection,
    TestBBSPaymentSession,
)


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(TestLoader),
    loader.loadTestsFromTestCase(TestBBSFields),
    loader.loadTestsFromTestCase(TestBBSMessages),
    loader.loadTestsFromTestCase(TestBBSTerminal),
    loader.loadTestsFromTestCase(TestBBSConnection),
    loader.loadTestsFromTestCase(TestBBSPaymentSession),
))
