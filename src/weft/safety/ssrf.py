"""Outbound request safety: SSRF protection and URL validation.

URLs handled here originate from search results, fetched pages, and model
output — untrusted by definition. Without this guard a crafted URL can make a
worker read cloud instance metadata or reach a service on the internal network.

Extracted from ClayHome ``packages/core/net.py``, with one addition: legacy
IPv4 literal spellings are rejected at parse time rather than only after DNS
resolution (see :func:`_literal_ip`).

This module is the deliberate exception to the package's no-I/O rule. DNS
resolution *is* the check: a hostname that looks public can resolve to
``127.0.0.1``. :func:`validate_url_shape` needs no network and can be used
alone where a caller does its own resolution.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

#: Cloud instance-metadata endpoints. Blocked by address anyway, but named
#: explicitly so the intent is obvious and a test can assert on them.
BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "localhost",
        "localhost.localdomain",
    }
)

BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain")

ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})

MAX_URL_LENGTH = 2048


class UnsafeURLError(ValueError):
    """The URL must not be fetched.

    The message is safe to log. It is not safe to echo back to an end user
    verbatim: it can confirm whether an internal host exists.
    """


@dataclass(slots=True, frozen=True)
class ResolvedTarget:
    """A URL that passed every check, plus what its host resolved to."""

    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


def _literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse canonical *and* legacy IPv4 literal spellings, without DNS.

    ``ipaddress`` accepts only dotted-quad form, but the C resolver behind most
    HTTP clients accepts the whole ``inet_aton`` grammar: ``127.1``,
    ``2130706433``, ``0x7f000001`` and ``0177.0.0.1`` all reach 127.0.0.1, and
    ``0xA9FEA9FE`` reaches the cloud metadata address.

    Resolving these through DNS would catch them too, but only after a lookup,
    and only if the resolver behaves as expected. Rejecting them here fails
    closed and costs nothing. Returns None for a genuine hostname.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    # Imported inside the function, not at module scope. JARVIS bans a tool
    # from importing `socket` at all, and enforces it by parsing the source.
    # weft has no ambient authority to begin with — it owns no transport —
    # but a module-level import would make a reader check that claim rather
    # than see it. The cost is one dict lookup per malformed host.
    import socket

    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def is_public_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is publicly routable.

    IPv6 transition forms are unwrapped rather than trusted: an IPv4-mapped,
    6to4 or Teredo address can carry a private IPv4 target inside a v6 literal
    that every ``is_private`` check would otherwise call public.
    """
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return False
    if ip.is_reserved or ip.is_unspecified:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public_address(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            return is_public_address(ip.sixtofour)
        if ip.teredo is not None:
            return all(is_public_address(part) for part in ip.teredo)
    return True


def validate_url_shape(
    url: str,
    *,
    internal_allowlist: frozenset[str] = frozenset(),
) -> tuple[str, int]:
    """Checks that need no DNS. Returns ``(host, port)``.

    ``internal_allowlist`` names hosts that are permitted to be non-public —
    a self-hosted SearXNG on the Docker network, for instance. It relaxes
    *only* the destination checks. Scheme, credential and port rules always
    apply, so the exemption can never widen into "fetch anything".

    Pass explicit hostnames, never a blanket "allow private" flag: the point is
    that one known endpoint is reachable, not that the guard is off.
    """
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("URL is empty or too long.")

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise UnsafeURLError("URL could not be parsed.") from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Scheme '{scheme or 'none'}' is not allowed.")

    if parts.username or parts.password:
        raise UnsafeURLError("Credentials in URLs are not allowed.")

    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURLError("URL has no host.")

    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeURLError("URL has an invalid port.") from exc

    exempt = host in internal_allowlist
    if not exempt:
        if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
            raise UnsafeURLError(f"Host '{host}' is not a public destination.")
        if port not in ALLOWED_PORTS:
            raise UnsafeURLError(f"Port {port} is not allowed.")
        # A literal address skips DNS entirely, so it must be checked here.
        literal = _literal_ip(host)
        if literal is not None and not is_public_address(literal):
            raise UnsafeURLError(f"Address {host} is not publicly routable.")

    return host, port


def resolve_public_target(
    url: str,
    *,
    internal_allowlist: frozenset[str] = frozenset(),
    getaddrinfo: object = None,
) -> ResolvedTarget:
    """Full check: shape, then DNS, then *every* resolved address.

    One private answer among many is enough to abuse, so every address a host
    resolves to must be public — not merely the first.

    ``getaddrinfo`` is injectable so tests can simulate resolution without a
    network. It defaults to :func:`socket.getaddrinfo`.
    """
    import socket  # see _literal_ip for why this is not at module scope

    host, port = validate_url_shape(url, internal_allowlist=internal_allowlist)

    if host in internal_allowlist:
        return ResolvedTarget(url=url, host=host, port=port, addresses=())

    resolver = getaddrinfo if getaddrinfo is not None else socket.getaddrinfo
    try:
        infos = resolver(host, port, proto=socket.IPPROTO_TCP)  # type: ignore[operator]
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Host '{host}' could not be resolved.") from exc
    except OSError as exc:
        raise UnsafeURLError(f"Host '{host}' could not be resolved.") from exc

    addresses = tuple({info[4][0] for info in infos})
    if not addresses:
        raise UnsafeURLError(f"Host '{host}' resolved to no addresses.")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeURLError(f"Host '{host}' resolved to an invalid address.") from exc
        if not is_public_address(ip):
            raise UnsafeURLError(f"Host '{host}' resolves to non-public address {address}.")

    return ResolvedTarget(url=url, host=host, port=port, addresses=addresses)
