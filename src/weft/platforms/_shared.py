"""Helpers every platform module needs.

Kept deliberately small. A platform module should read as "this is the request,
this is what the response means" with as little machinery in the way as
possible.
"""

from __future__ import annotations

import json
from typing import Any

#: A plain, honest identifier. Nothing here pretends to be a browser: the
#: package never defeats bot protection, and a user-agent that lies is the
#: first step toward doing so.
DEFAULT_USER_AGENT = "weft/0.1 (+https://github.com/Shades3101/weft)"


class ParseError(ValueError):
    """A response could not be interpreted.

    Distinct from an HTTP failure: the request succeeded and the body was
    unusable. Callers usually record this rather than retrying, because a retry
    produces the same unusable body.
    """


def json_body(body: bytes | str, *, what: str) -> Any:
    """Decode a JSON response, or fail with a message naming the source.

    ``what`` appears in the error. "YouTube returned no JSON" is actionable;
    "Expecting value: line 1 column 1" is not.
    """
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ParseError(f"{what} did not return valid JSON") from exc


def require_ok(status: int | None, *, what: str) -> None:
    """Refuse to parse a body that came with a failure status.

    Parsing an error page as if it were data is how a pipeline ends up storing
    'Page Not Found' as a company description.
    """
    if status is None or not (200 <= status < 300):
        raise ParseError(f"{what} returned HTTP {status}")
