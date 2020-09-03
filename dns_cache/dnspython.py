from dns.message import make_query, make_response

from dns.name import from_text, Name
from dns.rdata import get_rdata_class
from dns.rdataclass import IN
from dns.rdatatype import A
from dns.rrset import RRset
from dns.resolver import Answer

try:
    from dns.message import ANSWER
except ImportError:  # pragma: no cover
    ANSWER = 1

try:  # pragma: no cover
    from dns.rdataclass import RdataClass
    from dns.rdatatype import RdataType
except ImportError:  # pragma: no cover
    class FakeMake():
        @staticmethod
        def make(text):
            return text

    RdataClass = RdataType = FakeMake


def create_rdata(address, rdtype=A, rdclass=IN):
    cls = get_rdata_class(rdclass=rdclass, rdtype=rdtype)
    rdata = cls(rdclass=rdclass, rdtype=rdtype, address=address)
    return rdata


def create_simple_rrset(name, address, rdtype=A, rdclass=IN):
    if not isinstance(name, Name):
        name = from_text(name)

    rdata = create_rdata(rdclass=rdclass, rdtype=rdtype, address=address)
    rrset = RRset(name, rdclass, rdtype)
    rrset.add(rdata)
    return rrset


# Use dns.message.from_text/from_file for more complex data loading
def create_answer(name, rrset):
    rdtype = rrset.rdtype
    rdclass = rrset.rdclass

    if not isinstance(name, Name):
        name = from_text(name)

    query = make_query(name, rdtype, rdclass)
    response = make_response(query)
    response.answer = [rrset]
    response.index = {(ANSWER, name, rdclass, rdtype, 0, None): rrset}
    response.find_rrset(
        response.answer, name, rdclass=rdclass, rdtype=rdtype)

    rdtype = RdataType.make(rdtype)
    rdclass = RdataClass.make(rdclass)

    answer = Answer(name, rdtype, rdclass, response)
    return answer
