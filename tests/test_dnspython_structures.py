import unittest

from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A

from dns_cache.dnspython import (
    create_rdata,
    create_simple_rrset,
    create_answer,
)


class TestDataStructures(unittest.TestCase):
    def test_create_A(self):
        assert create_rdata("127.0.0.1", A, IN)
        rdata = create_rdata("127.0.0.1")
        assert rdata
        assert rdata.address == "127.0.0.1"

    def test_create_simple_rrset_dot(self):
        rrset = create_simple_rrset("localhost.", "127.0.0.1")
        assert rrset
        assert rrset.name == from_text("localhost.")

    def test_create_simple_rrset(self):
        rrset = create_simple_rrset("localhost", "127.0.0.1")
        assert rrset
        assert rrset.name == from_text("localhost.")

    def test_create_answer_dot(self):
        rrset = create_simple_rrset("localhost.", "127.0.0.1")
        answer = create_answer("localhost.", rrset)
        assert answer
        assert answer.response
        assert answer.response.question
        assert answer.response.answer

        assert answer.response.question[0].name == from_text("localhost.")

    def test_create_answer(self):
        rrset = create_simple_rrset("localhost", "127.0.0.1")
        answer = create_answer("localhost", rrset)
        assert answer
        assert answer.response
        assert answer.response.question
        assert answer.response.answer

        assert answer.response.question[0].name == from_text("localhost.")
