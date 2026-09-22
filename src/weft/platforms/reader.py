"""Jina Reader — rung 1.5 of the fetch ladder.

``https://r.jina.ai/<url>`` fetches a page server-side, renders its JavaScript,
and returns markdown. Keyless.

This is the rung that makes JARVIS viable. A JARVIS tool cannot drive a browser
— it reaches the network only through the egress-policed ``ctx.http`` — but
this is an ordinary HTTPS GET to one host, so a tool declaring
``network_hosts=("r.jina.ai",)`` gets JS-rendered content without leaving its
sandbox model.

**The target URL and the returned content pass through a third party.** That is
the whole mechanism, not an implementation detail. Never send a URL here that
is itself sensitive — an internal address, or one carrying a token in its query
string. The keyless tier is also rate-limited, so at volume this belongs behind
a browser, not in front of one.

Idea taken from Agent-Reach ``channels/web.py`` (MIT).
"""

from __future__ import annotations

from datetime import UTC, datetime

from weft.extract.antibot import is_challenge_page
from weft.platforms._shared import DEFAULT_USER_AGENT, ParseError
from weft.ports.dto import FetchedPage, FetchMethod, HttpRequest, HttpResponse
from weft.safety.ssrf import UnsafeURLError, validate_url_shape

ENDPOINT = "https://r.jina.ai"

#: The one host a caller needs to allow for this rung.
HOST = "r.jina.ai"


def reader_request(
    url: str,
    *,
    api_key: str | None = None,
    target_selector: str | None = None,
    timeout_seconds: float = 30.0,
) -> HttpRequest:
    """Build a Reader request for ``url``.

    The target is validated first. Without that check this function is an SSRF
    laundering service: the guard on the caller's own transport only sees
    ``r.jina.ai``, and would happily pass a request asking Jina to fetch
    ``http://169.254.169.254/`` on its behalf.

    An ``api_key`` raises the rate limit. weft does not hold one.
    """
    try:
        validate_url_shape(url)
    except UnsafeURLError as exc:
        raise UnsafeURLError(f"refusing to ask a reader service to fetch this URL: {exc}") from exc

    headers = {
        "Accept": "text/plain",
        "User-Agent": DEFAULT_USER_AGENT,
        # Ask for the main content rather than nav and footer furniture.
        "X-Return-Format": "markdown",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if target_selector:
        headers["X-Target-Selector"] = target_selector

    return HttpRequest(
        url=f"{ENDPOINT}/{url}",
        headers=headers,
        timeout_seconds=timeout_seconds,
    )


def parse_reader(response: HttpResponse, *, url: str) -> FetchedPage:
    """Turn a Reader response into a :class:`FetchedPage`.

    Reader answers 200 with an explanatory body when the *upstream* page was
    blocked, so a naive parse records a successful fetch of nothing. That case
    is detected and returned as an error, because "we were blocked" and "the
    page is empty" must not collapse into one fact.
    """
    now = datetime.now(UTC)
    text = response.text()

    if not response.ok:
        return FetchedPage(
            url=url,
            final_url=url,
            status_code=response.status,
            method=FetchMethod.READER,
            fetched_at=now,
            error=f"reader returned HTTP {response.status}",
        )

    if is_challenge_page(text):
        return FetchedPage(
            url=url,
            final_url=url,
            status_code=response.status,
            method=FetchMethod.READER,
            fetched_at=now,
            byte_size=len(response.body),
            error="upstream page was a bot challenge",
        )

    title = _title_of(text)
    return FetchedPage(
        url=url,
        final_url=response.final_url or url,
        status_code=response.status,
        content_type="text/markdown",
        title=title,
        text=text,
        byte_size=len(response.body),
        response_time_ms=response.elapsed_ms,
        fetched_at=now,
        method=FetchMethod.READER,
    )


def _title_of(markdown: str) -> str | None:
    """Reader prefixes its output with ``Title: ...``."""
    for line in markdown.splitlines()[:5]:
        if line.startswith("Title:"):
            return line[len("Title:") :].strip() or None
    return None


__all__ = ["ENDPOINT", "HOST", "ParseError", "parse_reader", "reader_request"]
