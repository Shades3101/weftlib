"""Brave Search API.

Included alongside SearXNG to prove the request/parse shape generalises to a
keyed commercial backend, and because Brave has a free tier — 2,000 queries a
month — which makes it a realistic fallback when a self-hosted instance is
down.

The key is passed in per call. webspec stores no credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from webspec.platforms._shared import DEFAULT_USER_AGENT, ParseError, json_body, require_ok
from webspec.ports.dto import HttpRequest, HttpResponse, SearchHit, SearchRequest, SearchResponse

PROVIDER = "brave"
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

#: Brave caps a page at 20 results regardless of what is asked for.
MAX_COUNT = 20

_FRESHNESS = ((1, "pd"), (7, "pw"), (31, "pm"), (366, "py"))


def search_request(request: SearchRequest, *, api_key: str) -> HttpRequest:
    params: dict[str, str] = {
        "q": request.query,
        "count": str(min(request.limit, MAX_COUNT)),
        "search_lang": request.language or "en",
    }
    if request.country_code:
        params["country"] = request.country_code.upper()
    if request.freshness_days is not None:
        for limit, code in _FRESHNESS:
            if request.freshness_days <= limit:
                params["freshness"] = code
                break

    return HttpRequest(
        url=ENDPOINT,
        params=params,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )


def parse_search(response: HttpResponse, request: SearchRequest) -> SearchResponse:
    require_ok(response.status, what="Brave Search")
    payload = json_body(response.body, what="Brave Search")
    if not isinstance(payload, dict):
        raise ParseError("Brave Search response was not an object")

    web = payload.get("web")
    results = (web or {}).get("results") if isinstance(web, dict) else None
    if not isinstance(results, list):
        # Brave omits `web` entirely for a query with no web results, which is
        # an empty answer rather than a malformed one.
        return SearchResponse(request=request, hits=[], provider=PROVIDER)

    hits: list[SearchHit] = []
    for rank, item in enumerate(results[: request.limit], start=1):
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        hits.append(
            SearchHit(
                url=str(url),
                title=item.get("title") or None,
                snippet=item.get("description") or None,
                rank=rank,
                published_at=_date(item.get("page_age")),
                provider=PROVIDER,
            )
        )

    return SearchResponse(request=request, hits=hits, provider=PROVIDER)


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
