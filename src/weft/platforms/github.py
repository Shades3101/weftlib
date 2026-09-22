"""GitHub's public REST API.

Keyless. The unauthenticated rate limit is 60 requests per hour per IP, which
is the real constraint on using this at any volume — :func:`rate_limit_of`
reads the remaining budget from any response so a caller can back off before it
is refused rather than after.

A token raises the limit to 5,000/hour. weft does not hold one: pass it via
``token=`` and the caller decides where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from weft.platforms._shared import DEFAULT_USER_AGENT, json_body, require_ok
from weft.ports.dto import HttpRequest, HttpResponse

API_ROOT = "https://api.github.com"

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": DEFAULT_USER_AGENT,
}


def _headers(token: str | None) -> dict[str, str]:
    headers = dict(_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass(slots=True, frozen=True)
class Repository:
    full_name: str
    description: str | None
    html_url: str
    homepage: str | None
    stars: int
    forks: int
    open_issues: int
    language: str | None
    topics: tuple[str, ...]
    archived: bool
    pushed_at: datetime | None
    license_name: str | None


@dataclass(slots=True, frozen=True)
class RateLimit:
    """What a response said about the remaining budget."""

    limit: int | None
    remaining: int | None
    resets_at: datetime | None

    @property
    def exhausted(self) -> bool:
        return self.remaining is not None and self.remaining <= 0


# --- requests ---------------------------------------------------------------


def repository_request(owner: str, repo: str, *, token: str | None = None) -> HttpRequest:
    return HttpRequest(url=f"{API_ROOT}/repos/{owner}/{repo}", headers=_headers(token))


def user_request(username: str, *, token: str | None = None) -> HttpRequest:
    return HttpRequest(url=f"{API_ROOT}/users/{username}", headers=_headers(token))


def readme_request(owner: str, repo: str, *, token: str | None = None) -> HttpRequest:
    """The README as rendered text rather than base64-wrapped JSON."""
    headers = _headers(token)
    headers["Accept"] = "application/vnd.github.raw+json"
    return HttpRequest(url=f"{API_ROOT}/repos/{owner}/{repo}/readme", headers=headers)


# --- parsing ----------------------------------------------------------------


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def parse_repository(response: HttpResponse) -> Repository:
    require_ok(response.status, what="GitHub repository")
    data = json_body(response.body, what="GitHub repository")
    if not isinstance(data, dict):
        raise TypeError("GitHub repository response was not an object")

    licence = data.get("license")
    topics = data.get("topics")
    return Repository(
        full_name=str(data.get("full_name", "")),
        description=data.get("description") or None,
        html_url=str(data.get("html_url", "")),
        homepage=data.get("homepage") or None,
        stars=int(data.get("stargazers_count") or 0),
        forks=int(data.get("forks_count") or 0),
        open_issues=int(data.get("open_issues_count") or 0),
        language=data.get("language") or None,
        topics=tuple(str(t) for t in topics) if isinstance(topics, list) else (),
        archived=bool(data.get("archived")),
        pushed_at=_timestamp(data.get("pushed_at")),
        license_name=(licence or {}).get("name") if isinstance(licence, dict) else None,
    )


def parse_readme(response: HttpResponse) -> str:
    """The raw README. Requested with the ``.raw`` accept header, so the body is
    already text rather than base64 inside JSON."""
    require_ok(response.status, what="GitHub README")
    return response.text()


def rate_limit_of(response: HttpResponse) -> RateLimit:
    """Read the budget from any GitHub response.

    Works on failures too — a 403 for rate limiting carries these headers, and
    that is exactly when a caller most needs them.
    """
    headers = {k.lower(): v for k, v in response.headers.items()}

    def _int(name: str) -> int | None:
        try:
            return int(headers[name])
        except (KeyError, ValueError, TypeError):
            return None

    reset = _int("x-ratelimit-reset")
    return RateLimit(
        limit=_int("x-ratelimit-limit"),
        remaining=_int("x-ratelimit-remaining"),
        resets_at=datetime.fromtimestamp(reset, tz=UTC) if reset is not None else None,
    )
