from __future__ import annotations

import pytest
from conftest import response

from weft.platforms import ParseError, github

REPO = {
    "full_name": "acme/widget",
    "description": "A widget",
    "html_url": "https://github.com/acme/widget",
    "homepage": "https://acme.com",
    "stargazers_count": 42,
    "forks_count": 7,
    "open_issues_count": 3,
    "language": "Python",
    "topics": ["automation", "cli"],
    "archived": False,
    "pushed_at": "2026-09-01T10:00:00Z",
    "license": {"name": "MIT License"},
}


def test_request_shape() -> None:
    request = github.repository_request("acme", "widget")
    assert request.url == "https://api.github.com/repos/acme/widget"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert "Authorization" not in request.headers


def test_token_is_used_but_never_stored() -> None:
    request = github.repository_request("acme", "widget", token="ghp_x")
    assert request.headers["Authorization"] == "Bearer ghp_x"
    # Nothing module-level retained it.
    assert "Authorization" not in github.repository_request("a", "b").headers


def test_parse_repository() -> None:
    repo = github.parse_repository(response(REPO))
    assert repo.full_name == "acme/widget"
    assert repo.stars == 42
    assert repo.topics == ("automation", "cli")
    assert repo.license_name == "MIT License"
    assert repo.pushed_at is not None and repo.pushed_at.year == 2026


def test_missing_optional_fields_become_none_not_crash() -> None:
    repo = github.parse_repository(response({"full_name": "a/b", "html_url": "u"}))
    assert repo.description is None
    assert repo.stars == 0
    assert repo.topics == ()
    assert repo.license_name is None


def test_error_status_refuses_to_parse() -> None:
    """A 404 body is not data. Parsing it stores 'Not Found' as a description."""
    with pytest.raises(ParseError, match="404"):
        github.parse_repository(response({"message": "Not Found"}, status=404))


def test_non_json_body_is_a_parse_error() -> None:
    with pytest.raises(ParseError):
        github.parse_repository(response("<html>proxy error</html>"))


def test_rate_limit_readable_from_a_403() -> None:
    """Exactly when a caller most needs the budget: after being refused."""
    limit = github.rate_limit_of(
        response(
            {"message": "rate limited"},
            status=403,
            headers={
                "x-ratelimit-limit": "60",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "1789000000",
            },
        )
    )
    assert limit.exhausted
    assert limit.limit == 60
    assert limit.resets_at is not None


def test_rate_limit_absent_headers_are_none_not_zero() -> None:
    """None means unknown; 0 means exhausted. Conflating them causes a
    permanent false backoff."""
    limit = github.rate_limit_of(response({}))
    assert limit.remaining is None
    assert not limit.exhausted
