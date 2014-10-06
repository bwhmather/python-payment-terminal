class Session(object):
    pass


class Payment(object):
    def __init__(
            self, amount, pan, card_end_date,
            provider_scheme, provider_auth_code):
        pass


class PaymentSession(Session):
    def result(self, timeout=None):
        raise NotImplementedError()

    def cancel(self):
        """
        :raises CompletedError: If commit has already been called
        """
        raise NotImplementedError()


class Terminal(object):
    def start_payment(
            self, amount, *, before_commit=None,
            on_print=None, on_display=None):
        """
        :returns: a new active ``PaymentSession`` object
        """
        pass

    def get_current_session(self):
        pass

    def shutdown(self):
        pass
