import time

from dns.exception import DNSException
from dns.name import from_text
from dns.rdataclass import IN
from dns.rdatatype import A
from dns.resolver import NXDOMAIN, Answer, NoMetaqueries, Resolver
from dns.version import MAJOR as _MAJOR, MINOR as _MINOR

import dns_cache.expiration

from .block import dnspython_resolver_socket_block
from .dnspython import create_answer

try:
    from types import StringTypes
except ImportError:  # pragma: no cover
    StringTypes = tuple([str])

DNSPYTHON_2 = (_MAJOR, _MINOR) >= (2, 0)


def _get_dnspython_version():
    return (_MAJOR, _MINOR)


class AggressiveCachingResolver(Resolver):
    # dnspython 2 introduced resolve
    def resolve(self, qname, rdtype=A, rdclass=IN,
                tcp=False, source=None, raise_on_no_answer=True, source_port=0,
                lifetime=None, search=None):
        assert self.cache

        answer = super(AggressiveCachingResolver, self).resolve(
            qname, rdtype, rdclass, tcp, source,
            raise_on_no_answer, source_port, lifetime,
        )
        # Stuff extra responses into the cache
        rrsets = answer.response.answer
        assert not raise_on_no_answer or rrsets

        for rrset in rrsets:
            self.cache.put((rrset.name, rrset.rdtype, rrset.rdclass), answer)

        self._inject(answer.response.authority)
        self._inject(answer.response.additional)

        return answer

    if not DNSPYTHON_2:  # pragma: no cover
        del resolve

    def query(self, qname, rdtype=A, rdclass=IN, **kwargs):
        assert self.cache

        answer = super(AggressiveCachingResolver, self).query(
            qname, rdtype=rdtype, rdclass=rdclass, **kwargs
        )
        # Stuff extra responses into the cache
        raise_on_no_answer = kwargs.get("raise_on_no_answer", True)
        rrsets = answer.response.answer
        assert not raise_on_no_answer or rrsets

        if DNSPYTHON_2:  # pragma: no cover
            # Extra caching was already done in .resolve
            return answer

        for rrset in rrsets:
            self.cache.put((rrset.name, rrset.rdtype, rrset.rdclass), answer)

        self._inject(answer.response.authority)
        self._inject(answer.response.additional)

        return answer

    def _inject(self, rrsets):
        for rrset in rrsets:
            forged_answer = create_answer(rrset.name, rrset)
            rdtype = forged_answer.rdtype
            rdclass = forged_answer.rdclass
            if (rrset.name, rdtype, rdclass) not in self.cache.data:
                self.cache.put(
                    (rrset.name, rdtype, rdclass),
                    forged_answer
                )


class NXAnswer(Answer):
    def __init__(self, *args, **kwargs):
        if _get_dnspython_version() >= (2, 0):  # pragma: nocover
            kwargs.pop("raise_on_no_answer")
        super(NXAnswer, self).__init__(*args, **kwargs)
        self.expiration += dns_cache.expiration.MIN_TTL


def _get_nxdomain_exception_values(e):  # pragma: no cover
    if _get_dnspython_version() >= (1, 16):
        return e.qnames(), e.responses()
    else:
        return e.kwargs["qnames"], e.kwargs["responses"]


class ExceptionCachingResolver(Resolver):
    # dnspython 2 introduced resolve
    def resolve(self, qname, rdtype=A, rdclass=IN,
                tcp=False, source=None, raise_on_no_answer=True, source_port=0,
                lifetime=None, search=None):
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
            return super(ExceptionCachingResolver, self).resolve(
                qname, rdtype, rdclass, tcp, source,
                raise_on_no_answer, source_port, lifetime,
            )
        except NoMetaqueries:
            raise
        except DNSException as e:
            self._cache_exception(e, qname, rdtype, rdclass)
            raise

    if not DNSPYTHON_2:  # pragma: no cover
        del resolve

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

        if DNSPYTHON_2:  # pragma: no cover
            return super(ExceptionCachingResolver, self).query(
                qname, rdtype=rdtype, rdclass=rdclass, **kwargs
            )

        try:
            return super(ExceptionCachingResolver, self).query(
                qname, rdtype=rdtype, rdclass=rdclass, **kwargs
            )
        except NoMetaqueries:
            raise
        except DNSException as e:
            self._cache_exception(e, qname, rdtype, rdclass)
            raise

    def _cache_exception(self, e, qname, rdtype, rdclass):
        if isinstance(e, NXDOMAIN):
            qnames, responses = _get_nxdomain_exception_values(e)
            for _qname, response in responses.items():
                answer = NXAnswer(
                    _qname, rdtype, rdclass, response, raise_on_no_answer=False
                )
                self.cache.put((_qname, rdtype, rdclass), answer)

        else:
            now = time.time()
            e.expiration = now + dns_cache.expiration.MIN_TTL
            self.cache.put((qname, rdtype, rdclass), e)
