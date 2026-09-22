"""Per-platform request builders and response parsers.

Each module answers two questions and nothing else: *which request would
retrieve this?* and *what does this response mean?* Executing the request is
the caller's job — see :mod:`weft.ports.protocols`.

Everything these parsers return is untrusted third-party content.
"""

from weft.platforms import github, reader, rss, youtube
from weft.platforms._shared import ParseError

__all__ = ["ParseError", "github", "reader", "rss", "youtube"]
