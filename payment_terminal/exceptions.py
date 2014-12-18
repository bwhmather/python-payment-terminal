class NotSupportedError(Exception):
    """ Raised if a driver does not exist for a uri scheme
    """
    pass


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


class CancelFailedError(Exception):
    """ Really bad
    """
    # TODO
    pass
