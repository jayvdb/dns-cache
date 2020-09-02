import socket
import unittest

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A
from dns.resolver import restore_system_resolver

from dns_cache import override_system_resolver
from dns_cache.block import dnspython_resolver_socket_block
from dns_cache.hosts import loads
from dns_cache.persistence import _LayeredCache
from dns_cache.resolver import DNSPYTHON_2

from .test_upstream import orig_gethostbyname


class TestHostsSerializer(unittest.TestCase):
    def test_loads(self):
        data = loads()
        assert data


class TestHostsCache(unittest.TestCase):

    def test_hit_localhost(self):
        name = "localhost"
        assert socket.gethostbyname == orig_gethostbyname

        try:
            socket.gethostbyname(name)
        except Exception as e:
            raise unittest.SkipTest("gethostbyname: {}".format(e))

        resolver = override_system_resolver()
        assert isinstance(resolver.cache, _LayeredCache)

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        q1 = query(name)

        assert len(resolver.cache._read_only_cache.data) >= 1
        # The layering does a put, which pushes localhost into cache2
        # TODO this needs to be blocked
        assert len(resolver.cache._writable_cache.data) == 1

        assert q1

        name = from_text(name)

        assert (name, A, IN) in resolver.cache.data
        assert resolver.cache.get((name, A, IN))

        with dnspython_resolver_socket_block():
            q2 = query(name)

        assert q2 is q1

        with dnspython_resolver_socket_block():
            ip = socket.gethostbyname(name)
            assert ip == "127.0.0.1"

        restore_system_resolver()
        assert socket.gethostbyname == orig_gethostbyname
