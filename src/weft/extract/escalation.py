"""When to climb the fetch ladder — and when not to.

The ladder:

======  ==========================================  ================
 Rung    Method                                      Relative cost
======  ==========================================  ================
 1       Plain HTTP                                  1x
 1.5     Reader service (e.g. ``r.jina.ai``)         ~10x, third party
 2       Headless browser                            ~100x
======  ==========================================  ================

Escalation must be a decision, not a habit. A pipeline that renders every page
in a browser works fine in testing and is ruinous at volume, and the damage is
invisible because the results look correct. So the decision lives here, as one
pure function over a fetched page, where it can be unit-tested and where a
change to it shows up in a diff.

The default is *not* to escalate. Escalation happens on a specific, recognised
signature — a JavaScript shell or a bot challenge — never on a generic failure.
A 404 is an answer; retrying it in a browser costs money to be told the same
thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from weft.extract.antibot import is_challenge_page
from weft.ports.dto import FetchedPage

#: Below this many readable characters, a 2xx HTML response is judged a shell
#: rather than a page. Chosen well under a short real article and well above a
#: loading screen's "Loading..." and nav furniture.
SHELL_TEXT_THRESHOLD = 200

#: A shell is also *large*: kilobytes of script delivering almost no text. A
#: genuinely tiny page is small in both, and should not be escalated.
SHELL_MIN_BYTES = 2_000


class EscalationReason(StrEnum):
    NONE = "none"
    JS_SHELL = "js_shell"
    CHALLENGE = "challenge"
    EMPTY_BODY = "empty_body"


@dataclass(slots=True, frozen=True)
class EscalationVerdict:
    escalate: bool
    reason: EscalationReason

    def __bool__(self) -> bool:
        return self.escalate


_NO = EscalationVerdict(False, EscalationReason.NONE)


def should_escalate(page: FetchedPage) -> EscalationVerdict:
    """Whether a higher rung is worth paying for.

    Returns no for anything that already answered — including an honest 404 or
    500. Those are facts about the resource, and a browser will reproduce them
    at a hundred times the price.
    """
    # A transport-level failure is not something a renderer fixes; the caller's
    # retry policy owns that.
    if page.error is not None:
        return _NO

    if page.status_code is None or not (200 <= page.status_code < 300):
        # One exception: some edges serve a challenge under a non-2xx status.
        if page.html and is_challenge_page(page.html):
            return EscalationVerdict(True, EscalationReason.CHALLENGE)
        return _NO

    if page.html and is_challenge_page(page.html):
        return EscalationVerdict(True, EscalationReason.CHALLENGE)

    text = (page.text or "").strip()
    if not text and page.byte_size > 0:
        return EscalationVerdict(True, EscalationReason.EMPTY_BODY)

    if len(text) < SHELL_TEXT_THRESHOLD and page.byte_size >= SHELL_MIN_BYTES:
        return EscalationVerdict(True, EscalationReason.JS_SHELL)

    return _NO
