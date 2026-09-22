"""How a caller hands a secret to a platform module.

weft owns no identity. It stores no token, refreshes nothing, and knows about
no user account — those belong to the consuming application, which already has
a secret store and an opinion about where credentials come from. What weft
needs is a *shape*: one agreed way for a caller to pass a secret into a request
builder, so that adding the first authenticated platform is not also a design
argument.

The shape is deliberately small. A credential knows how to place itself on an
:class:`~weft.ports.dto.HttpRequest` and nothing else:

    >>> from weft.ports import ApiKey
    >>> cred = ApiKey("X-Subscription-Token", "secret")
    >>> request = cred.apply(request)   # doctest: +SKIP

Three things this is not, each on purpose:

* **Not a token store.** There is no refresh, no expiry handling, no disk. A
  caller holding an expiring token refreshes it on its own side and passes the
  current value; weft would have to perform I/O to do otherwise, which is the
  one thing this library will not do.
* **Not a secret type.** :func:`repr` is redacted as a courtesy against a
  credential landing in a log line, but a redacted repr is not a security
  control. The value is a plain string in memory and the caller's secret
  handling is what actually protects it.
* **Not required.** weft's platforms are keyless today. ``auth`` is optional
  everywhere it appears, and a keyless platform ignores it entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from weft.ports.dto import HttpRequest

__all__ = ["ApiKey", "BearerToken", "Credential", "QueryKey"]


@runtime_checkable
class Credential(Protocol):
    """Something that can authenticate a request.

    A :class:`typing.Protocol` rather than a base class so a caller's existing
    credential object qualifies by shape. An application that already has a
    ``SigningKey`` with an ``apply`` method does not need to wrap it, or to
    import weft in the module that defines it.
    """

    def apply(self, request: HttpRequest) -> HttpRequest:
        """Return a copy of ``request`` carrying this credential.

        Implementations must not mutate ``request`` — :class:`HttpRequest` is
        frozen precisely so a credential cannot leak onto a shared instance.
        """
        ...


def _redacted(name: str, value: str) -> str:
    """A repr that names the credential without disclosing it.

    The length is included because the most common credential bug by far is a
    value that is empty or still has a trailing newline from a shell here-doc,
    and neither is visible in a fully masked repr.
    """
    return f"{name}(len={len(value)}, value=***)"


@dataclass(slots=True, frozen=True)
class ApiKey:
    """A key sent as a request header.

    The header name is explicit rather than defaulted because there is no
    convention worth guessing at: Brave wants ``X-Subscription-Token``, others
    want ``X-API-Key`` or ``Authorization``. A wrong default fails as a 401
    with no hint about which name was expected.
    """

    header: str
    value: str

    def apply(self, request: HttpRequest) -> HttpRequest:
        return request.with_header(self.header, self.value)

    def __repr__(self) -> str:
        return _redacted(f"ApiKey({self.header!r}", self.value) + ")"


@dataclass(slots=True, frozen=True)
class BearerToken:
    """An OAuth-style bearer token sent as ``Authorization: Bearer …``.

    weft does not run the OAuth flow that produced this token and will not.
    Obtaining and refreshing it is the caller's job; this type only carries the
    result to a request.
    """

    value: str

    def apply(self, request: HttpRequest) -> HttpRequest:
        return request.with_header("Authorization", f"Bearer {self.value}")

    def __repr__(self) -> str:
        return _redacted("BearerToken(", self.value) + ")"


@dataclass(slots=True, frozen=True)
class QueryKey:
    """A key passed as a query parameter, as several older APIs still require.

    Worth avoiding where a header is offered: query strings are logged by
    proxies and servers as a matter of routine, so this leaks a secret into
    places a header does not. It exists because some endpoints accept nothing
    else, not because it is a reasonable design.
    """

    param: str
    value: str

    def apply(self, request: HttpRequest) -> HttpRequest:
        merged = dict(request.params)
        merged[self.param] = self.value
        return HttpRequest(
            url=request.url,
            method=request.method,
            headers=dict(request.headers),
            params=merged,
            body=request.body,
            timeout_seconds=request.timeout_seconds,
            max_bytes=request.max_bytes,
        )

    def __repr__(self) -> str:
        return _redacted(f"QueryKey({self.param!r}", self.value) + ")"
