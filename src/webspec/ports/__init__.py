"""The seams a caller implements: transports, renderers, caches, and the
neutral data types that cross them.

Nothing here executes. These are protocols and dataclasses only.
"""

from webspec.ports.dto import (
    FetchedPage,
    FetchMethod,
    HttpRequest,
    HttpResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from webspec.ports.protocols import AsyncTransport, Cache, Renderer, Transport

__all__ = [
    "AsyncTransport",
    "Cache",
    "FetchMethod",
    "FetchedPage",
    "HttpRequest",
    "HttpResponse",
    "Renderer",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
    "Transport",
]
