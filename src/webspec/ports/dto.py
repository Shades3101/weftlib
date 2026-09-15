"""Neutral data types that cross the seam between webspec and its callers.

Every type here is provider-neutral and vendor-neutral on purpose: nothing
carries a particular API's response shape, so swapping a search backend or an
HTTP client never ripples outward.

Plain dataclasses, not pydantic. JARVIS wraps these in its own pydantic models
for its tool contracts and ClayHome in its own dataclasses; forcing a
validation library on both would be a dependency neither asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Requests and responses — the unit of work a caller executes
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class HttpRequest:
    """A description of a request. webspec builds these; it never sends them.

    ``timeout_seconds`` and ``max_bytes`` are advisory limits the caller is
    expected to enforce — webspec cannot, having no socket.
    """

    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout_seconds: float = 20.0
    max_bytes: int = 3_000_000

    def with_header(self, name: str, value: str) -> HttpRequest:
        """A copy carrying one more header. Frozen, so never mutated in place."""
        merged = dict(self.headers)
        merged[name] = value
        return HttpRequest(
            url=self.url,
            method=self.method,
            headers=merged,
            params=dict(self.params),
            body=self.body,
            timeout_seconds=self.timeout_seconds,
            max_bytes=self.max_bytes,
        )


@dataclass(slots=True)
class HttpResponse:
    """What a caller got back, handed to webspec for parsing."""

    url: str
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    final_url: str | None = None
    elapsed_ms: int | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def text(self, encoding: str = "utf-8") -> str:
        """Decode with replacement. A mis-declared charset is not worth an
        exception on a page we may still be able to read."""
        return self.body.decode(encoding, errors="replace")


# ---------------------------------------------------------------------------
# Fetched pages
# ---------------------------------------------------------------------------


class FetchMethod(StrEnum):
    """Which rung of the escalation ladder produced a page.

    Recorded rather than inferred so cost is attributable: a run that quietly
    started rendering every page in a browser should be visible in the data,
    not discovered in a bill.
    """

    HTTP = "http"
    READER = "reader"
    BROWSER = "browser"
    CACHE = "cache"


@dataclass(slots=True)
class FetchedPage:
    """A retrieved page and what is known about the retrieval.

    ``error`` being None is not sufficient for success — check :attr:`ok`,
    which also requires a 2xx. The two are separate because "we were blocked"
    and "there is nothing here" are different facts, and collapsing them is how
    a broken pipeline reports clean empty answers forever.
    """

    url: str
    final_url: str
    status_code: int | None = None
    content_type: str | None = None
    title: str | None = None
    text: str | None = None
    html: str | None = None
    language: str | None = None
    byte_size: int = 0
    response_time_ms: int | None = None
    fetched_at: datetime | None = None
    from_cache: bool = False
    method: FetchMethod = FetchMethod.HTTP
    error: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.status_code is not None
            and 200 <= self.status_code < 300
        )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class SearchRequest:
    """One query. Locale is first-class rather than an afterthought — the
    results for a query differ by language and country, and pretending
    otherwise silently returns one market's view of the world."""

    query: str
    language: str = "en"
    country_code: str | None = None
    limit: int = 10
    freshness_days: int | None = None
    category: str | None = None

    def cache_key(self) -> str:
        return "|".join(
            [
                self.query.strip().lower(),
                self.language,
                self.country_code or "-",
                str(self.limit),
                str(self.freshness_days or "-"),
            ]
        )


@dataclass(slots=True)
class SearchHit:
    url: str
    title: str | None = None
    snippet: str | None = None
    rank: int = 0
    language: str | None = None
    published_at: datetime | None = None
    provider: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResponse:
    request: SearchRequest
    hits: list[SearchHit]
    provider: str
    from_cache: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
