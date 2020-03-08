from __future__ import absolute_import

import os.path

from stash import Stash
from stash.algorithms.core.base import Algorithm

from dns.resolver import Cache, LRUCache

from .key_transform import key_decode, key_encode


class AlgorithmNone(Algorithm):
    __key__ = "none"

    def compact(self, *args, **kwargs):
        pass

    def prime(self, *args, **kwargs):
        pass


class StashCacheBase(object):
    def __init__(
        self,
        filename=None,
        archive=None,
        algorithm=AlgorithmNone,
        serializer="pickle:///?protocol=4",
        cache="memory:///",
        *args,
        **kwargs
    ):
        # serializer='jsonpickle:///' also works
        assert filename or archive
        super(StashCacheBase, self).__init__(*args, **kwargs)

        if not archive:
            # https://github.com/fuzeman/stash.py/issues/2
            filename = os.path.relpath(filename)
            archive = "sqlite://../{}?table=dns".format(filename)
        elif not archive.startswith("memory:") and archive.find("?") == -1:
            archive += "?table=dns"

        self.data = Stash(
            archive,
            algorithm,
            serializer,
            cache,
            key_transform=(key_encode, key_decode),
        )


class StashCache(StashCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(StashCache, self).__init__(*args, **kwargs)


class StashLRUCache(StashCacheBase, LRUCache):
    def __init__(self, *args, **kwargs):
        super(StashLRUCache, self).__init__(*args, **kwargs)
