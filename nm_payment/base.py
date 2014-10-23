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
        :raises SessionCompletedError: If commit has already been called
        """
        raise NotImplementedError()


class Terminal(object):
    def start_payment(
            self, amount, *, before_commit=None,
            on_print=None, on_display=None):
        """
        :param amount:
            The amount of money to request

        :param before_commit:
            function to be called after transaction is authorized but before it
            is committed.  It should take a ``Payment`` result object as its
            only argument.  If it returns True, the card will be charged.  If
            it returns False the transaction will be rolled back.  Exceptions
            will be re-raised by the ``PaymentSession.result`` method.

        :param on_print:
            function to be called when a print message is received

        :param on_display:
            function to be called when a display message is received.
            Should accept the string to display as it's first argument and two
            keyword arguments: ``prompt_customer`` and ``expects_input``.
            TODO

        :returns: a new active ``PaymentSession`` object
        """
        pass

    def get_current_session(self):
        pass

    def shutdown(self):
        pass
