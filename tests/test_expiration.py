"""Tests for overriding expiration."""
import datetime

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A

from freezegun import freeze_time

from dns_cache.expiration import (
    SECONDS_PER_WEEK,
    TEN_MINS,
    MinExpirationCache,
    MinExpirationLRUCache,
    NoExpirationCache,
)
from dns_cache.resolver import dnspython_resolver_socket_block

from tests.test_upstream import TestCache


class TestCache(TestCache):

    cache_cls = MinExpirationCache
    expiration = TEN_MINS

    def test_hit_a_expired(self):
        valid_name = "api.github.com"

        resolver = self.get_test_resolver("8.8.8.8")
        # Avoid the cleaning occurring instead of expiration
        if hasattr(resolver.cache, "next_cleaning"):
            resolver.cache.next_cleaning += TEN_MINS

        q1 = resolver.query(valid_name)
        assert len(resolver.cache.data) == 1
        name = from_text(valid_name)

        assert (name, A, IN) in resolver.cache.data
        assert resolver.cache.get((name, A, IN))

        assert len(resolver.cache.data) == 1

        with dnspython_resolver_socket_block():
            q2 = resolver.query(valid_name)

        assert q2.__dict__ == q1.__dict__

        with freeze_time(datetime.timedelta(seconds=self.expiration + 1)):
            assert not resolver.cache.get((name, A, IN))

        # LRU cache purges expired records in .get()
        if isinstance(resolver.cache, MinExpirationLRUCache):
            assert len(resolver.cache.data) == 0
        else:
            assert len(resolver.cache.data) == 1


class TestLRUCache(TestCache):

    cache_cls = MinExpirationLRUCache


class TestNoExpireCache(TestCache):

    cache_cls = NoExpirationCache
    expiration = SECONDS_PER_WEEK
