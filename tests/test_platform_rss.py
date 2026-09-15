from __future__ import annotations

import pytest
from conftest import response

from webspec.platforms import ParseError, rss

RSS_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Acme Blog</title><link>https://acme.com/blog</link>
  <description>News</description>
  <item>
    <title>We raised a Series A</title>
    <link>https://acme.com/blog/series-a</link>
    <description>Funding news</description>
    <pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate>
    <guid>https://acme.com/blog/series-a</guid>
  </item>
</channel></rss>"""

ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Acme Blog</title>
  <link rel="self" href="https://acme.com/feed.xml"/>
  <link rel="alternate" href="https://acme.com/blog"/>
  <entry>
    <title>Hiring engineers</title>
    <link rel="alternate" href="https://acme.com/blog/hiring"/>
    <id>tag:acme.com,2026:1</id>
    <updated>2026-09-01T10:00:00Z</updated>
    <summary>We are hiring</summary>
  </entry>
</feed>"""


def test_parses_rss() -> None:
    feed = rss.parse_feed(response(RSS_FEED, content_type="application/rss+xml"))
    assert feed.title == "Acme Blog"
    assert len(feed.entries) == 1
    entry = feed.entries[0]
    assert entry.title == "We raised a Series A"
    assert entry.published_at is not None and entry.published_at.year == 2026


def test_parses_atom_and_prefers_the_alternate_link() -> None:
    feed = rss.parse_feed(response(ATOM_FEED, content_type="application/atom+xml"))
    assert feed.link == "https://acme.com/blog"        # not the rel=self link
    assert feed.entries[0].link == "https://acme.com/blog/hiring"
    assert feed.entries[0].published_at is not None


def test_malformed_xml_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="well-formed"):
        rss.parse_feed(response("<rss><channel>"))


def test_html_page_is_not_a_feed() -> None:
    with pytest.raises(ParseError, match="neither"):
        rss.parse_feed(response("<html><body>not a feed</body></html>"))


def test_bad_date_yields_none_rather_than_dropping_the_entry() -> None:
    """An unparseable date is worth less than the entry it is attached to."""
    feed = rss.parse_feed(
        response(RSS_FEED.replace("Mon, 01 Sep 2026 10:00:00 GMT", "sometime last week"))
    )
    assert len(feed.entries) == 1
    assert feed.entries[0].published_at is None


def test_external_entities_are_not_resolved() -> None:
    """A feed must not be able to make the parser read a local file."""
    attack = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<rss version='2.0'><channel><title>&xxe;</title>"
        "<description>d</description><link>l</link></channel></rss>"
    )
    try:
        feed = rss.parse_feed(response(attack))
    except ParseError:
        return  # refusing outright is also a correct outcome
    assert "root:" not in (feed.title or "")
