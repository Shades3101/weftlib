"""The guard that decides what may be fetched at all.

These are the tests that matter most in the package: everything else returns a
wrong answer when it breaks, this returns your cloud credentials.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any, NoReturn

import pytest

from weft.safety import UnsafeURLError, resolve_public_target, validate_url_shape


def _resolver(*addresses: str) -> Callable[..., list[Any]]:
    """A fake getaddrinfo returning fixed addresses, so DNS never runs."""

    def fake(host: str, port: int, *args: Any, **kwargs: Any) -> list[Any]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (addr, port))
            for addr in addresses
        ]

    return fake


# --- literal addresses, rejected without DNS -------------------------------

@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",        # canonical loopback
        "127.1",            # inet_aton short form
        "2130706433",       # loopback as a single integer
        "0x7f000001",       # loopback in hex
        "0177.0.0.1",       # loopback in octal
        "0xA9FEA9FE",       # 169.254.169.254 — cloud metadata
        "169.254.169.254",  # link-local, the usual metadata address
        "10.0.0.1",         # RFC1918
        "192.168.1.1",      # RFC1918
        "172.16.0.1",       # RFC1918
        "0.0.0.0",          # unspecified
        "[::1]",            # IPv6 loopback
        "[::ffff:127.0.0.1]",   # IPv4-mapped loopback smuggled into v6
        "[2002:7f00:1::]",      # 6to4 wrapping 127.0.0.1
    ],
)
def test_private_literals_rejected(host: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_shape(f"http://{host}/")


def test_named_internal_hosts_rejected() -> None:
    for host in ("localhost", "metadata.google.internal", "foo.internal", "box.local"):
        with pytest.raises(UnsafeURLError):
            validate_url_shape(f"https://{host}/")


# --- shape rules ------------------------------------------------------------

def test_non_http_schemes_rejected() -> None:
    for url in ("file:///etc/passwd", "gopher://x.com/", "ftp://x.com/", "javascript:alert(1)"):
        with pytest.raises(UnsafeURLError):
            validate_url_shape(url)


def test_credentials_in_url_rejected() -> None:
    # `evil.test` is the real host here; the userinfo is a disguise.
    with pytest.raises(UnsafeURLError):
        validate_url_shape("https://example.com@evil.test/")


def test_unusual_ports_rejected() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_shape("http://example.com:22/")


def test_overlong_url_rejected() -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_shape("https://example.com/" + "a" * 3000)


def test_public_url_passes() -> None:
    assert validate_url_shape("https://example.com/path") == ("example.com", 443)


# --- DNS-stage checks -------------------------------------------------------

def test_public_hostname_resolving_privately_is_rejected() -> None:
    """The rebinding case: the name looks fine, the answer does not."""
    with pytest.raises(UnsafeURLError, match="non-public"):
        resolve_public_target(
            "https://totally-normal.example.com/",
            getaddrinfo=_resolver("127.0.0.1"),
        )


def test_one_private_answer_among_many_is_enough_to_reject() -> None:
    """A host that resolves to both is still abusable, so it must fail."""
    with pytest.raises(UnsafeURLError, match="non-public"):
        resolve_public_target(
            "https://mixed.example.com/",
            getaddrinfo=_resolver("93.184.216.34", "10.0.0.5"),
        )


def test_public_resolution_passes() -> None:
    target = resolve_public_target(
        "https://example.com/",
        getaddrinfo=_resolver("93.184.216.34"),
    )
    assert target.host == "example.com"
    assert target.addresses == ("93.184.216.34",)


def test_unresolvable_host_is_rejected() -> None:
    def boom(*args: Any, **kwargs: Any) -> NoReturn:
        raise socket.gaierror("nope")

    with pytest.raises(UnsafeURLError, match="could not be resolved"):
        resolve_public_target("https://nx.example.com/", getaddrinfo=boom)


# --- the internal-endpoint exemption ---------------------------------------

def test_exempt_host_may_be_internal() -> None:
    """A self-hosted SearXNG lives on a private address by definition."""
    host, port = validate_url_shape(
        "http://searxng:8080/search",
        internal_allowlist=frozenset({"searxng"}),
    )
    assert (host, port) == ("searxng", 8080)


def test_exemption_does_not_leak_to_other_hosts() -> None:
    """Naming one host must not switch the guard off for everything else."""
    with pytest.raises(UnsafeURLError):
        validate_url_shape(
            "http://127.0.0.1/",
            internal_allowlist=frozenset({"searxng"}),
        )
    with pytest.raises(UnsafeURLError):
        validate_url_shape(
            "http://metadata.google.internal/",
            internal_allowlist=frozenset({"searxng"}),
        )


def test_exemption_still_enforces_scheme_and_credentials() -> None:
    """The escape hatch relaxes the destination, never the rest."""
    with pytest.raises(UnsafeURLError):
        validate_url_shape("file:///etc/passwd", internal_allowlist=frozenset({"searxng"}))
    with pytest.raises(UnsafeURLError):
        validate_url_shape(
            "http://user:pw@searxng:8080/",
            internal_allowlist=frozenset({"searxng"}),
        )


def test_exempt_host_skips_dns_entirely() -> None:
    """A Docker service name does not resolve from outside the network."""
    def boom(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("DNS must not be attempted for an exempt host")

    target = resolve_public_target(
        "http://searxng:8080/search",
        internal_allowlist=frozenset({"searxng"}),
        getaddrinfo=boom,
    )
    assert target.addresses == ()
