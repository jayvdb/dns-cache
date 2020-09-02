from __future__ import absolute_import

import os.path
from datetime import timedelta

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A, AAAA

from dns.resolver import Cache

from python_hosts import Hosts

from .dnspython import create_answer, create_simple_rrset
from .expiration import NoExpirationCacheBase

_year_in_seconds = timedelta(days=365).total_seconds()


def _convert_entries(entries, expiration=None):
    out_data = []

    for entry in entries:
        if entry.entry_type == "ipv4":
            rdtype = A
        elif entry.entry_type == "ipv6":
            rdtype = AAAA
        else:
            continue

        for name in entry.names:
            name = from_text(name)

            ip = entry.address
            rrset = create_simple_rrset(name, ip, rdtype, rdclass=IN)
            rrset.ttl = _year_in_seconds
            out_entry = create_answer(name, rrset)
            if expiration:
                out_entry.expiration = expiration

            out_data.append(out_entry)

    return out_data


def loads(filename="/etc/hosts"):
     hosts = Hosts(path=filename)
     hosts.populate_entries()
     mtime = os.path.getmtime(filename)
     expiration = mtime + _year_in_seconds
     dnspython_data = _convert_entries(hosts.entries, expiration)

     return dnspython_data


class _DeserializeOnGetCacheBase(object):
    def __init__(
        self,
        filename=None,
        serializer=None,
        deserializer=None,
        *args,
        **kwargs,
    ):
        assert filename and deserializer
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


class HostsCacheBase(_DeserializeOnGetCacheBase, NoExpirationCacheBase):
    def __init__(
        self,
        filename=None,
        serializer=None,
        deserializer=loads,
        *args,
        **kwargs,
    ):
        super(HostsCacheBase, self).__init__(
            filename=filename,
            serializer=serializer,
            deserializer=deserializer,
            *args,
            **kwargs)


class HostsCache(HostsCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(HostsCache, self).__init__(*args, **kwargs)
