"""Content extraction, challenge detection, and the escalation decision."""

from __future__ import annotations

from weft.extract import (
    EscalationReason,
    extract_content,
    is_challenge_page,
    should_escalate,
)
from weft.ports import FetchedPage

REAL_PAGE = """
<html lang="en-GB">
  <head><title>  Acme Robotics  </title><style>.a{color:red}</style></head>
  <body>
    <script>analytics('pageview')</script>
    <h1>Acme Robotics</h1>
    <p>We build warehouse automation for mid-market logistics operators.</p>
    <noscript>Enable JavaScript</noscript>
  </body>
</html>
"""


def test_extracts_title_text_and_language() -> None:
    result = extract_content(REAL_PAGE)
    assert result.title == "Acme Robotics"
    assert result.language == "en"          # primary subtag only
    assert "warehouse automation" in result.text


def test_script_and_style_contribute_no_text() -> None:
    text = extract_content(REAL_PAGE).text
    assert "analytics" not in text
    assert "color:red" not in text
    assert "Enable JavaScript" not in text


def test_missing_title_and_lang_are_none_not_empty_string() -> None:
    result = extract_content("<html><body><p>hi</p></body></html>")
    assert result.title is None
    assert result.language is None


# --- challenge detection ----------------------------------------------------

def test_cloudflare_interstitial_detected() -> None:
    html = (
        "<html><head><title>Just a moment...</title></head>"
        "<body><div id='cf'>Ray ID: 8a1f</div>"
        "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate'></script></body></html>"
    )
    assert is_challenge_page(html)
    assert is_challenge_page(html.encode())


def test_ordinary_page_is_not_a_challenge() -> None:
    assert not is_challenge_page(REAL_PAGE)


def test_article_titled_access_denied_is_not_a_challenge() -> None:
    """A recognised title alone must not trip it — corroboration is required."""
    html = (
        "<html><head><title>Access Denied</title></head>"
        "<body><p>A history of HTTP 403 and what it means for API design.</p></body></html>"
    )
    assert not is_challenge_page(html)


# --- escalation -------------------------------------------------------------

def _page(**kw: object) -> FetchedPage:
    base: dict[str, object] = {
        "url": "https://e.com/",
        "final_url": "https://e.com/",
        "status_code": 200,
        "byte_size": 5000,
    }
    base.update(kw)
    return FetchedPage(**base)  # type: ignore[arg-type]


def test_good_page_does_not_escalate() -> None:
    assert not should_escalate(_page(text="x" * 5000))


def test_js_shell_escalates() -> None:
    verdict = should_escalate(_page(text="Loading...", byte_size=40_000))
    assert verdict.escalate
    assert verdict.reason is EscalationReason.JS_SHELL


def test_genuinely_tiny_page_does_not_escalate() -> None:
    """Short text in a small document is a short page, not a shell."""
    assert not should_escalate(_page(text="Under construction.", byte_size=300))


def test_challenge_escalates_even_with_a_2xx() -> None:
    html = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Ray ID: 1</body></html>"
    )
    verdict = should_escalate(_page(text="", html=html, byte_size=900))
    assert verdict.reason is EscalationReason.CHALLENGE


def test_honest_404_does_not_escalate() -> None:
    """A 404 is an answer. Paying a browser to confirm it is waste."""
    assert not should_escalate(_page(status_code=404, text="Not found", byte_size=500))


def test_transport_error_does_not_escalate() -> None:
    """A renderer does not fix a connection failure; retry policy owns that."""
    assert not should_escalate(_page(status_code=None, error="connection reset"))


def test_verdict_is_falsy_when_not_escalating() -> None:
    assert not should_escalate(_page(text="x" * 5000))
