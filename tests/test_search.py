from __future__ import annotations

import pytest
from conftest import response

from webspec.platforms import ParseError
from webspec.platforms.search import brave, searxng
from webspec.ports import SearchRequest

REQ = SearchRequest(query="b2b saas berlin", language="de", country_code="de", limit=2)


# --- SearXNG ----------------------------------------------------------------

def test_searxng_request_shape() -> None:
    request = searxng.search_request(REQ, base_url="http://searxng:8080/")
    assert request.url == "http://searxng:8080/search"
    assert request.params["format"] == "json"
    assert request.params["q"] == "b2b saas berlin"
    assert request.params["language"] == "de-DE"


def test_searxng_freshness_maps_to_buckets() -> None:
    """SearXNG has buckets, not day ranges; pick the narrowest that fits."""
    def bucket(days: int) -> str | None:
        req = SearchRequest(query="x", freshness_days=days)
        return searxng.search_request(req, base_url="http://s:8080").params.get("time_range")

    assert bucket(1) == "day"
    assert bucket(5) == "week"
    assert bucket(20) == "month"
    assert bucket(300) == "year"
    assert bucket(5000) is None      # older than a year: no filter at all


def test_searxng_parse_and_limit() -> None:
    payload = {
        "results": [
            {"url": f"https://e{i}.com", "title": f"t{i}", "content": f"s{i}", "engine": "google"}
            for i in range(5)
        ]
    }
    result = searxng.parse_search(response(payload), REQ)
    assert len(result.hits) == 2              # honours request.limit
    assert result.hits[0].rank == 1
    assert result.hits[0].provider == "searxng"
    assert result.hits[0].raw == {"engine": "google"}


def test_searxng_html_response_is_a_configuration_error_not_empty_results() -> None:
    """The failure mode that would otherwise look like 'no results', forever."""
    with pytest.raises(ParseError, match="search.formats"):
        searxng.parse_search(
            response("<html>results page</html>", content_type="text/html"), REQ
        )


def test_searxng_results_without_a_url_are_skipped() -> None:
    payload = {"results": [{"title": "no url"}, {"url": "https://ok.com", "title": "ok"}]}
    result = searxng.parse_search(response(payload), REQ)
    assert [hit.url for hit in result.hits] == ["https://ok.com"]


def test_searxng_missing_results_array_is_an_error() -> None:
    with pytest.raises(ParseError, match="results"):
        searxng.parse_search(response({"query": "x"}), REQ)


# --- Brave ------------------------------------------------------------------

def test_brave_request_carries_the_key_in_a_header() -> None:
    request = brave.search_request(REQ, api_key="secret")
    assert request.headers["X-Subscription-Token"] == "secret"
    assert "secret" not in request.url          # never in the URL, which gets logged


def test_brave_count_is_capped_at_the_api_maximum() -> None:
    request = brave.search_request(SearchRequest(query="x", limit=500), api_key="k")
    assert request.params["count"] == "20"


def test_brave_parse() -> None:
    payload = {
        "web": {
            "results": [
                {"url": "https://a.com", "title": "A", "description": "d",
                 "page_age": "2026-09-01T00:00:00Z"},
            ]
        }
    }
    result = brave.parse_search(response(payload), REQ)
    assert result.hits[0].url == "https://a.com"
    assert result.hits[0].published_at is not None


def test_brave_no_web_key_is_an_empty_answer_not_an_error() -> None:
    """Brave omits `web` when nothing matched. That is a real empty result."""
    result = brave.parse_search(response({"query": {}}), REQ)
    assert result.hits == []
    assert result.ok


def test_both_backends_return_the_same_shape() -> None:
    """The point of the ports: a caller swaps backends by changing an import."""
    a = searxng.parse_search(response({"results": [{"url": "https://x.com"}]}), REQ)
    b = brave.parse_search(response({"web": {"results": [{"url": "https://x.com"}]}}), REQ)
    assert type(a) is type(b)
    assert a.hits[0].url == b.hits[0].url
    assert a.provider != b.provider
