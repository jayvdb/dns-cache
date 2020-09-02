import unittest

from dns.rdataclass import IN
from dns.rdatatype import A

from dns_cache.hosts import loads


class TestHostsSerializer(unittest.TestCase):
    def test_loads(self):
        data = loads()
        assert data
