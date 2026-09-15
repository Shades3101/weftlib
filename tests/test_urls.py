"""Normalization: two references to one page must collapse to one string."""

from __future__ import annotations

import pytest

from webspec.safety import host_of, normalize_url, root_url, url_hash


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://Example.COM/Path", "https://example.com/Path"),
        ("https://www.acme.com/", "https://acme.com/"),
        ("https://example.com:443/x", "https://example.com/x"),
        ("http://example.com:80/x", "http://example.com/x"),
        ("https://example.com/about/", "https://example.com/about"),
        ("https://example.com/about/index.html", "https://example.com/about"),
        ("https://example.com/page#section", "https://example.com/page"),
        ("example.com/x", "https://example.com/x"),
    ],
)
def test_normalization(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_tracking_params_stripped_but_real_ones_kept() -> None:
    assert (
        normalize_url("https://example.com/p?utm_source=x&id=7&fbclid=abc")
        == "https://example.com/p?id=7"
    )


def test_query_order_does_not_matter() -> None:
    assert normalize_url("https://e.com/?b=2&a=1") == normalize_url("https://e.com/?a=1&b=2")


def test_www_kept_on_a_bare_two_label_host() -> None:
    """`www.com` is a real domain; stripping it would break the host."""
    assert normalize_url("https://www.com/") == "https://www.com/"


def test_unparseable_input_is_returned_not_raised() -> None:
    """Callers treat a bad URL as something to skip. The safety guard, not the
    normalizer, is what refuses to fetch it."""
    assert normalize_url("https://[oops/") == "https://[oops/"
    assert normalize_url("") == ""


def test_hash_is_stable_across_equivalent_forms() -> None:
    assert url_hash("https://www.example.com/a/") == url_hash("HTTPS://example.com/a")


def test_host_and_root() -> None:
    assert host_of("https://www.example.com/deep/path?x=1") == "example.com"
    assert root_url("https://www.example.com/deep/path") == "https://example.com"
    assert host_of("not a url at all") is None or isinstance(host_of("not a url at all"), str)
