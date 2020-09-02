"""Tests for dnspython and its builtin cache."""
import functools
import os
import socket
import sys
import time
import unittest

from dns.exception import SyntaxError as DNSSyntaxError
from dns.exception import Timeout
from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A, AAAA, ANY, MX, NS
from dns.resolver import (
    NXDOMAIN,
    Answer,
    Cache,
    LRUCache,
    LRUCacheNode,
    NoAnswer,
    NoMetaqueries,
    NoNameservers,
    Resolver,
    _getaddrinfo,
    override_system_resolver,
    restore_system_resolver,
)

import pubdns

from unittest_expander import foreach, expand

from dns_cache.block import (
    _SocketBlockedError,
    dnspython_resolver_socket_block,
)
from dns_cache.resolver import (
    _get_nxdomain_exception_values,
    DNSPYTHON_2,
)

DEFAULT_NAMESERVER = "8.8.8.8"
NAMESERVER = os.getenv("NAMESERVER", None)
PORT = os.getenv("PORT", None)
WINDOWS = sys.platform == "win32"
PY2 = sys.version_info < (3, 0)

pd = pubdns.PubDNS()
orig_gethostbyname = socket.gethostbyname


def compare_response(a, b):
    # dnspython Answer class does not implement __eq__
    # and sometimes even the following fails.
    try:
        assert a.__dict__ == b.__dict__
    except AttributeError as e:
        assert str(e) == "rdclass"
        raise unittest.SkipTest("Encountered bug in dnspython __eq__")


def _get_nameservers():
    if NAMESERVER:
        return [NAMESERVER]

    data = pd.servers("US")
    return sorted([
        entry["server"] for entry in data
        if ":" not in entry["server"]
        and entry["server"] not in [
            "24.154.1.5",  # NoAnswer
            # NoNameserver:
            "97.64.136.6",
            "209.143.22.182",
            "216.240.32.71",
        ]
    ])


def _get_nameserver_sample(rate=5):
    return [
        nameserver
        for i, nameserver in enumerate(_get_nameservers())
        if not i % rate
    ]


get_nameservers = functools.partial(
    _get_nameserver_sample, rate=5 if PY2 else 4
)


def get_test_resolver(cls=Resolver, nameserver=None, **kwargs):
    resolver = cls(configure=False, **kwargs)
    try:
        if sys.platform == "win32":
            resolver.read_registry()
        else:
            resolver.read_resolv_conf("/etc/resolv.conf")
    except Exception:
        pass

    if not nameserver:
        if NAMESERVER:
            nameserver = NAMESERVER
        else:
            nameserver = DEFAULT_NAMESERVER

    resolver.nameservers = [nameserver]

    if PORT:
        resolver.nameserver_ports = {nameserver: PORT}

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


class _TestCacheBase(object):

    resolver_cls = Resolver
    cache_cls = Cache
    expiration = 60 * 5

    def tearDown(self):
        restore_system_resolver()
        assert socket.gethostbyname == orig_gethostbyname

    def get_test_resolver(self, nameserver=None):
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

    def _test_hit_additional(self, nameserver, aggressive=False):
        name = "cloudflare.com."

        resolver = self.get_test_resolver(nameserver)

        try:
            q1 = resolver.query(name, NS)
        except Timeout:
            raise unittest.SkipTest("Timeout occurred")

        if not q1.response.additional:
            raise unittest.SkipTest("no additional section")

        # Many US servers are returning an additional section with
        # only a single entry, as opposed to many as expected by the logic.
        if len(q1.response.additional) == 1:
            raise unittest.SkipTest("additional section has one entry")

        if aggressive:
            assert len(resolver.cache.data) > 1
        else:
            assert len(resolver.cache.data) == 1

        name = from_text(name)
        assert (name, NS, IN) in resolver.cache.data
        assert resolver.cache.get((name, NS, IN))

        entry = resolver.cache.data[(name, NS, IN)]

        if isinstance(entry, LRUCacheNode):
            answer = entry.value
        else:
            answer = entry

        rrsets = answer.response.answer
        assert rrsets
        assert len(rrsets) == 1
        names = set([rrset.name for rrset in rrsets])

        assert len(names) == 1
        rrset = [rrset for rrset in rrsets][0]

        assert len(answer.response.additional) > 1

        rrsets = answer.response.additional
        assert rrsets
        assert len(rrsets) > 1

        additional_names = sorted(set([
            rrset.name for rrset in rrsets
            if rrset.rdclass == IN
        ]))
        assert additional_names

        additional_a_names = sorted(set([
            rrset.name for rrset in rrsets
            if rrset.rdtype == A and rrset.rdclass == IN
        ]))

        if not additional_a_names:
            additional_aaaa_names = sorted(set([
                rrset.name for rrset in rrsets
                if rrset.rdtype == AAAA and rrset.rdclass == IN
            ]))
            if additional_aaaa_names:
                raise unittest.SkipTest("Additional only has AAAA")

        assert additional_a_names

        with dnspython_resolver_socket_block():
            q2 = resolver.query(name, NS)

        if aggressive:
            assert len(resolver.cache.data) > 1
        else:
            assert len(resolver.cache.data) == 1

        assert q2 is q1

        if aggressive:
            return resolver, additional_a_names

        with self.assertRaises(_SocketBlockedError):
            with dnspython_resolver_socket_block():
                ip = resolver.query(additional_a_names[0], A)

        return resolver

        # TODO use a socket function which gets NS records

    def _test_hit_authority(self, nameserver, aggressive=False):
        name = "a.gtld-servers.net."

        resolver = self.get_test_resolver(nameserver)

        try:
            q1 = resolver.query(name, A)
        except Timeout:
            raise unittest.SkipTest("Timeout occurred")

        if not q1.response.authority:
            raise unittest.SkipTest("no authority section")

        if aggressive:
            assert len(resolver.cache.data) >= 1
        else:
            assert len(resolver.cache.data) == 1

        name = from_text(name)
        assert (name, A, IN) in resolver.cache.data
        assert resolver.cache.get((name, A, IN))

        entry = resolver.cache.data[(name, A, IN)]

        if isinstance(entry, LRUCacheNode):
            answer = entry.value
        else:
            answer = entry

        assert answer == q1

        rrsets = answer.response.answer
        assert rrsets
        assert len(rrsets) == 1

        names = set([rrset.name for rrset in rrsets])

        assert len(names) == 1

        assert len(answer.response.authority) == 1

        rrsets = answer.response.authority

        assert rrsets
        assert len(rrsets) == 1

        authority_names = sorted(set([
            rrset.name for rrset in rrsets
            if rrset.rdtype == NS and rrset.rdclass == IN
        ]))

        with dnspython_resolver_socket_block():
            q2 = resolver.query(name, A)

        if aggressive:
            assert len(resolver.cache.data) >= 1
        else:
            assert len(resolver.cache.data) == 1

        assert q2 is q1

        if aggressive:
            return resolver, authority_names

        with self.assertRaises(_SocketBlockedError):
            with dnspython_resolver_socket_block():
                resolver.query(authority_names[0], NS)

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

    def test_nxdomain(self, expected_extra=0, long_expiry=False, ignore_any=False):
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

        e_qnames = e_responses = None
        with self.assertRaises(NXDOMAIN) as first_e:
            query(missing_name)

        if not hasattr(first_e, "qnames"):
            first_e = first_e.exception
        e_qnames, e_responses = _get_nxdomain_exception_values(first_e)
        assert e_qnames and e_responses

        name = from_text(missing_name)
        assert e_qnames == [name]

        assert len(resolver.cache.data) == expected_cache_count

        self._flush_cache(resolver)

        with self.assertRaises(NXDOMAIN):
            query(missing_name, A, tcp=True)

        assert len(resolver.cache.data) == expected_cache_count

        if DNSPYTHON_2:
            assert (name, ANY, IN) in resolver.cache.data
            entry = resolver.cache.data[(name, ANY, IN)]
            assert entry is not None

            if isinstance(entry, LRUCacheNode):
                entry = entry.value

            assert isinstance(entry, Answer)

        if expected_extra:
            assert (name, A, IN) in resolver.cache.data
        else:
            assert (name, A, IN) not in resolver.cache.data

        # While dnspython 2 creates a cache entry for ANY,
        # requests for ANY fail, and the cache entry persists
        with self.assertRaises(NoMetaqueries):
            query(missing_name, ANY)

        # The exception caching .resolve sets ignore_any becase it
        # fetches from the cache, which removes the cache entry unless
        # the expiration is high
        if DNSPYTHON_2 and not ignore_any:
            assert (name, ANY, IN) in resolver.cache.data
            entry = resolver.cache.data[(name, ANY, IN)]
            assert entry is not None

            if isinstance(entry, LRUCacheNode):
                entry = entry.value

            assert isinstance(entry, Answer)

        with self.assertRaises(NXDOMAIN):
            query(missing_name, A, tcp=True)

        # While dnspython 2 creates a cache entry for ANY, and it uses
        # that caching to response to A without network activity,
        # the cache entry expiries very quickly.  This appear to be
        # improved in dnspython 2.1dev.
        if not long_expiry:
            if DNSPYTHON_2:
                long_expiry = True

        if long_expiry:
            with self.assertRaises(NXDOMAIN):
                with dnspython_resolver_socket_block():
                    query(missing_name, A)

        # bailout because test_exceptions would fail the below assertion, as the
        # exception NODOMAIN will be raised even when the socket is blocked
        if expected_extra or long_expiry:
            return resolver, first_e

        with self.assertRaises(_SocketBlockedError):
            with dnspython_resolver_socket_block():
                query(missing_name, A)

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

    def test_miss_localhost(self):
        name = "localhost"

        assert socket.gethostbyname == orig_gethostbyname

        try:
            socket.gethostbyname(name)
        except Exception as e:
            raise unittest.SkipTest("gethostbyname: {}".format(e))

        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        with self.assertRaises(_SocketBlockedError):
            with dnspython_resolver_socket_block():
                query(name)

        with self.assertRaises((NXDOMAIN, NoAnswer)):
            query(name)


@expand
class TestCache(_TestCacheBase, unittest.TestCase):
    @foreach(get_nameservers())
    def test_hit_additional(self, nameserver=None):
        if not nameserver:
            raise unittest.SkipTest("unittest_expander leftover")

        self._test_hit_additional(nameserver)

    @foreach(get_nameservers())
    def test_hit_authority(self, nameserver=None):
        if not nameserver:
            raise unittest.SkipTest("unittest_expander leftover")

        self._test_hit_authority(nameserver)


class TestLRUCache(TestCache):

    cache_cls = LRUCache
