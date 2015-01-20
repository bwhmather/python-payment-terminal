import unittest

from payment_terminal.tests import test_loader
import payment_terminal.drivers.bbs.tests as test_bbs


def suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite((
        loader.loadTestsFromModule(test_bbs),
        loader.loadTestsFromModule(test_loader),
    ))
    return suite
