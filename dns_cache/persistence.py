from lazyutils import delegate_to

class _DeserializeOnGetCacheBase(object):
    def __init__(
        self,
        filename,
        deserializer,
        *args,
        **kwargs
    ):
        assert deserializer
        super(_DeserializeOnGetCacheBase, self).__init__(*args, **kwargs)
        self._filename = filename
        self._deserializer = deserializer

    def get(self, key):
        if self._deserialize:
            self._deserialize()
            self._deserialize = None
        return super(_DeserializeOnGetCacheBase, self).get(key)

    def _deserialize(self):
        data = self._deserializer(self._filename)
        for entry in data:
            key = (entry.name, entry.rdtype, entry.rdclass)
            self.put(key, entry)


class _LayeredCache(object):
    # This is not designed perfectly.
    # It is a readonly 'front' cache, delegating to a normal cache,
    # intended primary to support the special case of HostsCache
    # handling /etc/hosts

    def __init__(self, read_only_cache, writable_cache):
        self._cache1 = read_only_cache
        self._cache2 = writable_cache

    def get(self, key):
        try:
            return self._cache1.get(key)
        except Exception:
            pass
        return self._cache2.get(key)

    put = delegate_to("_cache2")
    _maybe_clean = delegate_to("_cache2")
    flush = delegate_to("_cache2")
    set_max_size = delegate_to("_cache2")
    data = delegate_to("_cache2")
    __del__ = delegate_to("_cache2")
