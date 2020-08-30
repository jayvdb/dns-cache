"""Tests for caching exceptions."""
import unittest

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A, ANY, MX
from dns.resolver import (
    NXDOMAIN,
    Cache,
    LRUCache,
    LRUCacheNode,
    NoAnswer,
    NoNameservers,
)

from dns_cache.resolver import (
    ExceptionCachingResolver,
    _get_nxdomain_exception_values,
)

from tests.test_upstream import (
    _get_nameserver_sample,
    _TestCacheBase,
    DNSPYTHON_2,
    dnspython_resolver_socket_block,
    expand,
    foreach,
)


@expand
class TestCache(_TestCacheBase, unittest.TestCase):

    cache_cls = Cache
    resolver_cls = ExceptionCachingResolver

    def test_no_nameservers(self):
        name = "al.fr."

        resolver = super(TestCache, self).test_no_nameservers(expected_extra=1)

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        resolver.lifetime = 1
        # Cache seed-ed by super class.

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoNameservers):
                query(name)

    def test_nxdomain(self):
        missing_name = "invalid.invalid."

        resolver, first_e = super(TestCache, self).test_nxdomain(
            expected_extra=1, ignore_any=True)

        name = from_text(missing_name)

        # Remove the core dnspython2 cache entry, which does not re-appear
        # below because the remainder of query use the dns-cache cache entry.
        if DNSPYTHON_2 and (name, ANY, IN) in resolver.cache.data:
            del resolver.cache.data[(name, ANY, IN)]

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        e_qnames, e_responses = _get_nxdomain_exception_values(first_e)

        assert len(resolver.cache.data) == 1

        assert (name, A, IN) in resolver.cache.data

        entry = resolver.cache.data[(name, A, IN)]
        assert entry is not None

        if isinstance(entry, LRUCacheNode):
            entry = entry.value

        answer = resolver.cache.get((name, A, IN))
        assert answer is not None

        assert answer is entry

        with dnspython_resolver_socket_block():
            with self.assertRaises(NXDOMAIN) as e:
                query(missing_name)

            if not hasattr(e, "qnames"):
                e = e.exception
            assert e_qnames, e_responses == _get_nxdomain_exception_values(e)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NXDOMAIN):
                query(missing_name)

        with self.assertRaises(NXDOMAIN):
            query(missing_name)

        assert len(resolver.cache.data) == 1

    def test_no_answer(self):
        name = "www.google.com"

        resolver = super(TestCache, self).test_no_answer(
            expected_extra=0 if DNSPYTHON_2 else 1)

        resolver.lifetime = 1
        # Cache seed-ed by super class.

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoAnswer):
                query(name, MX, tcp=True)

    @foreach(_get_nameserver_sample(rate=20))
    def test_hit_additional(self, nameserver=None):
        if not nameserver:
            raise unittest.SkipTest("unittest_expander leftover")

        super(TestCache, self)._test_hit_additional(nameserver)

    @foreach(_get_nameserver_sample(rate=20))
    def test_hit_authority(self, nameserver=None):
        if not nameserver:
            raise unittest.SkipTest("unittest_expander leftover")

        super(TestCache, self)._test_hit_authority(nameserver)


class TestLRUCache(TestCache):

    cache_cls = LRUCache
