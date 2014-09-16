import unittest

from nm_payment.tests.test_bbs import TestBBS
from nm_payment.tests.test_bbs_fields import TestBBSFields
from nm_payment.tests.test_bbs_messages import TestBBSMessages
from nm_payment.tests.test_stream import TestStream


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(TestBBS),
    loader.loadTestsFromTestCase(TestBBSFields),
    loader.loadTestsFromTestCase(TestBBSMessages),
    loader.loadTestsFromTestCase(TestStream),
))
