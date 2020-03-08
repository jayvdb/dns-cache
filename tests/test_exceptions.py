"""Tests for caching exceptions."""
from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import MX, A
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
    dnspython_resolver_socket_block,
)

from tests.test_upstream import TestCache


class TestCache(TestCache):

    cache_cls = Cache
    resolver_cls = ExceptionCachingResolver

    def test_no_nameservers(self):
        name = "al.fr."

        resolver = self.get_test_resolver()

        with self.assertRaises(NoNameservers):
            resolver.query(name)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoNameservers):
                resolver.query(name)

    def test_nxdomain(self):
        missing_name = "invalid.invalid."

        resolver = self.get_test_resolver()

        e_qnames = e_responses = None
        with self.assertRaises(NXDOMAIN) as e:
            resolver.query(missing_name)

        if not hasattr(e, "qnames"):
            e = e.exception
        e_qnames, e_responses = _get_nxdomain_exception_values(e)
        assert e_qnames and e_responses

        assert len(resolver.cache.data) == 1

        name = from_text(missing_name)
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
                resolver.query(missing_name)

            if not hasattr(e, "qnames"):
                e = e.exception
            assert e_qnames, e_responses == _get_nxdomain_exception_values(e)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NXDOMAIN):
                resolver.query(missing_name)

        with self.assertRaises(NXDOMAIN):
            resolver.query(missing_name)

        assert len(resolver.cache.data) == 1

    def test_no_answer(self):
        name = "www.google.com"

        resolver = self.get_test_resolver()
        resolver.flags = 0

        with self.assertRaises(NoAnswer):
            resolver.query(name, MX, tcp=True)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoAnswer):
                resolver.query(name, MX, tcp=True)


class TestLRUCache(TestCache):

    cache_cls = LRUCache
