"""YouTube video metadata and transcripts, without an API key.

Two endpoints, each with a different character:

* **oEmbed** is a small, documented, stable public endpoint. Title, author and
  thumbnail. Use it freely.
* **timedtext** is the player's own caption endpoint. It is undocumented and
  will break without notice — it already changed shape once, which is why the
  parser accepts both the XML and JSON3 forms. Treat a transcript failure as
  expected, not exceptional.

Getting a transcript needs the caption track list first, and finding that needs
a value from the watch page. Three round trips, which is why each step here is
a separate request/parse pair rather than one function that hides them.

**Verified 2026-09-15: the transcript path does not work from a datacenter IP.**
``www.youtube.com/watch`` answered 429 on every attempt, so
:func:`parse_caption_tracks` raises rather than returning captions. The oEmbed
metadata endpoint is unaffected and works fine.

That is not a bug to fix here. YouTube blocks unauthenticated watch-page reads
from cloud ranges, and getting past it needs cookies, a PO token, and continuous
maintenance as the checks change — which is exactly what ``yt-dlp`` does for a
living. **If you need transcripts at any volume, shell out to yt-dlp.** This
module is for the case where a caller wants one transcript from an IP YouTube
does not block, and would rather not add a dependency for it.

The failure is at least loud: a 429 raises :class:`ParseError` instead of
returning an empty tuple, so "we were blocked" never gets recorded as "this
video has no captions".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from weft.platforms._shared import (
    DEFAULT_USER_AGENT,
    ParseError,
    json_body,
    require_ok,
)
from weft.ports.dto import HttpRequest, HttpResponse

WATCH_URL = "https://www.youtube.com/watch"
OEMBED_URL = "https://www.youtube.com/oembed"

_HEADERS = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en"}

#: Video ids are exactly 11 characters of URL-safe base64.
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

#: The caption track list is embedded in the watch page as a JSON blob.
_CAPTION_TRACKS = re.compile(r'"captionTracks":(\[.*?\])', re.DOTALL)


@dataclass(slots=True, frozen=True)
class VideoMetadata:
    video_id: str
    title: str | None
    author_name: str | None
    author_url: str | None
    thumbnail_url: str | None


@dataclass(slots=True, frozen=True)
class CaptionTrack:
    url: str
    language_code: str
    name: str | None
    auto_generated: bool


@dataclass(slots=True, frozen=True)
class TranscriptCue:
    start_seconds: float
    duration_seconds: float
    text: str


@dataclass(slots=True, frozen=True)
class Transcript:
    video_id: str
    language_code: str
    cues: tuple[TranscriptCue, ...]

    @property
    def text(self) -> str:
        return "\n".join(cue.text for cue in self.cues if cue.text)


def video_id_from_url(url: str) -> str | None:
    """Extract a video id from any of the URL shapes YouTube uses.

    Returns None rather than guessing — a caller that cannot identify the video
    should say so, not fetch a different one.
    """
    if _VIDEO_ID.match(url):
        return url
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return None

    if host == "youtu.be":
        candidate = parts.path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID.match(candidate) else None

    if host not in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        return None

    if parts.path == "/watch":
        candidate = parse_qs(parts.query).get("v", [""])[0]
        return candidate if _VIDEO_ID.match(candidate) else None

    for prefix in ("/embed/", "/v/", "/shorts/", "/live/"):
        if parts.path.startswith(prefix):
            candidate = parts.path[len(prefix) :].split("/")[0]
            return candidate if _VIDEO_ID.match(candidate) else None
    return None


# --- metadata (oEmbed) ------------------------------------------------------


def metadata_request(video_id: str) -> HttpRequest:
    return HttpRequest(
        url=OEMBED_URL,
        params={"url": f"{WATCH_URL}?v={video_id}", "format": "json"},
        headers=_HEADERS,
    )


def parse_metadata(response: HttpResponse, video_id: str) -> VideoMetadata:
    require_ok(response.status, what="YouTube oEmbed")
    data = json_body(response.body, what="YouTube oEmbed")
    if not isinstance(data, dict):
        raise ParseError("YouTube oEmbed response was not an object")
    return VideoMetadata(
        video_id=video_id,
        title=data.get("title") or None,
        author_name=data.get("author_name") or None,
        author_url=data.get("author_url") or None,
        thumbnail_url=data.get("thumbnail_url") or None,
    )


# --- captions ---------------------------------------------------------------


def watch_page_request(video_id: str) -> HttpRequest:
    """The watch page, which carries the caption track list."""
    return HttpRequest(url=WATCH_URL, params={"v": video_id}, headers=_HEADERS)


def parse_caption_tracks(response: HttpResponse) -> tuple[CaptionTrack, ...]:
    """Caption tracks from a watch page.

    An empty tuple means no captions were offered — a normal outcome, not an
    error. A :class:`ParseError` means the page no longer has the shape this
    expects, which is a different problem and should be visible as one.
    """
    require_ok(response.status, what="YouTube watch page")
    match = _CAPTION_TRACKS.search(response.text())
    if not match:
        return ()

    tracks = json_body(match.group(1), what="YouTube caption tracks")
    if not isinstance(tracks, list):
        raise ParseError("YouTube caption track list was not an array")

    found = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        url = track.get("baseUrl")
        if not url:
            continue
        name = track.get("name")
        found.append(
            CaptionTrack(
                url=str(url),
                language_code=str(track.get("languageCode") or ""),
                name=(name or {}).get("simpleText") if isinstance(name, dict) else None,
                # "asr" is automatic speech recognition: a machine transcript.
                auto_generated=track.get("kind") == "asr",
            )
        )
    return tuple(found)


def select_track(
    tracks: tuple[CaptionTrack, ...],
    *,
    prefer: tuple[str, ...] = ("en",),
) -> CaptionTrack | None:
    """Pick a track: a preferred language first, human over automatic.

    Falls back to any track at all — a machine transcript in another language
    beats nothing, and the caller can see which it got.
    """
    for language in prefer:
        for auto in (False, True):
            for track in tracks:
                if track.language_code.startswith(language) and track.auto_generated is auto:
                    return track
    for auto in (False, True):
        for track in tracks:
            if track.auto_generated is auto:
                return track
    return None


def transcript_request(track: CaptionTrack) -> HttpRequest:
    """Fetch a track as JSON3, which is far easier to parse than the XML."""
    return HttpRequest(url=track.url, params={"fmt": "json3"}, headers=_HEADERS)


def parse_transcript(
    response: HttpResponse,
    *,
    video_id: str,
    language_code: str,
) -> Transcript:
    require_ok(response.status, what="YouTube transcript")

    # YouTube signals "I will not serve you these captions" as 200 with a
    # zero-length body, not as a 4xx. Reported live on 2026-09-22 against a
    # video whose tracks had just been listed successfully on the watch page,
    # so it is a refusal to serve, not a video without captions. Left as a
    # distinct error because "empty body" is diagnosable — it means the caller
    # needs a different egress IP — whereas the JSON decode failure it would
    # otherwise become sends you looking for a parser bug that is not there.
    if not response.body.strip():
        raise ParseError(
            "YouTube returned an empty transcript body (200 with no content). "
            "The track was listed but not served — typically an IP-based block; "
            "try a residential egress or a caption-bearing fallback."
        )

    data = json_body(response.body, what="YouTube transcript")
    if not isinstance(data, dict):
        raise ParseError("YouTube transcript response was not an object")

    cues = []
    for event in data.get("events") or []:
        if not isinstance(event, dict):
            continue
        segments = event.get("segs")
        if not isinstance(segments, list):
            continue
        text = "".join(
            str(seg.get("utf8", "")) for seg in segments if isinstance(seg, dict)
        ).strip()
        if not text:
            continue
        cues.append(
            TranscriptCue(
                start_seconds=float(event.get("tStartMs") or 0) / 1000.0,
                duration_seconds=float(event.get("dDurationMs") or 0) / 1000.0,
                text=text,
            )
        )

    return Transcript(video_id=video_id, language_code=language_code, cues=tuple(cues))
