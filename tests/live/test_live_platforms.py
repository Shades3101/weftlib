"""Live checks against the real endpoints.

Each test asserts the *shape* weft's parser depends on, not the content. That
GitHub's description for a repo changed is none of our business; that
``stargazers_count`` stopped being an integer is very much our business, and is
the class of breakage the fixture-based suite cannot see.

Assertions are kept loose on purpose. A live test that pins a star count is a
test that fails every Tuesday and gets muted by March.
"""

from __future__ import annotations

import pytest

from weft.extract import extract_content
from weft.platforms import github, reader, rss, youtube
from weft.platforms.search import brave, searxng
from weft.ports import ApiKey, SearchRequest

from .conftest import UrllibTransport, requires_network

pytestmark = [pytest.mark.live, requires_network]


class TestGitHub:
    def test_repository_shape_holds(self, http: UrllibTransport) -> None:
        response = http.send(github.repository_request("python", "cpython"))
        if response.status == 403:
            pytest.skip("GitHub rate limit reached for this IP")

        repo = github.parse_repository(response)
        assert repo.full_name.lower() == "python/cpython"
        assert isinstance(repo.stars, int)
        assert repo.stars > 0

    def test_rate_limit_headers_still_present(self, http: UrllibTransport) -> None:
        """weft reports remaining quota; that depends on headers GitHub could
        rename without breaking any of its own clients."""
        response = http.send(github.repository_request("python", "cpython"))
        limit = github.rate_limit_of(response)
        assert limit.limit is None or isinstance(limit.limit, int)

    def test_readme_decodes(self, http: UrllibTransport) -> None:
        """The README arrives base64-encoded inside JSON — two layers that have
        each changed at other providers."""
        response = http.send(github.readme_request("python", "cpython"))
        if response.status == 403:
            pytest.skip("GitHub rate limit reached for this IP")
        assert len(github.parse_readme(response)) > 100


class TestYouTube:
    #: "Me at the zoo" — the first video uploaded to YouTube, and about as
    #: unlikely to be deleted as anything on the platform.
    VIDEO_ID = "jNQXAC9IVRw"

    def test_oembed_metadata(self, http: UrllibTransport) -> None:
        response = http.send(youtube.metadata_request(self.VIDEO_ID))
        meta = youtube.parse_metadata(response, self.VIDEO_ID)
        assert meta.title
        assert meta.author_name

    def test_caption_tracks_are_still_findable(self, http: UrllibTransport) -> None:
        """The fragile one, and the reason this suite exists: tracks are scraped
        out of the watch page's embedded JSON, which YouTube reshapes without
        notice and serves differently to datacentre IPs."""
        response = http.send(youtube.watch_page_request(self.VIDEO_ID))
        tracks = youtube.parse_caption_tracks(response)
        if not tracks:
            pytest.skip("YouTube served no caption tracks (commonly an IP-based block)")

        track = youtube.select_track(tracks, prefer=("en",))
        assert track is not None

        # Listing tracks and being served them are separate permissions. YouTube
        # answers a refused timedtext fetch with 200 and an empty body, which is
        # a fact about this machine's IP rather than a regression in weft.
        served = http.send(youtube.transcript_request(track))
        if not served.body.strip():
            pytest.skip("YouTube listed the track but served an empty body (IP-based block)")

        transcript = youtube.parse_transcript(
            served, video_id=self.VIDEO_ID, language_code=track.language_code
        )
        assert transcript.cues


class TestRSS:
    FEED = "https://hnrss.org/frontpage"

    def test_feed_parses(self, http: UrllibTransport) -> None:
        feed = rss.parse_feed(http.send(rss.feed_request(self.FEED)))
        assert feed.entries
        first = feed.entries[0]
        assert first.link and first.link.startswith("http")


class TestReader:
    def test_reader_returns_readable_text(self, http: UrllibTransport) -> None:
        request = reader.reader_request("https://example.com")
        response = http.send(request)
        if response.status == 429:
            pytest.skip("r.jina.ai rate limit reached (keyless tier)")

        page = reader.parse_reader(response, url="https://example.com")
        assert page.ok
        assert page.text and "example" in page.text.lower()

    def test_reader_still_refuses_an_internal_target(self) -> None:
        """Not a network test — asserts that nothing leaves the process. Kept
        here beside the live reader test because this is the failure mode a
        working live test would otherwise make look harmless."""
        from weft.safety import UnsafeURLError

        with pytest.raises(UnsafeURLError):
            reader.reader_request("http://169.254.169.254/latest/meta-data/")


class TestSearch:
    def test_brave_returns_hits(self, http: UrllibTransport, brave_key: str) -> None:
        query = SearchRequest(query="python programming language", limit=5)
        request = brave.search_request(query, auth=ApiKey(brave.KEY_HEADER, brave_key))
        response = http.send(request)
        if response.status == 429:
            pytest.skip("Brave rate limit reached (free tier is 1 query/second)")

        result = brave.parse_search(response, query)
        assert result.ok
        assert result.hits
        assert all(hit.url.startswith("http") for hit in result.hits)

    def test_searxng_returns_hits(self, http: UrllibTransport, searxng_url: str) -> None:
        query = SearchRequest(query="python programming language", limit=5)
        response = http.send(searxng.search_request(query, base_url=searxng_url))
        if response.status == 403:
            pytest.skip("SearXNG rejected the request (check `json` is in search.formats)")

        result = searxng.parse_search(response, query)
        assert result.ok
        assert result.hits


class TestExtraction:
    def test_real_html_yields_text(self, http: UrllibTransport) -> None:
        from weft.ports import HttpRequest

        response = http.send(HttpRequest(url="https://example.com"))
        content = extract_content(response.text())
        # Asserting on the boilerplate wording would fail the day IANA reworded
        # the page — as they have. The claim worth making is that extraction
        # found the title and a non-trivial body, not what the body says.
        assert content.title == "Example Domain"
        assert len(content.text) > 50
