import time

from dns.resolver import Cache, LRUCache

FIVE_MINS = 60 * 5
TEN_MINS = 60 * 10
SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_WEEK = SECONDS_PER_DAY * 7

_NO_EXPIRY = SECONDS_PER_WEEK

MIN_TTL = FIVE_MINS


class MinExpirationCacheBase(object):
    def __init__(self, min_ttl=None, *args, **kwargs):
        if not min_ttl:
            min_ttl = MIN_TTL
        super(MinExpirationCacheBase, self).__init__(*args, **kwargs)
        self.min_ttl = min_ttl

    def put(self, key, value):
        now = time.time()
        min_expiration = now + self.min_ttl
        if min_expiration > value.expiration:
            value.expiration = min_expiration
        super(MinExpirationCacheBase, self).put(key, value)


class NoExpirationCacheBase(MinExpirationCacheBase):
    def __init__(self, min_ttl=_NO_EXPIRY):
        super(NoExpirationCacheBase, self).__init__(min_ttl)

    def _maybe_clean(self):
        """Avoid the _maybe_clean phase of dns.resolver.Cache."""
        pass


class MinExpirationCache(MinExpirationCacheBase, Cache):
    def __init__(self, cleaning_interval=None, min_ttl=None, *args, **kwargs):
        if not min_ttl:
            min_ttl = MIN_TTL
        if not cleaning_interval:
            cleaning_interval = max(MIN_TTL, min_ttl)
        super(MinExpirationCache, self).__init__(
            cleaning_interval=cleaning_interval, min_ttl=min_ttl, *args, **kwargs
        )


class NoExpirationCache(NoExpirationCacheBase, Cache):
    pass


class MinExpirationLRUCache(MinExpirationCacheBase, LRUCache):
    pass


class NoExpirationLRUCache(NoExpirationCacheBase, LRUCache):
    pass
