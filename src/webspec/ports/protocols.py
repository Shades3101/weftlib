"""The seams a caller implements.

webspec builds requests and parses responses. Somebody has to actually send
them, and these protocols describe that somebody. They are
:class:`typing.Protocol` rather than ABCs so an existing class can satisfy one
by shape, without inheriting from this package — ClayHome's fetcher already has
the right methods and should not need to be told about webspec to qualify.

Both sync and async forms are provided. ClayHome is async throughout; a script
or a sync tool runtime is not, and forcing either to adapt would be a tax paid
for nothing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from webspec.ports.dto import FetchedPage, HttpRequest, HttpResponse


@runtime_checkable
class Transport(Protocol):
    """Sends an :class:`HttpRequest` and returns what came back.

    Implementations own everything a caller must not be able to skip: the SSRF
    check, timeouts, retries, size caps, robots handling, and rate limiting.
    webspec deliberately cannot enforce any of it — that is the caller's
    security boundary, not this library's.
    """

    def send(self, request: HttpRequest) -> HttpResponse: ...


@runtime_checkable
class AsyncTransport(Protocol):
    """The async form of :class:`Transport`."""

    async def send(self, request: HttpRequest) -> HttpResponse: ...


@runtime_checkable
class Renderer(Protocol):
    """Retrieves a page that plain HTTP cannot read — a JavaScript shell, say.

    Deliberately shaped so a headless browser, a hosted reader service, or a
    paid unblocking API all fit. Which one is behind it is the caller's
    decision and its cost to bear; a browser launch is orders of magnitude more
    expensive than a GET, so :func:`webspec.extract.escalation.should_escalate`
    exists to make that choice deliberate rather than habitual.
    """

    async def render(self, url: str, *, wait_ms: int = 1500) -> FetchedPage: ...


@runtime_checkable
class Cache(Protocol):
    """Stores fetched pages between runs.

    ClayHome backs this with Postgres; a script may back it with a dict or not
    at all. webspec never calls it — the type exists so a caller's fetcher can
    declare what it accepts in terms this package understands.
    """

    async def get(self, key: str) -> FetchedPage | None: ...

    async def put(self, key: str, page: FetchedPage, *, ttl_seconds: int) -> None: ...
