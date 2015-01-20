import unittest

from payment_terminal.tests.test_loader import TestLoader
import payment_terminal.tests.bbs


def suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite((
        loader.loadTestsFromModule(payment_terminal.tests.bbs),
        loader.loadTestsFromTestCase(TestLoader),
    ))
    return suite
