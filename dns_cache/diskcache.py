from __future__ import absolute_import

import diskcache as dc

from dns.resolver import Cache, LRUCache


class DiskCacheBase(object):
    def __init__(self, directory, *args, **kwargs):
        super(DiskCacheBase, self).__init__(*args, **kwargs)
        self.data = dc.Cache(directory)


class DiskCache(DiskCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(DiskCache, self).__init__(*args, **kwargs)


class DiskLRUCache(DiskCacheBase, LRUCache):
    def __init__(self, *args, **kwargs):
        super(DiskLRUCache, self).__init__(*args, **kwargs)
