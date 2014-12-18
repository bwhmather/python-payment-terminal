from urllib.parse import urlparse

from payment_terminal.drivers import bbs, dummy


_BUILTIN_DRIVERS = {
    'bbs+tcp': bbs.open_tcp,
    'dummy': dummy.open_dummy,
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

__all__ = ['register_driver', 'open_terminal']
