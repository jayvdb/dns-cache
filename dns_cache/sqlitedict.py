from __future__ import absolute_import

from sqlitedict import SqliteDict

from dns.resolver import Cache, LRUCache

from .key_transform import StringKeyDictBase


class StringKeySqliteDict(StringKeyDictBase, SqliteDict):
    def __init__(self, *args, **kwargs):
        # Skip StringKeyDictBase
        SqliteDict.__init__(self, *args, **kwargs)


class SqliteDictCacheBase(object):

    # String keys are needed pending https://github.com/RaRe-Technologies/sqlitedict/pull/74

    def __init__(self, filename, autocommit=True, *args, **kwargs):
        super(SqliteDictCacheBase, self).__init__(*args, **kwargs)
        self.data = StringKeySqliteDict(filename, autocommit=autocommit)


class SqliteDictCache(SqliteDictCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(SqliteDictCache, self).__init__(*args, **kwargs)


class SqliteDictLRUCache(SqliteDictCacheBase, LRUCache):
    def __init__(self, *args, **kwargs):
        super(SqliteDictLRUCache, self).__init__(*args, **kwargs)
