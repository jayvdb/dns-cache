from __future__ import absolute_import

import os.path
import pickle
import shutil
import socket
import sys
import unittest

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A

try:
    import apsw
except ImportError:
    apsw = None

from dns_cache.hosts import HostsCache
from dns_cache.diskcache import DiskCache, DiskLRUCache
from dns_cache.pickle import PickableCache, PickableCacheBase, PickableLRUCache
from dns_cache.sqlitedict import SqliteDictCache, SqliteDictLRUCache
from dns_cache.stash import StashCache, StashLRUCache

from tests.test_upstream import (
    compare_response,
    DNSPYTHON_2,
    dnspython_resolver_socket_block,
    get_test_resolver,
    orig_gethostbyname,
    restore_system_resolver,
)

try:
    # Python 3 backport to Python 2.7
    from pickle4 import pickle as pickle4
except ImportError:
    pickle4 = None

try:
    from dns_cache.disk_dict import DiskDictCache
except ImportError:
    DiskDictCache = None

PY2 = sys.version_info[0] == 2


def seed_cache(resolver):
    if DNSPYTHON_2:
        query = resolver.resolve
    else:
        query = resolver.query

    q1 = query("github.com.")
    assert len(resolver.cache.data) > 0

    q2 = query("bitbucket.org.")

    assert len(resolver.cache.data) > 1
    assert q2 != q1

    name = from_text("github.com.")
    assert resolver.cache.get((name, A, IN))

    q2 = query("github.com.")
    assert len(resolver.cache.data) > 1
    compare_response(q1, q2)


class _TestPersistentCacheBase(object):
    cache_cls = None
    kwargs = {}

    def tearDown(self):
        restore_system_resolver()
        assert socket.gethostbyname == orig_gethostbyname

    def is_jsonpickle(self):
        serializer = self.kwargs.get("serializer", None)
        if hasattr(serializer, "startswith") and serializer.startswith(
            "jsonpickle:///"
        ):
            return True

    def is_memory(self):
        return self.kwargs.get("archive", "") == "memory:///"

    def get_test_resolver(self):
        using_json_pickle = self.is_jsonpickle()
        using_memory = self.is_memory()
        archive = self.kwargs.get("archive", "")

        if (
            issubclass(self.cache_cls, (StashCache, StashLRUCache))
            and pickle.HIGHEST_PROTOCOL < 3
        ):
            if not using_memory and not using_json_pickle:
                raise unittest.SkipTest(
                    "stash pickle:// requires protocol 3; highest is %d"
                    % pickle.HIGHEST_PROTOCOL
                )

        if PY2 and archive.startswith("apsw:"):
            raise unittest.SkipTest("Unknown error in apsw: support on Python 2")

        resolver = get_test_resolver()

        resolver.cache = self.cache_cls(**self.kwargs)

        return resolver

    def seed_cache(self, resolver):
        seed_cache(resolver)


class TestPickling(_TestPersistentCacheBase, unittest.TestCase):

    cache_cls = PickableCache
    kwargs = {"filename": os.path.abspath("dns.pickle")}
    load_on_get = False
    query_name = "github.com."

    def remove_cache(self, required=True):
        filename = self.kwargs.get("filename", None)
        directory = self.kwargs.get("directory", None)
        using_json_pickle = self.is_jsonpickle()
        archive = self.kwargs.get("archive", None)

        if archive:
            start = archive.find(":///") + 4
            end = archive.find("?")
            if end == -1:
                end = len(archive)
            filename = archive[start:end]
            if using_json_pickle:
                assert filename.startswith("jsonpickle")
            if archive.startswith("memory:///"):
                assert not filename
            else:
                assert filename.endswith(".stash")

        if filename:
            remove_failed = False
            if required:
                assert os.path.exists(filename)
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except OSError:
                    remove_failed = True
            if required and not remove_failed:
                assert not os.path.exists(filename)

        if directory:
            remove_failed = False
            if required:
                assert os.path.exists(directory)
            if os.path.exists(directory):
                try:
                    shutil.rmtree(directory)
                except OSError:
                    remove_failed = True
            if required and not remove_failed:
                assert not os.path.exists(directory)

    def test_empty_cache(self):
        self.remove_cache(required=False)
        resolver = self.get_test_resolver()
        using_json_pickle = self.is_jsonpickle()

        if not using_json_pickle:
            archive = self.kwargs.get("archive", "")
            if archive.startswith("apsw:"):
                raise unittest.SkipTest("Unknown error in apsw:// with pickle://")

        if isinstance(resolver.cache, PickableLRUCache):
            raise unittest.SkipTest("Unknown error in PickableLRUCache")

        if isinstance(resolver.cache, PickableCacheBase):
            resolver.cache.flush()

        assert len(resolver.cache.data) == 0

        # Check persistance empty cache
        if isinstance(resolver.cache, StashCache):
            resolver.cache.data.prime()
            resolver.cache.data.compact()
            resolver.cache.data.flush()
        else:
            if hasattr(resolver.cache, "__del__"):
                resolver.cache.__del__()
            else:
                resolver.cache = None

        resolver = self.get_test_resolver()

        assert len(resolver.cache.data) == 0

        self.remove_cache()

    def test_reload(self):
        self.remove_cache(required=False)
        resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        using_memory = self.is_memory()

        assert len(resolver.cache.data) == 0

        self.seed_cache(resolver)

        q1 = query(self.query_name)
        assert q1

        if using_memory:
            pass
        elif hasattr(resolver.cache, "__del__"):
            resolver.cache.__del__()
        else:
            resolver.cache = None

        if not using_memory:
            resolver = self.get_test_resolver()

        if DNSPYTHON_2:
            query = resolver.resolve
        else:
            query = resolver.query

        if not self.load_on_get:
            assert len(resolver.cache.data) > 0

        with dnspython_resolver_socket_block():
            q2 = query(self.query_name)

        assert len(resolver.cache.data) > 0

        if DNSPYTHON_2 and isinstance(resolver.cache, (StashCache, StashLRUCache)):
            # The reponse and rrset have slightly different values, which
            # means the loading from the cache distorts the value somehow
            # TODO: remove this and nail down differences
            q1.response = None
            q1.rrset = None

            q2.response = None
            q2.rrset = None

        if isinstance(resolver.cache, HostsCache):
            q1.expiration = None
            q2.expiration = None

            q1.response.id = q2.response.id

        compare_response(q1, q2)

        self.remove_cache()


class TestLRUPickling(TestPickling):

    cache_cls = PickableLRUCache
    kwargs = {"filename": os.path.abspath("dns-lru.pickle")}


class TestHosts(TestPickling):

    cache_cls = HostsCache
    kwargs = {"filename": None}
    query_name = "localhost."
    load_on_get = True
    seed_cache = lambda self, resolver: None


class TestStashMemory(TestPickling):

    cache_cls = StashCache
    kwargs = {"archive": "memory:///"}


class TestStashPickle3(TestStashMemory):

    kwargs = {
        "filename": os.path.abspath("pickle3.stash"),
        "serializer": "pickle:///?protocol=3",
    }


class TestLRUStashPickle3(TestStashMemory):

    cache_cls = StashLRUCache
    kwargs = {
        "filename": os.path.abspath("pickle3-lru.stash"),
        "serializer": "pickle:///?protocol=3",
    }


class TestStashPickle4(TestStashMemory):

    kwargs = {
        "filename": os.path.abspath("pickle4.stash"),
        "serializer": "pickle:///?protocol=4",
    }


class TestStashJsonPickle(TestStashMemory):

    kwargs = {
        "filename": os.path.abspath("jsonpickle.stash"),
        "serializer": "jsonpickle:///",
    }


class TestLRUStashJsonPickle(TestStashMemory):

    cache_cls = StashLRUCache
    kwargs = {
        "filename": os.path.abspath("jsonpickle-lru.stash"),
        "serializer": "jsonpickle:///",
    }


if apsw:

    class TestStashPickleApsw(TestStashMemory):

        kwargs = {
            "archive": "apsw:///pickle-apsw.stash?table=dns",
            "serializer": "pickle:///?protocol=4",
        }

    class TestStashJsonPickleApsw(TestStashMemory):

        kwargs = {
            "archive": "apsw:///jsonpickle-apsw.stash?table=dns",
            "serializer": "jsonpickle:///",
        }


class TestStashJsonPickleArchive(TestStashMemory):

    kwargs = {
        "archive": "sqlite:///jsonpickle-archive.stash",
        "serializer": "jsonpickle:///",
    }


class TestStashJsonPickleTablename(TestStashMemory):

    kwargs = {
        "archive": "sqlite:///jsonpickle-table.stash?table=dns",
        "serializer": "jsonpickle:///",
    }


class TestSqliteDict(TestPickling):

    cache_cls = SqliteDictCache
    kwargs = {"filename": os.path.abspath("dns.sqlite")}


class TestLRUSqliteDict(TestPickling):

    cache_cls = SqliteDictLRUCache
    kwargs = {"filename": os.path.abspath("dns-lru.sqlite")}


class TestDiskCache(TestPickling):

    cache_cls = DiskCache
    kwargs = {"directory": os.path.abspath("disk-cache-dir")}


class TestLRUDiskCache(TestPickling):

    cache_cls = DiskLRUCache
    kwargs = {"directory": os.path.abspath("disk-cache-lru-dir")}


if DiskDictCache:

    class TestDiskDictJsonPickleCache(TestPickling):

        cache_cls = DiskDictCache
        kwargs = {"directory": os.path.abspath("diskdict-cache-dir")}

    class TestDiskDictPickle4Cache(TestPickling):

        cache_cls = DiskDictCache
        kwargs = {
            "directory": os.path.abspath("diskdict-cache-dir"),
            "serializer": pickle4.dumps,
            "deserializer": pickle4.loads,
        }
