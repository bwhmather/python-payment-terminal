from urllib.parse import urlparse

from nm_payment.drivers import bbs


_BUILTIN_DRIVERS = {
    'bbs+tcp': bbs.open_tcp,
}

_drivers = {}
_drivers.update(_BUILTIN_DRIVERS)


def register_driver(uri_scheme, factory):
    _drivers[uri_scheme] = factory


def open_terminal(uri, *args, **kwargs):
    scheme = urlparse(uri).scheme
    if not scheme or scheme == uri:
        raise ValueError("Malformed terminal uri")
    try:
        driver = _drivers[scheme]
    except KeyError:
        raise Exception("Unrecognised terminal uri")
    else:
        return driver(uri, *args, **kwargs)

__all__ = [register_driver, open_terminal]
