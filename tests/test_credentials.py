"""The credential seam: carries a secret onto a request, and nothing else."""

from __future__ import annotations

import pytest

from weft.platforms.search import brave
from weft.ports import ApiKey, BearerToken, Credential, HttpRequest, QueryKey, SearchRequest


@pytest.fixture
def request_() -> HttpRequest:
    return HttpRequest(url="https://example.com", headers={"Accept": "application/json"})


class TestPlacement:
    def test_api_key_lands_in_its_header(self, request_: HttpRequest) -> None:
        out = ApiKey("X-API-Key", "secret").apply(request_)
        assert out.headers["X-API-Key"] == "secret"

    def test_bearer_token_is_prefixed(self, request_: HttpRequest) -> None:
        out = BearerToken("abc123").apply(request_)
        assert out.headers["Authorization"] == "Bearer abc123"

    def test_query_key_lands_in_params(self, request_: HttpRequest) -> None:
        out = QueryKey("apikey", "secret").apply(request_)
        assert out.params["apikey"] == "secret"
        assert "apikey" not in out.headers

    @pytest.mark.parametrize(
        "credential",
        [ApiKey("X-API-Key", "s"), BearerToken("s"), QueryKey("k", "s")],
    )
    def test_existing_fields_survive(
        self, credential: Credential, request_: HttpRequest
    ) -> None:
        """A credential adds; it must not clear what the platform already set."""
        out = credential.apply(request_)
        assert out.headers["Accept"] == "application/json"
        assert out.url == request_.url


class TestNoMutation:
    """The original request must be untouched — it may be shared or reused."""

    @pytest.mark.parametrize(
        "credential",
        [ApiKey("X-API-Key", "s"), BearerToken("s"), QueryKey("k", "s")],
    )
    def test_source_request_is_unchanged(
        self, credential: Credential, request_: HttpRequest
    ) -> None:
        before = dict(request_.headers), dict(request_.params)
        credential.apply(request_)
        assert (dict(request_.headers), dict(request_.params)) == before


class TestRedaction:
    """A courtesy against log leakage, not a security control — but it should
    at least hold for the obvious cases."""

    @pytest.mark.parametrize(
        "credential",
        [ApiKey("X-API-Key", "hunter2"), BearerToken("hunter2"), QueryKey("k", "hunter2")],
    )
    def test_secret_absent_from_repr(self, credential: Credential) -> None:
        assert "hunter2" not in repr(credential)

    def test_length_survives_for_debugging(self) -> None:
        """The usual bug is an empty or newline-terminated value; masking the
        length entirely hides both."""
        assert "len=7" in repr(BearerToken("hunter2"))
        assert "len=8" in repr(BearerToken("hunter2\n"))

    def test_header_name_is_visible(self) -> None:
        """Which credential failed is not itself a secret."""
        assert "X-API-Key" in repr(ApiKey("X-API-Key", "hunter2"))


class TestProtocolConformance:
    @pytest.mark.parametrize(
        "credential",
        [ApiKey("X-API-Key", "s"), BearerToken("s"), QueryKey("k", "s")],
    )
    def test_builtins_satisfy_the_protocol(self, credential: Credential) -> None:
        assert isinstance(credential, Credential)

    def test_a_foreign_type_qualifies_by_shape(self, request_: HttpRequest) -> None:
        """The point of a Protocol: a caller's own credential type works without
        inheriting from, or importing, weft."""

        class CallerOwnedKey:
            def apply(self, request: HttpRequest) -> HttpRequest:
                return request.with_header("X-Custom", "from-caller")

        assert isinstance(CallerOwnedKey(), Credential)
        assert CallerOwnedKey().apply(request_).headers["X-Custom"] == "from-caller"


class TestBraveAcceptsEitherForm:
    """Brave is the one keyed platform, so it is where the seam is exercised."""

    def test_api_key_and_auth_produce_the_same_request(self) -> None:
        query = SearchRequest(query="python")
        via_key = brave.search_request(query, api_key="secret")
        via_auth = brave.search_request(query, auth=ApiKey(brave.KEY_HEADER, "secret"))
        assert via_key == via_auth
        assert via_key.headers[brave.KEY_HEADER] == "secret"

    def test_neither_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            brave.search_request(SearchRequest(query="python"))

    def test_both_is_rejected(self) -> None:
        """Silently preferring one would make the ignored key look effective."""
        with pytest.raises(ValueError, match="exactly one"):
            brave.search_request(
                SearchRequest(query="python"),
                api_key="secret",
                auth=ApiKey(brave.KEY_HEADER, "other"),
            )

    def test_a_caller_credential_reaches_the_request(self) -> None:
        request = brave.search_request(
            SearchRequest(query="python"), auth=BearerToken("token")
        )
        assert request.headers["Authorization"] == "Bearer token"
