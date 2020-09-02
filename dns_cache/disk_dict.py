from __future__ import absolute_import

import jsonpickle

from dns.resolver import Cache

from .key_transform import StringKeyDictBase

from disk_dict import DiskDict


class DiskDict(StringKeyDictBase, DiskDict):  # pragma: no cover
    def __len__(self):
        return len(list(self.keys()))


class DiskDictCacheBase(object):  # pragma: no cover
    def __init__(
        self,
        directory,
        serializer=jsonpickle.dumps,
        deserializer=jsonpickle.loads,
        *args,
        **kwargs
    ):  # pragma: no cover
        super(DiskDictCacheBase, self).__init__(*args, **kwargs)
        self.data = DiskDict(
            location=directory, serializer=serializer, deserializer=deserializer
        )


class DiskDictCache(DiskDictCacheBase, Cache):  # pragma: no cover
    def __init__(self, *args, **kwargs):
        super(DiskDictCache, self).__init__(*args, **kwargs)
