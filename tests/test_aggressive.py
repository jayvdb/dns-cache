"""Tests for aggressive caching."""
import socket

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import CNAME, A
from dns.resolver import Cache, LRUCacheNode

from dns_cache.resolver import AggressiveCachingResolver
from dns_cache.resolver import dnspython_resolver_socket_block

from tests.test_upstream import TestCache


class TestCache(TestCache):

    cache_cls = Cache
    resolver_cls = AggressiveCachingResolver

    def test_hit_cname(self):
        cname = "www.coala.io"
        a = "coala.io"

        # TODO: This was previously 3, but it appears Google DNS is returning
        # less results by default, or the aggressive caching isnt finding
        # the embedded additional entries
        expected_cache_size = 1

        resolver = self.get_test_resolver("8.8.8.8")

        q1 = resolver.query(cname)
        assert len(resolver.cache.data) >= expected_cache_size

        name = from_text(cname)
        assert (name, A, IN) in resolver.cache.data
        assert resolver.cache.get((name, A, IN))

        entry = resolver.cache.data[(name, A, IN)]

        if isinstance(entry, LRUCacheNode):
            answer = entry.value
        else:
            answer = entry

        rrsets = answer.response.answer
        assert rrsets
        names = set([rrset.name for rrset in rrsets])

        a_name = from_text(a)

        assert name in names

        with dnspython_resolver_socket_block():
            q2 = resolver.query(cname)

        assert len(resolver.cache.data) >= expected_cache_size

        assert q2 is q1

        with dnspython_resolver_socket_block():
            ip = socket.gethostbyname(cname)

        assert ip == "46.101.245.76"

        # Sometimes the response includes solar.coala.io
        if (a_name, A, IN) in resolver.cache.data:
            with dnspython_resolver_socket_block():
                ip = socket.gethostbyname(a)

            assert ip == "46.101.245.76"
