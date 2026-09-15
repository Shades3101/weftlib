from __future__ import annotations

import pytest
from conftest import response

from webspec.platforms import reader
from webspec.safety import UnsafeURLError


def test_request_shape() -> None:
    request = reader.reader_request("https://acme.com/about")
    assert request.url == "https://r.jina.ai/https://acme.com/about"
    assert request.headers["X-Return-Format"] == "markdown"


def test_refuses_to_launder_an_ssrf_target() -> None:
    """Without this the caller's own guard only ever sees r.jina.ai, and would
    happily ask a third party to fetch the metadata endpoint for us."""
    for url in (
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8080/admin",
        "http://metadata.google.internal/",
        "file:///etc/passwd",
    ):
        with pytest.raises(UnsafeURLError):
            reader.reader_request(url)


def test_api_key_is_optional_and_not_retained() -> None:
    assert "Authorization" not in reader.reader_request("https://a.com").headers
    keyed = reader.reader_request("https://a.com", api_key="jina_x")
    assert keyed.headers["Authorization"] == "Bearer jina_x"
    assert "Authorization" not in reader.reader_request("https://a.com").headers


def test_parse_success() -> None:
    body = "Title: Acme — About\n\nWe build widgets for logistics operators.\n"
    page = reader.parse_reader(response(body, content_type="text/plain"), url="https://acme.com")
    assert page.ok
    assert page.title == "Acme — About"
    assert "widgets" in (page.text or "")
    assert page.method == "reader"


def test_upstream_challenge_is_an_error_not_an_empty_page() -> None:
    """Reader answers 200 with an explanation when the target blocked it."""
    body = "Warning: Target URL returned error 403: requiring captcha\n"
    page = reader.parse_reader(response(body, content_type="text/plain"), url="https://x.com")
    assert not page.ok
    assert page.error is not None and "challenge" in page.error


def test_reader_http_failure_is_recorded() -> None:
    page = reader.parse_reader(response("", status=429), url="https://x.com")
    assert not page.ok
    assert "429" in (page.error or "")
