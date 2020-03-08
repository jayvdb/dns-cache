import time
from contextlib import contextmanager

from dns.exception import DNSException
from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A
from dns.resolver import NXDOMAIN, Answer, Resolver

import dns_cache.expiration

try:
    from types import StringTypes
except ImportError:  # pragma: no cover
    StringTypes = tuple([str])


def _get_dnspython_version():
    from dns.version import MAJOR, MINOR

    return (MAJOR, MINOR)


def _socket_factory_blocker(*args, **kwargs):
    raise AssertionError("_socket_factory_blocker invoked")


@contextmanager
def dnspython_resolver_socket_block():
    import dns.resolver

    real_query_socket_factory = dns.resolver.dns.query.socket_factory
    dns.resolver.dns.query.socket_factory = _socket_factory_blocker
    try:
        yield
    finally:
        dns.resolver.dns.query.socket_factory = real_query_socket_factory


class AggressiveCachingResolver(Resolver):
    def query(self, qname, rdtype=A, rdclass=IN, **kwargs):
        assert self.cache

        answer = super(AggressiveCachingResolver, self).query(
            qname, rdtype, rdclass, **kwargs
        )
        # Stuff extra responses into the cache
        raise_on_no_answer = kwargs.get("raise_on_no_answer", True)
        rrsets = answer.response.answer
        assert not raise_on_no_answer or rrsets

        for rrset in rrsets:
            self.cache.put((rrset.name, rrset.rdtype, rrset.rdclass), answer)
        return answer


class NXAnswer(Answer):
    def __init__(self, *args, **kwargs):
        super(NXAnswer, self).__init__(*args, **kwargs)
        self.expiration += dns_cache.expiration.MIN_TTL


def _get_nxdomain_exception_values(e):  # pragma: no cover
    if _get_dnspython_version() >= (1, 16):
        return e.qnames(), e.responses()
    else:
        return e.kwargs["qnames"], e.kwargs["responses"]


class ExceptionCachingResolver(Resolver):
    def query(self, qname, rdtype=A, rdclass=IN, **kwargs):
        assert self.cache

        if isinstance(qname, StringTypes):
            qname = from_text(qname)

        answer = self.cache.get((qname, rdtype, rdclass))
        if answer is not None:
            if isinstance(answer, NXAnswer):
                raise NXDOMAIN(qnames=[qname], responses={qname: answer.response})
            elif isinstance(answer, DNSException):
                raise answer

        try:
            return super(ExceptionCachingResolver, self).query(
                qname, rdtype, rdclass, **kwargs
            )
        except NXDOMAIN as e:
            qnames, responses = _get_nxdomain_exception_values(e)
            for _qname, response in responses.items():
                answer = NXAnswer(
                    _qname, rdtype, rdclass, response, raise_on_no_answer=False
                )
                self.cache.put((_qname, rdtype, rdclass), answer)

            raise
        except DNSException as e:
            now = time.time()
            e.expiration = now + dns_cache.expiration.MIN_TTL
            self.cache.put((qname, rdtype, rdclass), e)
            raise
