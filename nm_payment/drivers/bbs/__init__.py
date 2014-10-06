import socket
from urllib.parse import urlparse

import logging
log = logging.getLogger('nm_payment')

from nm_payment.base import Terminal

from .connection import _BBSMsgRouterConnection
from .payment_session import _BBSPaymentSession


class BBSMsgRouterTerminal(Terminal):
    def __init__(self, port):
        self._connection = _BBSMsgRouterConnection(port)

    def start_payment(self, amount, *, before_commit=None):
        return _BBSPaymentSession(
            self._connection, amount, before_commit=before_commit
        )

    def shutdown(self):
        self._connection.shutdown()


def open_tcp(uri, *args, **kwargs):
    uri_parts = urlparse(uri)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((uri_parts.hostname, uri_parts.port))
    port = s.makefile(mode='r+b', buffering=True)

    return BBSMsgRouterTerminal(port)
