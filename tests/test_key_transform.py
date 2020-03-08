import unittest

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A

from dns_cache.key_transform import StringKeyDict, key_decode, key_encode


class TestKeyEncoding(unittest.TestCase):
    def test_encode(self):
        assert key_encode(("foo.bar.", A, IN)) == "foo.bar.!1!1"
        assert key_encode(("foo!bar.", A, IN)) == "foo!bar.!1!1"

    def test_decode(self):
        assert key_decode("foo.bar.!1!1") == (from_text("foo.bar."), A, IN)
        assert key_decode("foo!bar.!1!1") == (from_text("foo!bar."), A, IN)


class TestKeyTransformDict(unittest.TestCase):
    def test_basic(self):
        d = StringKeyDict()
        d[("foo.bar.", A, IN)] = "blah"
        assert d[("foo.bar.", A, IN)] == "blah"
        assert ("foo.bar.", A, IN) in d
        del d[("foo.bar.", A, IN)]
        assert len(d) == 0
        d.put(("foo.bar.", A, IN), "blah")
        assert d[("foo.bar.", A, IN)] == "blah"

    def test_keys(self):
        d = StringKeyDict()
        d[("foo.bar.", A, IN)] = "blah"
        d[("foo.baz.", A, IN)] = "blah"
        assert set(d.keys()) == set(
            [(from_text("foo.bar."), A, IN), (from_text("foo.baz."), A, IN)]
        )

    def test_items(self):
        d = StringKeyDict()
        d[("foo.bar.", A, IN)] = "blah"
        d[("foo.baz.", A, IN)] = "blah"
        assert set(d.items()) == set(
            [
                ((from_text("foo.bar."), A, IN), "blah"),
                ((from_text("foo.baz."), A, IN), "blah"),
            ]
        )
