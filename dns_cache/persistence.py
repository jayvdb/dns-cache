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
