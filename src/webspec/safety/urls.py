"""URL normalization.

Two references to the same page must normalize to the same string, or callers
cache it twice, fetch it twice, and — in a discovery pipeline — report the same
result twice.

Extracted from ClayHome ``packages/core/urls.py``. The public-suffix-aware
helpers there (``registrable_domain``, ``is_aggregator``,
``is_plausible_company_domain``) deliberately stayed behind: they need
``tldextract`` plus curated lists of aggregator and free-mail domains, which is
prospecting domain knowledge rather than web access, and would put a dependency
in a package that otherwise needs none.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

#: Analytics and campaign parameters that never change what a page shows.
TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_source_platform", "utm_creative_format",
        "gclid", "gbraid", "wbraid", "fbclid", "msclkid", "dclid", "yclid",
        "mc_cid", "mc_eid", "igshid", "twclid", "ttclid", "li_fat_id",
        "ref", "referrer", "source",
        "_hsenc", "_hsmi", "hsa_cam", "hsa_grp",
        "vero_id", "vero_conv", "s_kwcid", "ef_id",
        "trk", "trkCampaign", "spm", "scm", "share_source",
    }
)

DEFAULT_PORTS = {"http": "80", "https": "443"}

#: Index filenames that address the same resource as their parent directory.
INDEX_FILENAMES = ("/index.html", "/index.htm", "/index.php", "/default.aspx")


def normalize_url(url: str, *, keep_query: bool = True) -> str:
    """Canonical form for comparison and caching.

    Lowercases scheme and host, drops default ports and fragments, strips
    tracking parameters, sorts what remains, collapses index filenames, and
    removes a trailing slash on non-root paths.

    Returns the stripped input if it cannot be parsed. Callers treat an
    unparseable URL as something to skip, not as a crash — and the safety guard
    in :mod:`webspec.safety.ssrf` is what decides whether it may be fetched.
    """
    if not url:
        return ""
    candidate = url.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = "https://" + candidate.lstrip("/")

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return url.strip()

    scheme = (parts.scheme or "https").lower()
    try:
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return url.strip()
    if not host:
        return url.strip()

    # `www.acme.com` and `acme.com` are the same site in practice. Collapsing
    # them is what stops one page being treated as two.
    if host.startswith("www.") and host.count(".") > 1:
        host = host[4:]

    try:
        port = parts.port
    except ValueError:
        return url.strip()
    netloc = host
    if port is not None and str(port) != DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    for index_name in INDEX_FILENAMES:
        if path.lower().endswith(index_name):
            path = path[: -len(index_name)] or "/"
            break

    query = ""
    if keep_query and parts.query:
        kept = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        query = urlencode(sorted(kept))

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str) -> str:
    """Stable cache key. Always hashes the normalized form, never the input."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def host_of(url: str) -> str | None:
    """Hostname of the normalized URL, or None when there isn't one."""
    try:
        host = urlsplit(normalize_url(url)).hostname
    except ValueError:
        return None
    return host.lower().rstrip(".") if host else None


def root_url(url: str) -> str | None:
    """The homepage for a URL — where research into a site starts."""
    host = host_of(url)
    if not host:
        return None
    try:
        scheme = urlsplit(normalize_url(url)).scheme or "https"
    except ValueError:
        return None
    return f"{scheme}://{host}"
