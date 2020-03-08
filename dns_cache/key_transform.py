from dns.name import from_text


def key_encode(key):
    name, rdtype, rdclass = key
    return "{}!{}!{}".format(name, rdtype, rdclass)


def key_decode(key):
    name, rdtype, rdclass = key.rsplit("!", 2)
    return (from_text(name, None), int(rdtype), int(rdclass))


class KeyTransformDictBase(object):
    def __contains__(self, key):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        return super(KeyTransformDictBase, self).__contains__(key)

    def __setitem__(self, key, value):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        super(KeyTransformDictBase, self).__setitem__(key, value)

    def get(self, key, default=None):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        return super(KeyTransformDictBase, self).get(key, default)

    def put(self, key, value):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        try:
            return super(KeyTransformDictBase, self).put(key, value)
        except AttributeError:
            return super(KeyTransformDictBase, self).__setitem__(key, value)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        return super(KeyTransformDictBase, self).__getitem__(key)

    def __delitem__(self, key):
        if isinstance(key, tuple):
            key = self.key_encode(key)
        super(KeyTransformDictBase, self).__delitem__(key)

    def keys(self):
        return (key_decode(key) for key in super(KeyTransformDictBase, self).keys())

    def items(self):
        for key, value in super(KeyTransformDictBase, self).items():
            yield key_decode(key), value


class StringKeyDictBase(KeyTransformDictBase):
    key_encode = staticmethod(key_encode)
    key_decode = staticmethod(key_decode)


class StringKeyDict(StringKeyDictBase, dict):
    pass
