class Session(object):
    pass


class PaymentSession(Session):
    def is_authorized(self):
        raise NotImplementedError()

    def wait_authorized(self):
        raise NotImplementedError()

    def add_authorized_callback(self, callback):
        raise NotImplementedError()

    def is_completed(self):
        raise NotImplementedError()

    def wait_completed(self):
        raise NotImplementedError()

    def add_completed_callback(self):
        raise NotImplementedError()

    def commit(self):
        """
        :raises NotAuthorizedError: If card reader has not yet authorized the
            payment
        :raises CompletedError: If commit has already been called
        :raises CancelledError: If the payment has been cancelled or reversed
        """
        raise NotImplementedError()

    def cancel(self):
        """
        :raises CompletedError: If commit has already been called
        """
        raise NotImplementedError()


class Terminal(object):
    def start_payment(self, amount, *, on_print=None, on_display=None):
        """
        :returns: a new active ``PaymentSession`` object
        """
        pass

    def get_current_session(self):
        pass

    def shutdown(self):
        pass
