from threading import Lock
from concurrent.futures import Future, CancelledError, TimeoutError


class ClosedError(Exception):
    pass


class _Chain(object):
    def __init__(self):
        self._next = Future()

    def push(self, value):
        next_ = _Chain()
        self._next.set_result((value, next_))
        return next_

    def close(self):
        self._next.cancel()

    def wait(self, timeout=None):
        try:
            result = self._next.result(timeout)
        except CancelledError:
            raise ClosedError()
        return result

    def wait_result(self, timeout=None):
        return self.wait(timeout)[0]

    def wait_next(self, timeout=None):
        return self.wait(timeout)[1]


class StreamIterator(object):
    def __init__(self, head):
        self._next = head

    def wait(self, timeout=None):
        result, self._next = self._next.wait(timeout)
        return result

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.wait()
        except ClosedError:
            raise StopIteration()


class Stream(object):
    def __init__(self, initial=None):
        self._lock = Lock()
        self._chain = _Chain()
        self._chain.push(initial)

    def head(self):
        return self._chain.wait_result()

    def stream(self):
        return StreamIterator(self._chain)

    def push(self, value):
        with self._lock:
            # head of chain should always have a result set
            self._chain = self._chain.wait_next()
            self._chain.push(value)

    def close(self):
        with self._lock:
            self._chain = self._chain.wait_next()
            self._chain.close()

__all__ = ['ClosedError', 'TimeoutError', '_Chain', 'Stream']
