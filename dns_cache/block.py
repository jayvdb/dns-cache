from contextlib import contextmanager

import dns.query  # noqa
import dns.resolver  # noqa

try:  # pragma: nocover
    from dns.resolver import _Resolution
except ImportError:  # pragma: nocover
    _Resolution = None


class _SocketBlockedError(AssertionError):
    def __init__(self, *args, **kw):
        super(_SocketBlockedError, self).__init__("_socket_factory_blocker invoked")


def _socket_factory_blocker(*args, **kwargs):
    raise _SocketBlockedError()


def _socket_factory_exception_handler(self, response, ex):  # pragma: nocover
    raise ex


@contextmanager
def dnspython_resolver_socket_block():
    import dns.resolver

    real_query_socket_factory = dns.query.socket_factory
    assert dns.resolver.dns.query.socket_factory == real_query_socket_factory
    dns.query.socket_factory = _socket_factory_blocker
    dns.resolver.dns.query.socket_factory = _socket_factory_blocker
    if _Resolution:  # pragma: nocover
        orig_resolution_exception_handler = _Resolution.query_result
        _Resolution.query_result = _socket_factory_exception_handler
    try:
        yield
    finally:
        dns.query.socket_factory = real_query_socket_factory
        dns.resolver.dns.query.socket_factory = real_query_socket_factory
        if _Resolution:  # pragma: nocover
            _Resolution.query_result = orig_resolution_exception_handler
