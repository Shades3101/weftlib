"""SearXNG — a self-hosted metasearch engine.

The reason it matters here is not that it is free. It is that from a sandbox's
point of view it is a **single host**: a JARVIS tool declaring
``network_hosts=("searxng",)`` gets results aggregated from many engines while
its egress allowlist stays one entry long. Allowlisting Google, Bing, Brave and
the rest individually would be a far wider grant for the same capability.

Two operational notes that will otherwise cost an afternoon:

1. **JSON output is disabled by default.** Add ``json`` to ``search.formats``
   in the instance's ``settings.yml`` or every request returns HTML.
2. **The instance is on a private address**, which the SSRF guard rejects by
   design. Pass its hostname in ``internal_allowlist`` — see
   :func:`webspec.safety.validate_url_shape`.

At volume, remember SearXNG scrapes upstream engines. It inherits their rate
limiting; it does not escape it.
"""

from __future__ import annotations

from typing import Any

from webspec.platforms._shared import (
    DEFAULT_USER_AGENT,
    ParseError,
    json_body,
    require_ok,
)
from webspec.ports.dto import HttpRequest, HttpResponse, SearchHit, SearchRequest, SearchResponse

PROVIDER = "searxng"

#: SearXNG's own freshness buckets. It has no arbitrary day range, so a request
#: is mapped to the narrowest bucket that still contains it.
_TIME_RANGES = ((1, "day"), (7, "week"), (31, "month"), (366, "year"))


def _time_range(freshness_days: int | None) -> str | None:
    if freshness_days is None:
        return None
    for limit, name in _TIME_RANGES:
        if freshness_days <= limit:
            return name
    return None


def search_request(
    request: SearchRequest,
    *,
    base_url: str,
    categories: str = "general",
) -> HttpRequest:
    """Build a query against a SearXNG instance.

    ``base_url`` is the instance root, e.g. ``http://searxng:8080``.
    """
    params: dict[str, str] = {
        "q": request.query,
        "format": "json",
        "categories": categories,
        "language": request.language or "all",
    }
    if request.country_code:
        # SearXNG expresses locale as language-REGION on the language field.
        params["language"] = f"{request.language or 'en'}-{request.country_code.upper()}"
    time_range = _time_range(request.freshness_days)
    if time_range:
        params["time_range"] = time_range

    return HttpRequest(
        url=f"{base_url.rstrip('/')}/search",
        params=params,
        headers={"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT},
    )


def parse_search(response: HttpResponse, request: SearchRequest) -> SearchResponse:
    """Parse a SearXNG JSON response.

    A 200 carrying HTML means ``json`` is missing from the instance's
    ``search.formats``. That is reported as a configuration error rather than
    as an empty result set, because an empty result set is what a caller would
    otherwise silently believe forever.
    """
    require_ok(response.status, what="SearXNG")

    if response.content_type.startswith("text/html"):
        raise ParseError(
            "SearXNG returned HTML, not JSON: add 'json' to search.formats "
            "in the instance's settings.yml"
        )

    payload = json_body(response.body, what="SearXNG")
    if not isinstance(payload, dict):
        raise ParseError("SearXNG response was not an object")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ParseError("SearXNG response had no results array")

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
                snippet=item.get("content") or None,
                rank=rank,
                provider=PROVIDER,
                raw=_slim(item),
            )
        )

    return SearchResponse(request=request, hits=hits, provider=PROVIDER)


def _slim(item: dict[str, Any]) -> dict[str, Any]:
    """Keep the few raw fields worth having; drop the rest.

    SearXNG echoes a lot per result. Storing all of it inflates every cached
    response for fields nothing reads.
    """
    return {
        key: item[key]
        for key in ("engine", "engines", "score", "category", "publishedDate")
        if key in item
    }
