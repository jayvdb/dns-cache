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
            # print("out_entry.expiration 1", out_entry.expiration)
            if expiration:
                out_entry.expiration = expiration
            # print("out_entry.expiration 2", out_entry.expiration)

            out_data.append(out_entry)

    return out_data


def loads(filename=None):
     hosts = Hosts(path=filename)
     hosts.populate_entries()
     mtime = os.path.getmtime(hosts.hosts_path)
     expiration = mtime + _year_in_seconds
     # print('file mtime', mtime, expiration)
     dnspython_data = _convert_entries(hosts.entries, expiration)
     
     return dnspython_data


class _DeserializeOnGetCacheBase(object):
    def __init__(
        self,
        filename,
        deserializer,
        *args,
        **kwargs
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
        filename,
        *args,
        **kwargs
    ):
        super(HostsCacheBase, self).__init__(
            *args,
            filename=filename,
            deserializer=loads,
            **kwargs)


class HostsCache(HostsCacheBase, Cache):
    def __init__(self, *args, **kwargs):
        super(HostsCache, self).__init__(*args, **kwargs)
