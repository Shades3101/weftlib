"""Guards that must run before a request leaves the process.

SSRF checking and URL normalization, extracted from ClayHome's
``packages/core/net.py`` and ``packages/core/urls.py``.
"""

from webspec.safety.ssrf import (
    ResolvedTarget,
    UnsafeURLError,
    is_public_address,
    resolve_public_target,
    validate_url_shape,
)
from webspec.safety.urls import host_of, normalize_url, root_url, url_hash

__all__ = [
    "ResolvedTarget",
    "UnsafeURLError",
    "host_of",
    "is_public_address",
    "normalize_url",
    "resolve_public_target",
    "root_url",
    "url_hash",
    "validate_url_shape",
]
