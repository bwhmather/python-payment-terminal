class Session(object):
    pass


class PaymentSession(Session):
    def get_authorized():
        raise NotImplementedError()

    def get_completed():
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
