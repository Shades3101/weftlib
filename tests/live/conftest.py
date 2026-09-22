"""Opt-in live-network tests.

The rest of the suite injects fixtures and fake resolvers, which is what makes
it fast and deterministic — and also what makes it blind. A fixture captured in
2026 keeps passing forever after an endpoint has changed shape underneath it.
These tests exist to catch exactly that, and they are the only tests here that
touch the network.

They are **skipped by default**. ``pyproject.toml`` sets ``-m "not live"``, so
a plain ``pytest`` run never reaches out. To run them::

    WEFT_LIVE=1 pytest -m live

Each is allowed to skip rather than fail when the dependency it needs is not
configured — a missing Brave key or SearXNG instance is a fact about the
environment, not a bug in weft. What they must never do is pass silently
without having made a request.

The transport below is deliberately :mod:`urllib` from the standard library.
weft claims to work with any HTTP client and to depend on none; a live suite
that reached for httpx would quietly weaken that claim into "works with the
client we tested".
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request

import pytest

from weft.ports import HttpRequest, HttpResponse

#: Live tests are opt-in twice over: the marker is deselected by default *and*
#: this variable must be set. Belt and braces, because a CI job that starts
#: silently hammering YouTube is a bad afternoon.
ENABLED = os.environ.get("WEFT_LIVE") == "1"

requires_network = pytest.mark.skipif(
    not ENABLED, reason="live network tests are opt-in: set WEFT_LIVE=1"
)


class UrllibTransport:
    """A :class:`~weft.ports.Transport` in a dozen lines of standard library.

    It satisfies the protocol by shape, without importing or subclassing
    anything from weft — which is the claim the protocol exists to make.

    Not suitable for production: no retries, no robots handling, no SSRF check.
    A real caller supplies those. That this stub is enough to exercise every
    platform module is the point.
    """

    def send(self, request: HttpRequest) -> HttpResponse:
        url = request.url
        if request.params:
            separator = "&" if urllib.parse.urlparse(url).query else "?"
            url = f"{url}{separator}{urllib.parse.urlencode(request.params)}"

        wire = urllib.request.Request(  # noqa: S310 - https enforced below
            url, data=request.body, headers=request.headers, method=request.method
        )
        if wire.type not in ("http", "https"):
            raise ValueError(f"refusing non-HTTP scheme: {wire.type}")

        try:
            with urllib.request.urlopen(wire, timeout=request.timeout_seconds) as raw:  # noqa: S310
                body = raw.read(request.max_bytes)
                return HttpResponse(
                    url=request.url,
                    status=raw.status,
                    body=body,
                    headers={k.lower(): v for k, v in raw.headers.items()},
                    final_url=raw.url,
                )
        except urllib.error.HTTPError as exc:
            # A 404 or 429 is a real answer about the endpoint's shape, so it is
            # returned for the test to judge rather than raised.
            return HttpResponse(
                url=request.url,
                status=exc.code,
                body=exc.read(),
                headers={k.lower(): v for k, v in exc.headers.items()},
                final_url=request.url,
            )
        except urllib.error.URLError as exc:
            pytest.skip(f"network unreachable: {exc.reason}")


@pytest.fixture(scope="session")
def http() -> UrllibTransport:
    return UrllibTransport()


@pytest.fixture(scope="session")
def brave_key() -> str:
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        pytest.skip("BRAVE_API_KEY is not set")
    return key


@pytest.fixture(scope="session")
def searxng_url() -> str:
    url = os.environ.get("WEFT_SEARXNG_URL")
    if not url:
        pytest.skip("WEFT_SEARXNG_URL is not set (e.g. http://localhost:8080)")
    return url.rstrip("/")
