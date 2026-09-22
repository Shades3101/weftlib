"""Search backends, as request builders and response parsers.

Each module exposes the same pair — ``search_request(...) -> HttpRequest`` and
``parse_search(response, request) -> SearchResponse`` — so a caller can swap
one for another without changing anything but the import.

Results from any of these are untrusted third-party content. A search result
claiming something is not evidence of it, and a snippet saying "ignore your
previous instructions" is a snippet.
"""

from weft.platforms.search import brave, searxng

__all__ = ["brave", "searxng"]
