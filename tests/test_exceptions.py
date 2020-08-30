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
)

from tests.test_upstream import (
    DNSPYTHON_2,
    dnspython_resolver_socket_block,
    TestCache,
)


class TestCache(TestCache):

    cache_cls = Cache
    resolver_cls = ExceptionCachingResolver

    def test_no_nameservers(self):
        name = "al.fr."

        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with self.assertRaises(NoNameservers):
            query(name)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoNameservers):
                query(name)

    def test_nxdomain(self):
        missing_name = "invalid.invalid."

        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        e_qnames = e_responses = None
        with self.assertRaises(NXDOMAIN) as e:
            query(missing_name)

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

        resolver = self.get_test_resolver()
        resolver.flags = 0

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with self.assertRaises(NoAnswer):
            query(name, MX, tcp=True)

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            with self.assertRaises(NoAnswer):
                query(name, MX, tcp=True)


class TestLRUCache(TestCache):

    cache_cls = LRUCache
