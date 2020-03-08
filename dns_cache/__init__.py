import atexit
import os
import os.path
import sys

from dns.resolver import override_system_resolver as upstream_override_system_resolver

from .expiration import _NO_EXPIRY as NO_EXPIRY
from .expiration import FIVE_MINS, MinExpirationCache, NoExpirationCache
from .pickle import PickableCache
from .resolver import AggressiveCachingResolver, ExceptionCachingResolver

__version__ = "0.2.0"


class Resolver(AggressiveCachingResolver, ExceptionCachingResolver):
    pass


class MinExpirationPickableCache(MinExpirationCache, PickableCache):
    pass


class NoExpirationPickableCache(NoExpirationCache, PickableCache):
    pass


def override_system_resolver(
    resolver=None, cache=None, directory=None, min_ttl=FIVE_MINS
):  # pragma: no cover
    if not cache:
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except TypeError:
                try:
                    os.makedirs(directory)
                except OSError:
                    pass

            filename = os.path.join(directory, "dns.pickle")
            if min_ttl == NO_EXPIRY:
                cache = MinExpirationPickableCache(filename=filename, min_ttl=min_ttl)
            else:
                cache = MinExpirationPickableCache(filename=filename, min_ttl=min_ttl)
        else:
            if min_ttl == NO_EXPIRY:
                cache = NoExpirationCache(min_ttl=min_ttl)
            else:
                cache = MinExpirationCache(min_ttl=min_ttl)

    if not resolver:
        resolver = Resolver(configure=False)
        try:
            if sys.platform == "win32":
                resolver.read_registry()
            else:
                resolver.read_resolv_conf("/etc/resolv.conf")
        except Exception:
            resolver.nameservers = ["8.8.8.8"]

        resolver.cache = cache

    upstream_override_system_resolver(resolver)

    if hasattr(cache, "__del__"):
        atexit.register(cache.__del__)

    return resolver
