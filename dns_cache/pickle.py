import collections
import os.path

try:
    import threading as _threading
except ImportError:  # pragma: no cover
    import dummy_threading as _threading

try:
    # Python 3 backport to Python 2.7
    from pickle4 import pickle as pickle
except ImportError:  # pragma: no cover
    import pickle

from dns.resolver import LRUCacheNode, Cache, LRUCache


class SelfPickle(object):
    def __init__(self, filename, *args, **kwargs):
        super(SelfPickle, self).__init__(*args, **kwargs)
        self.filename = filename
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                p = pickle.load(f)
            self.__dict__.update(p.__dict__)

    def __del__(self):
        with open(self.filename, "wb") as f:
            pickle.dump(self, f)
        self.data = None
        self.filename = None


class PickableCacheBase(SelfPickle):
    def __getstate__(self):
        odict = self.__dict__.copy()
        del odict["lock"]
        return odict

    def __setstate__(self, odict):
        self.lock = _threading.Lock()
        self.__dict__.update(odict)


class PickableLRUCacheBase(SelfPickle):
    def _flatten_lru(self):
        new = collections.OrderedDict()
        try:
            self.lock.acquire()
            node = self.sentinel.next
            while node != self.sentinel:
                new[node.key] = node.value
                node = node.next
        finally:
            self.lock.release()
        return new

    def __getstate__(self):
        odict = self.__dict__.copy()
        odict["data"] = self._flatten_lru()
        del odict["sentinel"]
        del odict["lock"]
        return odict

    def __setstate__(self, odict):
        self.lock = _threading.Lock()
        sentinel = odict["sentinel"] = LRUCacheNode(None, None)
        flattened_lru = odict["data"]
        try:
            flattened_lru = reversed(flattened_lru.items())
        except TypeError:  # pragma: no cover
            flattened_lru = flattened_lru.items()
        data = odict["data"] = {}
        for key, value in flattened_lru:
            # TODO: make more efficient
            node = LRUCacheNode(key, value)
            node.link_after(sentinel)
            data[node.key] = node
        self.__dict__.update(odict)


class PickableCache(PickableCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(PickableCache, self).__init__(*args, **kwargs)


class PickableLRUCache(PickableLRUCacheBase, LRUCache):
    def __init__(self, *args, **kwargs):
        super(PickableLRUCache, self).__init__(*args, **kwargs)
