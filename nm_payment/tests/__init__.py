import unittest

from nm_payment.tests.test_bbs import TestBBS


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(TestBBS),
))
