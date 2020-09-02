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
from .persistence import _DeserializeOnGetCacheBase

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


def loads(filename=None):
     hosts = Hosts(path=filename)
     hosts.populate_entries()
     mtime = os.path.getmtime(hosts.hosts_path)
     expiration = mtime + _year_in_seconds
     dnspython_data = _convert_entries(hosts.entries, expiration)
     
     return dnspython_data


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
