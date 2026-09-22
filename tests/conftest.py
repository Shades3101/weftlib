from __future__ import annotations

import json
from typing import Any

from weft.ports import HttpResponse


def response(
    body: Any = b"",
    *,
    status: int = 200,
    url: str = "https://example.com/",
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    """Build an HttpResponse from a dict, str, or bytes."""
    if isinstance(body, (dict, list)):
        raw = json.dumps(body).encode()
    elif isinstance(body, str):
        raw = body.encode()
    else:
        raw = body
    merged = {"content-type": content_type}
    merged.update(headers or {})
    return HttpResponse(url=url, status=status, body=raw, headers=merged)
