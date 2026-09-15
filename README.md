# webspec

Web access as pure logic. Builds request descriptions, parses responses,
**performs no I/O**.

```python
from webspec.platforms import youtube

request = youtube.transcript_request("dQw4w9WgXcQ")   # a description
response = my_http_client.send(request)                # caller executes
transcript = youtube.parse_transcript(response)        # back to webspec
```

## Why no I/O

Two consumers, one hard constraint:

- **JARVIS** (`Personal-AI`) — tools reach the network *only* through
  `ctx.http`, the egress-policed client its Tool Runtime builds from a declared
  host allowlist. A tool may not import an HTTP client or open a socket. A
  library that fetched things itself could not be used there.
- **ClayHome** — has its own fetcher with robots.txt handling, per-host
  concurrency limits, retries, size caps, and a Postgres-backed page cache. It
  does not want a second, competing HTTP stack.

So the library owns the *logic* and each caller owns the *pipe*. The side
effect is portability: no HTTP client, no async framework, no pydantic, no
version conflicts with anything.

The single exception is `webspec.safety`, which resolves DNS — that is the
point of an SSRF check. It is a pure function returning a verdict.

## Identity

`webspec` owns **none**. Credentials are passed in by the caller, never stored
or managed here. JARVIS supplies a user's token; ClayHome supplies its own app
key or nothing at all. OAuth flows, token storage, and user accounts live in
the consuming application.

The first version is entirely keyless.

## Install

```toml
webspec = { path = "../webspec", editable = true }
```

Python 3.12. The upper pin (`<3.13`) matches JARVIS; nothing here requires it.

## Licence

MIT. Platform endpoint notes in `docs/platform-notes.md` are derived from
[Agent-Reach](https://github.com/Panniantong/Agent-Reach) (MIT).
