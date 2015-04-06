import socket
from urllib.parse import urlparse

from payment_terminal.base import Terminal

from .connection import BBSMsgRouterConnection
from .payment_session import BBSPaymentSession

import logging
log = logging.getLogger('payment_terminal')


class BBSMsgRouterTerminal(Terminal):
    def __init__(self, port):
        self._connection = BBSMsgRouterConnection(port)

    def start_payment(
            self, amount, *, before_commit=None,
            on_print=None, on_display=None):
        """
        :returns: a new active ``PaymentSession`` object
        """
        return BBSPaymentSession(
            self._connection, amount, before_commit=before_commit,
            on_print=on_print, on_display=on_display
        )

    def shutdown(self):
        self._connection.shutdown()


def open_tcp(uri):
    uri_parts = urlparse(uri)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((uri_parts.hostname, uri_parts.port))
    port = s.makefile(mode='r+b', buffering=True)

    return BBSMsgRouterTerminal(port)

__all__ = ['BBSMsgRouterTerminal', 'open_tcp']
