from __future__ import absolute_import

import os.path
import sys
from datetime import timedelta

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A, AAAA

from dns.resolver import Cache

from reconfigure.configs import HostsConfig

from .dnspython import create_answer, create_simple_rrset
from .expiration import NoExpirationCacheBase
from .persistence import _DeserializeOnGetCacheBase

_year_in_seconds = timedelta(days=365).total_seconds()

# References to https://en.wikipedia.org/wiki/Hosts_(file)
_WINDOWS_PATHS = [
    # Microsoft Windows NT, 2000, XP,[5] 2003, Vista, 2008, 7, 2012, 8, 10
    r"${SystemRoot}\System32\drivers\etc\hosts",
    # Microsoft Windows 95, 98, ME
    r"${WinDir}\hosts",
    # Microsoft Windows 3.1
    r"${WinDir}\HOSTS",
    # Symbian OS 6.1-9.0
    r"C:\system\data\hosts",
    # Symbian OS 9.1+
    r"C:\private\10000882\hosts",
]
_UNIX_PATHS = [
    # Unix, Unix-like, POSIX, Apple Macintosh Mac OS X 10.2 and newer,
    # Android, iOS 2.0 and newer
    "/etc/hosts",
    # openSUSE
    "/usr/etc/hosts",
]
_OTHER_PARTS = [
    # Plan 9
    "/lib/ndb/hosts",
    # BeOS
    "/boot/beos/etc/hosts",
    # Haiku
    "/boot/common/settings/network/hosts",
]


def guess_hosts_path():
    if sys.platform == "win32":
        possible_paths = _WINDOWS_PATHS + _UNIX_PATHS + _OTHER_PARTS
    else:
        possible_paths = _UNIX_PATHS + _OTHER_PARTS + _WINDOWS_PATHS

    for path in possible_paths:
        path = os.path.expandvars(os.path.expanduser(path))
        if os.path.exists(path):
            return path

    raise RuntimeError()


def _convert_entries(entries, expiration=None):
    out_data = []

    for entry in entries:
        if ":" in entry.address:
            rdtype = AAAA
        elif "." in entry.address:
            rdtype = A
        else:
            continue

        names = [entry.name] + [
            alias.name for alias in entry.aliases
        ]
        for name in names:
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
    if not filename:
        filename = guess_hosts_path()

    mtime = os.path.getmtime(filename)

    config = HostsConfig(path=filename)
    config.load()

    expiration = mtime + _year_in_seconds
    dnspython_data = _convert_entries(config.tree.hosts, expiration)

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
