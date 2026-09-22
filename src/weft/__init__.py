"""weft — web access as pure logic.

This package performs **no I/O**. It builds request descriptions and parses
response payloads; the caller executes them with whatever HTTP client it
already has.

That is not an aesthetic preference. JARVIS tools may only reach the network
through ``ctx.http``, the egress-policed client its Tool Runtime supplies, and
are forbidden from importing an HTTP client or opening a socket. A library that
fetched anything itself could not be imported there at all. The same rule makes
the package trivially portable: it has no opinion about sync vs async, about
your HTTP client, cache, or framework.

The one deliberate exception is :mod:`weft.safety`, which resolves DNS —
that *is* the SSRF check. It is a pure function returning a verdict, exposed so
a transport can consult it before it connects.

Importing :mod:`weft` gives you the types that cross the seam — requests,
responses, credentials, and the protocols a caller satisfies::

    from weft import HttpRequest, HttpResponse, SearchRequest, Transport

Platform modules and extraction are deliberately *not* re-exported here. They
are imported explicitly::

    from weft.platforms import github, youtube
    from weft.platforms.search import brave, searxng
    from weft.extract import extract_content

That is not tidiness for its own sake. :mod:`weft.extract` pulls in
``selectolax``, the package's only runtime dependency; a caller that just wants
to build a GitHub request and parse the JSON should not pay for an HTML parser
it never calls. Keeping the top level to dependency-free types means
``import weft`` stays cheap no matter what else is installed.
"""

from weft.ports import (
    ApiKey,
    AsyncTransport,
    BearerToken,
    Cache,
    Credential,
    FetchedPage,
    FetchMethod,
    HttpRequest,
    HttpResponse,
    QueryKey,
    Renderer,
    SearchHit,
    SearchRequest,
    SearchResponse,
    Transport,
)
from weft.safety import UnsafeURLError

__version__ = "0.1.0"

__all__ = [
    "ApiKey",
    "AsyncTransport",
    "BearerToken",
    "Cache",
    "Credential",
    "FetchMethod",
    "FetchedPage",
    "HttpRequest",
    "HttpResponse",
    "QueryKey",
    "Renderer",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
    "Transport",
    "UnsafeURLError",
    "__version__",
]
