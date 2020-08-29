"""Tests for dnspython and its builtin cache."""
import os
import socket
import sys
import time
import unittest

from dns.exception import SyntaxError as DNSSyntaxError
from dns.exception import Timeout
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
    Resolver,
    _getaddrinfo,
    override_system_resolver,
)

from dns_cache.block import (
    _SocketBlockedError,
    dnspython_resolver_socket_block,
)
from dns_cache.resolver import DNSPYTHON_2

NAMESERVER = os.getenv("NAMESERVER", "8.8.8.8")
WINDOWS = sys.platform == "win32"


def compare_response(a, b):
    # dnspython Answer class does not implement __eq__
    # and sometimes even the following fails.
    try:
        assert a.__dict__ == b.__dict__
    except AttributeError as e:
        assert str(e) == "rdclass"
        raise unittest.SkipTest("Encountered bug in dnspython __eq__")


def get_test_resolver(cls=Resolver, nameserver=NAMESERVER, **kwargs):
    resolver = cls(configure=False, **kwargs)
    try:
        if sys.platform == "win32":
            resolver.read_registry()
        else:
            resolver.read_resolv_conf("/etc/resolv.conf")
    except Exception:
        pass

    resolver.nameservers = [nameserver]

    override_system_resolver(resolver)

    assert socket.getaddrinfo is _getaddrinfo

    return resolver


class TestSocketBlock(unittest.TestCase):
    def test_class(self):
        assert isinstance(_SocketBlockedError(), AssertionError)

    def test_socket_block(self):
        "Verify the socket block logic works" ""
        resolver = get_test_resolver()

        with dnspython_resolver_socket_block():
            with self.assertRaises(_SocketBlockedError) as cm:
                resolver.query("first.attempt.invalid.")
            self.assertEqual(str(cm.exception), "_socket_factory_blocker invoked")

        if not DNSPYTHON_2:
            return

        with dnspython_resolver_socket_block():
            with self.assertRaises(_SocketBlockedError) as cm:
                resolver.resolve("first.attempt.invalid.")
            self.assertEqual(str(cm.exception), "_socket_factory_blocker invoked")


class TestCache(unittest.TestCase):

    resolver_cls = Resolver
    cache_cls = Cache
    expiration = 60 * 5

    def get_test_resolver(self, nameserver=NAMESERVER):
        resolver = get_test_resolver(self.resolver_cls, nameserver)
        resolver.cache = self.cache_cls()

        assert len(resolver.cache.data) == 0

        return resolver

    def _flush_cache(self, resolver):
        if DNSPYTHON_2:
            resolver.cache.flush()
            return

        # Avoid a bug in LRUCache on dnspython < 2
        if len(resolver.cache.data):
            for key in list(resolver.cache.data):
                resolver.cache.flush(key)

    def test_hit_a(self):
        valid_name = "api.github.com"

        resolver = self.get_test_resolver(nameserver="8.8.8.8")

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        q1 = query(valid_name)

        assert len(resolver.cache.data) == 1
        name = from_text(valid_name)

        assert (name, A, IN) in resolver.cache.data
        assert resolver.cache.get((name, A, IN))

        with dnspython_resolver_socket_block():
            q2 = query(valid_name)

        assert q2 is q1

        now = time.time()
        assert q1.expiration < now + self.expiration + 1

        with dnspython_resolver_socket_block():
            ip = socket.gethostbyname(valid_name)
            assert ip

    def test_hit_cname(self):
        cname = "www.coala.io"
        a = "coala.io"

        resolver = self.get_test_resolver("8.8.8.8")

        q1 = resolver.query(cname)
        assert len(resolver.cache.data) == 1

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

        assert len(resolver.cache.data) == 1

        assert q2 is q1

        with dnspython_resolver_socket_block():
            ip = socket.gethostbyname(cname)

        assert ip == "46.101.245.76"

        # override_system_resolver is broken on Windows
        # https://github.com/rthalley/dnspython/issues/416
        if WINDOWS:
            return

        with self.assertRaises(socket.gaierror):
            with dnspython_resolver_socket_block():
                socket.gethostbyname(a)

        ip = socket.gethostbyname(a)
        assert ip == "46.101.245.76"

    def test_no_nameservers(self, expected_extra=0):
        name = "al.fr."
        # Other examples which trigger this are
        # 'hi.my.', 'www.mandrivalinux.com', 'www.myopenid.com', 'd.cd.' and 'al.fr'

        resolver = self.get_test_resolver()
        resolver.lifetime = 5

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        try:
            query(name)
        except Timeout:
            raise unittest.SkipTest("Timeout occurred")
        except NoNameservers:
            pass

        assert len(resolver.cache.data) == expected_extra

        try:
            query(name, tcp=True)
        except Timeout:
            raise unittest.SkipTest("Timeout occurred")
        except NoNameservers:
            pass

        assert len(resolver.cache.data) == expected_extra

        return resolver

    def test_syntax_error(self):
        name = ".ekit.com"

        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with self.assertRaises(DNSSyntaxError):
            query(name)

        assert len(resolver.cache.data) == 0

    def test_nxdomain(self, expected_extra=0):
        missing_name = "invalid.invalid."

        expected_cache_count = expected_extra + (1 if DNSPYTHON_2 else 0)

        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        try:
            query(missing_name)
        except NXDOMAIN:
            pass
        else:
            raise unittest.SkipTest("DNS hijacked")

        with self.assertRaises(NXDOMAIN):
            query(missing_name)

        assert len(resolver.cache.data) == expected_cache_count

        self._flush_cache(resolver)

        with self.assertRaises(NXDOMAIN):
            query(missing_name, tcp=True)

        assert len(resolver.cache.data) == expected_cache_count

        return resolver

    def test_no_answer(self, expected_extra=0):
        name = "www.google.com"

        expected_cache_count = expected_extra + (1 if DNSPYTHON_2 else 0)

        resolver = self.get_test_resolver()
        resolver.flags = 0

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with self.assertRaises(NoAnswer):
            try:
                query(name, MX, tcp=True)
            except (Timeout, NoNameservers):
                raise unittest.SkipTest("Another DNS exception occurred")

        assert len(resolver.cache.data) == expected_cache_count

        return resolver


class TestLRUCache(TestCache):

    cache_cls = LRUCache
