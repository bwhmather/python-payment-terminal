class ConnectionError(Exception):
    pass


class SessionCompletedError(Exception):
    """ Could not perform operation on session as session is finished
    """
    pass


class SessionCancelledError(SessionCompletedError):
    """ Could not perform operation on session as session has been cancelled
    """
    pass
