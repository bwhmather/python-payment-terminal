import weakref
import gc
import threading
import unittest

from nm_payment.stream import _Chain, Stream, StreamIterator


class TestStream(unittest.TestCase):
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

        self.assertEqual(list(StreamIterator(head)), [1, 2, 3, 4, 5])

    def test_memory(self):
        # Make sure that chains don't hold references to previous links
        chain = _Chain()
        head = weakref.ref(chain)
        for i in range(1000):
            chain = chain.push(i)
        gc.collect()
        self.assertIsNone(head())

    def test_iter_memory(self):
        # Make sure that chain iterators do not hold a reference to the head
        chain = _Chain()

        def push_1000(chain):
            for i in range(1000):
                chain = chain.push(i)
        t = threading.Thread(target=push_1000, args=(chain,), daemon=True)

        iterator = StreamIterator(chain)
        chain = weakref.ref(chain)

        t.start()
        for i in range(1000):
            next(iterator)

        t.join()

        gc.collect()
        self.assertIsNone(chain())

    def test_stream(self):
        stream = Stream()

        for i in [1, 2, 3, 4, 5]:
            stream.push(i)
        stream.close()

        self.assertEqual(list(stream), [1, 2, 3, 4, 5])
