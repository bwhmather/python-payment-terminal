import weakref
import gc
import threading
import time
import unittest

from nm_payment.stream import TimeoutError, _Future, _Chain, StreamBuilder


class TestStream(unittest.TestCase):
    def test_future_simple(self):
        message = _Future()
        message.set_result(42)
        self.assertEqual(message.wait(), 42)

    def test_future_wait(self):
        message = _Future()

        def set_42():
            # XXX should be sufficient to make sure this gets called after wait
            time.sleep(0.05)
            message.set_result(42)
        t = threading.Thread(target=set_42, daemon=True)
        t.start()

        self.assertEqual(message.wait(), 42)
        t.join()

    def test_future_timeout(self):
        message = _Future()
        try:
            message.wait(timeout=0.05)
        except TimeoutError:
            pass

    def test_chain(self):
        chain = _Chain()
        chain.push(2)
        self.assertEqual(chain.wait_result(), 2)

    def test_chain_iter(self):
        head = _Chain()
        chain = head

        for i in [1, 2, 3, 4, 5]:
            chain = chain.push(i)
        chain.close()

        self.assertEqual(list(head), [1, 2, 3, 4, 5])

    def test_memory(self):
        # Make sure that chains don't hold references to previous links
        chain = _Chain()
        head = weakref.ref(chain)
        for i in range(100000):
            chain = chain.push(i)
        gc.collect()
        self.assertIsNone(head())

    def test_iter_memory(self):
        # Make sure that chain iterators do not hold a reference to the head
        chain = _Chain()

        def push_100000(chain):
            for i in range(100000):
                chain = chain.push(i)
        t = threading.Thread(target=push_100000, args=(chain,), daemon=True)

        iterator = iter(chain)
        chain = weakref.ref(chain)

        t.start()
        for i in range(100000):
            next(iterator)

        t.join()

        gc.collect()
        self.assertIsNone(chain())

    def test_builder(self):
        builder = StreamBuilder()
        stream = builder.stream()

        self.assertIsNone(next(stream))
        self.assertIsNone(builder.head())

        for i in [1, 2, 3, 4, 5]:
            builder.push(i)
            self.assertEqual(builder.head(), i)
        builder.close()

        self.assertEqual(list(stream), [1, 2, 3, 4, 5])
