"""Turning fetched bytes into usable text, and judging what came back.

Includes the escalation decision — whether a page is worth re-fetching at a
more expensive rung — because that judgement is content analysis, and keeping
it here makes it testable without a network.
"""

from weft.extract.antibot import is_challenge_page
from weft.extract.escalation import (
    EscalationReason,
    EscalationVerdict,
    should_escalate,
)
from weft.extract.html import ExtractedContent, extract_content, visible_text_length

__all__ = [
    "EscalationReason",
    "EscalationVerdict",
    "ExtractedContent",
    "extract_content",
    "is_challenge_page",
    "should_escalate",
    "visible_text_length",
]
