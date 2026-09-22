from __future__ import annotations

import pytest
from conftest import response

from weft.platforms import ParseError, youtube
from weft.ports import HttpResponse


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
        "dQw4w9WgXcQ",
    ],
)
def test_video_id_from_every_url_shape(url: str) -> None:
    assert youtube.video_id_from_url(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/watch?v=dQw4w9WgXcQ",  # not a YouTube host
        "https://www.youtube.com/watch?v=short",     # wrong id length
        "https://www.youtube.com/",
        "not a url",
    ],
)
def test_unrecognised_urls_return_none_rather_than_guessing(url: str) -> None:
    assert youtube.video_id_from_url(url) is None


def test_metadata_parse() -> None:
    meta = youtube.parse_metadata(
        response({"title": "A talk", "author_name": "Acme"}), "dQw4w9WgXcQ"
    )
    assert meta.title == "A talk"
    assert meta.author_name == "Acme"


def test_no_captions_is_empty_not_an_error() -> None:
    """A video without captions is a normal outcome."""
    assert youtube.parse_caption_tracks(response("<html>no captions here</html>")) == ()


def test_caption_tracks_parsed_from_watch_page() -> None:
    page = (
        '<html><script>{"captionTracks":['
        '{"baseUrl":"https://yt/api/timedtext?a=1","languageCode":"en",'
        '"name":{"simpleText":"English"},"kind":"asr"},'
        '{"baseUrl":"https://yt/api/timedtext?a=2","languageCode":"de",'
        '"name":{"simpleText":"Deutsch"}}'
        "]}</script></html>"
    )
    tracks = youtube.parse_caption_tracks(response(page))
    assert len(tracks) == 2
    assert tracks[0].auto_generated is True
    assert tracks[1].auto_generated is False


def test_track_selection_prefers_language_then_human_over_automatic() -> None:
    auto_en = youtube.CaptionTrack("u1", "en", "English (auto)", True)
    human_en = youtube.CaptionTrack("u2", "en", "English", False)
    human_de = youtube.CaptionTrack("u3", "de", "Deutsch", False)

    assert youtube.select_track((auto_en, human_en), prefer=("en",)) is human_en
    assert youtube.select_track((auto_en,), prefer=("en",)) is auto_en
    # Falls back to something rather than nothing.
    assert youtube.select_track((human_de,), prefer=("en",)) is human_de
    assert youtube.select_track((), prefer=("en",)) is None


def test_transcript_parse_joins_segments_and_converts_ms() -> None:
    payload = {
        "events": [
            {"tStartMs": 1500, "dDurationMs": 2000,
             "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
            {"tStartMs": 4000, "segs": [{"utf8": "\n"}]},   # whitespace only
            {"tStartMs": 5000, "dDurationMs": 1000, "segs": [{"utf8": "Bye"}]},
        ]
    }
    transcript = youtube.parse_transcript(
        response(payload), video_id="dQw4w9WgXcQ", language_code="en"
    )
    assert [cue.text for cue in transcript.cues] == ["Hello world", "Bye"]
    assert transcript.cues[0].start_seconds == 1.5
    assert transcript.text == "Hello world\nBye"


def test_transcript_error_status_refuses_to_parse() -> None:
    with pytest.raises(ParseError):
        youtube.parse_transcript(
            response("", status=404), video_id="x", language_code="en"
        )


class TestEmptyTranscriptBody:
    """YouTube refuses captions as 200-with-no-body rather than a 4xx.

    Observed live on 2026-09-22 on a video whose tracks the watch page had just
    listed, so this is a refusal to serve rather than a video without captions.
    """

    def _empty(self, body: bytes) -> HttpResponse:
        return response(body, url="https://youtube.com/api/timedtext")

    @pytest.mark.parametrize("body", [b"", b"   ", b"\n"])
    def test_empty_body_says_what_happened(self, body: bytes) -> None:
        with pytest.raises(ParseError, match="empty transcript body"):
            youtube.parse_transcript(self._empty(body), video_id="x", language_code="en")

    def test_it_does_not_masquerade_as_a_parser_bug(self) -> None:
        """The failure this replaced sent you hunting for a JSON bug that was
        never there."""
        with pytest.raises(ParseError) as caught:
            youtube.parse_transcript(self._empty(b""), video_id="x", language_code="en")
        assert "valid JSON" not in str(caught.value)

    def test_real_json_still_parses(self) -> None:
        body = b'{"events":[{"segs":[{"utf8":"hello"}],"tStartMs":0,"dDurationMs":100}]}'
        transcript = youtube.parse_transcript(
            self._empty(body), video_id="x", language_code="en"
        )
        assert transcript.cues
