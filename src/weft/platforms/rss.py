"""RSS 2.0 and Atom feeds.

Parsed with the stdlib rather than ``feedparser``. The formats are small, this
package is meant to stay dependency-light, and — the deciding reason —
``xml.etree`` will not resolve external entities, so a feed cannot make the
parser fetch a local file. ``feedparser`` is fine, but it is another dependency
to justify for two element names.

Feeds are third-party content. Everything here may be attacker-controlled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from weft.platforms._shared import DEFAULT_USER_AGENT, ParseError, require_ok
from weft.ports.dto import HttpRequest, HttpResponse

_ATOM = "{http://www.w3.org/2005/Atom}"

#: Caps on a hostile or merely enormous feed. weft cannot bound the download
#: — it has no socket — but it can refuse to build a million objects from it.
MAX_ENTRIES = 500


@dataclass(slots=True, frozen=True)
class FeedEntry:
    title: str | None
    link: str | None
    summary: str | None
    published_at: datetime | None
    entry_id: str | None


@dataclass(slots=True, frozen=True)
class Feed:
    title: str | None
    link: str | None
    description: str | None
    entries: tuple[FeedEntry, ...]


def feed_request(url: str) -> HttpRequest:
    return HttpRequest(
        url=url,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )


def _text(node: ElementTree.Element | None) -> str | None:
    if node is None:
        return None
    text = (node.text or "").strip()
    return text or None


def _date(raw: str | None) -> datetime | None:
    """Accept both formats feeds use, and neither if the value is nonsense."""
    if not raw:
        return None
    raw = raw.strip()
    try:  # Atom: ISO 8601
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        pass
    try:  # RSS: RFC 822
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _atom_link(entry: ElementTree.Element) -> str | None:
    """Atom puts the URL in an attribute, and may offer several. Prefer the
    alternate link; fall back to the first one with an href."""
    fallback = None
    for link in entry.findall(f"{_ATOM}link"):
        href = link.get("href")
        if not href:
            continue
        if link.get("rel", "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def parse_feed(response: HttpResponse) -> Feed:
    require_ok(response.status, what="Feed")
    try:
        root = ElementTree.fromstring(response.body)  # noqa: S314 - see module docstring
    except ElementTree.ParseError as exc:
        raise ParseError("Feed body is not well-formed XML") from exc

    channel = root.find("channel")
    if channel is not None:  # RSS 2.0
        entries = [
            FeedEntry(
                title=_text(item.find("title")),
                link=_text(item.find("link")),
                summary=_text(item.find("description")),
                published_at=_date(_text(item.find("pubDate"))),
                entry_id=_text(item.find("guid")),
            )
            for item in channel.findall("item")[:MAX_ENTRIES]
        ]
        return Feed(
            title=_text(channel.find("title")),
            link=_text(channel.find("link")),
            description=_text(channel.find("description")),
            entries=tuple(entries),
        )

    if root.tag == f"{_ATOM}feed":
        entries = [
            FeedEntry(
                title=_text(entry.find(f"{_ATOM}title")),
                link=_atom_link(entry),
                summary=_text(entry.find(f"{_ATOM}summary"))
                or _text(entry.find(f"{_ATOM}content")),
                published_at=_date(
                    _text(entry.find(f"{_ATOM}published"))
                    or _text(entry.find(f"{_ATOM}updated"))
                ),
                entry_id=_text(entry.find(f"{_ATOM}id")),
            )
            for entry in root.findall(f"{_ATOM}entry")[:MAX_ENTRIES]
        ]
        return Feed(
            title=_text(root.find(f"{_ATOM}title")),
            link=_atom_link(root),
            description=_text(root.find(f"{_ATOM}subtitle")),
            entries=tuple(entries),
        )

    raise ParseError("Body is neither an RSS channel nor an Atom feed")
