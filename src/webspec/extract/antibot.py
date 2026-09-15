"""Telling a challenge page from a real one.

A Cloudflare interstitial returns markup and often a 2xx. Parsed naively it
looks like a page that simply has little on it, so a pipeline records a clean
empty answer and moves on — permanently, and silently. "We were blocked" and
"there is nothing here" are different facts and must not collapse into one.

The heuristics are deliberately narrow. A false positive costs a needless
escalation to an expensive rung; a false negative poisons stored results with
challenge text. Narrow wins.

The Jina/Cloudflare markers come from Agent-Reach ``channels/web.py``
(``_is_antibot_page``), MIT licensed.
"""

from __future__ import annotations

#: Only the head of the document is examined. A challenge page announces itself
#: immediately; scanning further finds phrases in ordinary prose.
SCAN_BYTES = 4096

_CHALLENGE_TITLES = (
    "just a moment...",
    "attention required! | cloudflare",
    "checking your browser",
    "access denied",
    "verifying you are human",
    "one moment, please",
)

_CHALLENGE_MARKERS = (
    "/cdn-cgi/challenge-platform/",
    "performing security verification",
    "enable javascript and cookies to continue",
    "ray id",
    "__cf_chl",
    "px-captcha",
    "datadome",
)


def is_challenge_page(body: bytes | str) -> bool:
    """Whether a response is a bot challenge rather than content.

    Requires a recognised title *and* a corroborating marker, so a blog post
    titled "Access Denied" is not mistaken for an interstitial.
    """
    if isinstance(body, bytes):
        sample = body[:SCAN_BYTES].decode("utf-8", errors="ignore")
    else:
        sample = body[:SCAN_BYTES]
    sample = sample.casefold()

    has_title = any(title in sample for title in _CHALLENGE_TITLES)
    has_marker = any(marker in sample for marker in _CHALLENGE_MARKERS)

    # Jina Reader reports an upstream challenge in its own preamble rather than
    # passing the interstitial through.
    jina_warning = "warning:" in sample and "requiring captcha" in sample

    return (has_title and has_marker) or jina_warning
