# dns-cache

`dns-cache` is a Python client side DNS caching framework utilising
[`dnspython`](https://github.com/rthalley/dnspython) v1.15+ for DNS
and supports various local key stores, and provides caching of lookup failures,
and configurable expiration of cached responses.

Some reasons to use a client side cache include:
- processing data containing many repeated invalid domains,
- running a local DNS caching service is not practical or appropriate,
- adding reporting of DNS activity performed within a job.

## Installation

The recommended way to install `dns-cache` is by using pip as follows:

`pip install dns-cache`

## Getting started

To quickly benefit from client side dns-caching in your existing application, install the system resolver.

```python
import dns_cache
import requests

dns_cache.override_system_resolver()

for i in range(10):
     requests.get('http://www.coala.io/')
```

If you have a fast dns proxy, 10 requests will possibly show no performance improvement.
Even 100 may not perform better in this contrived example.

However when many parts of a system are performing lookups on the same DNS records, or where
sessions are being closed and new ones created and need to access the same DNS records,
the difference becomes more noticable, especially in jobs which takes hours to run.

For long running jobs, use the `min_ttl` argument to increase the default if 5 minutes isnt sufficient.
It can be set to `dns_cache.NO_EXPIRY` for a ttl of one week, which is not recommended except when
accompanied with custom cache expiration logic.

## Key stores

Multiple key stores are supported, and their dependencies need to added separately as required.

1. `pickle` and [`pickle4`](https://github.com/moreati/pickle4) backport: `dns_cache.pickle.PickableCache`
2. [`diskcache`](https://github.com/grantjenks/python-diskcache): `dns_cache.diskcache.DiskCache`
3. [`stash.py`](https://github.com/fuzeman/stash.py/): `dns_cache.stash.StashCache`
4. [`sqlitedict`](https://github.com/RaRe-Technologies/sqlitedict): `dns_cache.sqlitedict.SqliteDictCache`
5. [`disk_dict`](https://github.com/AWNystrom/DiskDict): `dns_cache.disk_dict.DiskDictCache` (Python 2.7 only)

`stash.py` support uses `pickle` or `jsonpickle` on Python 3, however only `jsonpickle` works on Python 2.7.

## Caching additions

The following classes can be used separately or together.

1. `dns_cache.resolver.AggressiveCachingResolver`: indexes all qnames in the response, increasing the number of keys,
   but reducing the number of requests and cached responses when several related records are requested, such as a HTTP redirect
   from www.foo.com to foo.com (or vis versa) where one is a CNAME point to the other.
2. `dns_cache.resolver.ExceptionCachingResolver`: caches lookup failures.

**Note:** `dns_cache.override_system_resolver()` can be used to install a custom `resolver` or `cache`, which may
be derived from the above classes or your own implementation from scratch.

## Similar projects

Python:
1. [`velocity`](https://github.com/s0md3v/velocity) is a lighter weight approach, with a [`serious bug`](https://github.com/s0md3v/velocity/issues/2)
2. [`dnsplug`](https://github.com/nresare/dnsplug), unfortunately not available on PyPI.

Other:
1. [`dnscache`](https://github.com/rs/dnscache) (Go)
2. [`native-dns-cache`](https://github.com/tjfontaine/native-dns-cache) (Node)
