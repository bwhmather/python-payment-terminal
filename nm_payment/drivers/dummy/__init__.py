from threading import Thread, Lock, Event

from nm_payment.base import Terminal, PaymentSession
from nm_payment.exceptions import SessionCancelledError, SessionCompletedError


class DummyPaymentSession(PaymentSession):
    def __init__(
            self, amount, *, before_commit=None,
            on_print=lambda *args, **kwargs: None,
            on_display=lambda *args, **kwargs: None):
        self._lock = Lock()
        self._cancel = Event()

        self._before_commit = before_commit
        self._on_display = on_display
        self._on_print = on_print

        self._result = None
        self._exception = None

        self._thread = Thread(target=self._sequence)
        self._thread.start()

    def _sleep(self, timeout):
        if self._cancel.wait(timeout):
            raise SessionCancelledError()

    def _sequence(self):
        try:
            self._on_display("Insert card")

            self._sleep(1)

            self._on_display("Enter pin")

            self._sleep(3)

            commit = True
            if self._before_commit is not None:
                # TODO result
                commit = self._before_commit(None)

            if commit:
                # TODO
                self._result = True
            else:
                self._exception = SessionCancelledError()
        except BaseException as e:
            with self._lock:
                self._exception = e
            raise

    def cancel(self):
        with self._lock:
            if not self._cancel.is_set():
                self._cancel.set()

        try:
            self.result()
        except SessionCancelledError:
            return
        # TODO do other exceptions count as a cancellation
        else:
            raise SessionCompletedError()

    def result(self, *, timeout=None):
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError()

        if self._exception is not None:
            raise self._exception
        return self._result

    def add_done_callback(self, fn):
        def wait():
            try:
                self.result()
            except Exception:
                pass
            fn(self)

        Thread(target=wait, daemon=True).start()


class DummyTerminal(Terminal):
    def __init__(self):
        self._lock = Lock()
        self._current_session = None

    def start_payment(
            self, amount, *, before_commit=None,
            on_print=None, on_display=None):
        with self._lock:
            if self._current_session is not None:
                try:
                    self._current_session.cancel()
                # TODO too narrow?
                except SessionCompletedError:
                    pass
            self._current_session = DummyPaymentSession(
                amount, before_commit=before_commit,
                on_print=on_print, on_display=on_display
            )
        return self._current_session

    def shutdown(self):
        pass


def open_dummy(uri, *args, **kwargs):
    return DummyTerminal()
