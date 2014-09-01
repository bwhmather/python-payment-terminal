from threading import Condition


class TimeoutError(Exception):
    pass


class _Future(object):
    def __init__(self):
        self._completed = False
        self._result = None
        self._condition = Condition()

    def set_result(self, result):
        with self._condition:
            if self._completed:
                raise Exception("result already set")
            self._completed = True
            self._result = result
            self._condition.notify_all()

    def wait(self, timeout=None):
        with self._condition:
            if not self._completed:
                if not self._condition.wait(timeout):
                    raise TimeoutError()
            return self._result


class Chain(object):
    def __init__(self):
        self._next = _Future()

    def push(self, value):
        next_ = Chain()
        self._next.set_result((value, next_))
        return next_

    def wait(self, timeout=None):
        return self._next.wait(timeout)

    def wait_result(self, timeout=None):
        return self.wait(timeout)[0]

    def wait_next(self, timeout=None):
        return self.wait(timeout)[1]

    def __iter__(self):
        return Stream(self)


class Stream(object):
    def __init__(self, head):
        self._next = head

    def wait(self, timeout=None):
        result, self._next = self._next.wait(timeout)
        return result

    def __iter__(self):
        return self

    def __next__(self):
        return self.wait()
