# weft

Web access as pure logic. Builds request descriptions, parses responses,
**performs no I/O**.

```python
from weft.platforms import github

request  = github.repository_request("python", "cpython")  # a description
response = my_http_client.send(request)                    # caller executes
repo     = github.parse_repository(response)               # back to weft
```

`my_http_client` is yours. weft never sends anything, so every call is a pair:
build a request, hand back the response. Adapting an existing client takes
about a dozen lines — `tests/live/conftest.py` does it with `urllib` from the
standard library.

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

The single exception is `weft.safety`, which resolves DNS — that is the
point of an SSRF check. It is a pure function returning a verdict.

## Identity

`weft` owns **none**. Credentials are passed in by the caller, never stored
or managed here. JARVIS supplies a user's token; ClayHome supplies its own app
key or nothing at all. OAuth flows, token storage, and user accounts live in
the consuming application.

Every platform shipped today is keyless. What weft does define is the *shape* a
secret travels in, so the first authenticated platform is not also a design
argument:

```python
from weft.ports import ApiKey, BearerToken
from weft.platforms.search import brave

request = brave.search_request(query, auth=ApiKey(brave.KEY_HEADER, key))
```

`Credential` is a `Protocol`, so a credential type you already have satisfies
it by shape — it needs an `apply(request) -> request` method and no import from
weft. There is no refresh, no expiry, no disk: holding and renewing the secret
stays with the application, because doing otherwise would require weft to
perform I/O.

## Install

weft has no dependency on any HTTP client, async framework or validation
library, which is what lets it drop into an existing project without a version
conflict. Its one runtime dependency is `selectolax`, used by `weft.extract`.

```bash
pip install git+https://github.com/Shades3101/webspec.git
```

```toml
# pyproject.toml — from a checkout next door
weft = { path = "../weft", editable = true }
```

Python 3.12. The upper pin (`<3.13`) matches JARVIS; nothing here requires it.

Importing `weft` gives you the types that cross the seam; platform modules are
imported by path, so a caller that only builds API requests never loads an HTML
parser:

```python
from weft import HttpRequest, SearchRequest, Transport   # dependency-free
from weft.platforms import github, reader, rss, youtube
from weft.platforms.search import brave, searxng
from weft.extract import extract_content                 # pulls in selectolax
```

## Tests

```bash
pytest                      # 161 tests, no network, well under a second
WEFT_LIVE=1 pytest -m live  # real endpoints, opt-in
```

The default suite injects fixtures and fake resolvers, which is what makes it
fast — and also what makes it blind to an endpoint that changed shape. The live
suite exists for that, runs weekly in CI rather than on pull requests, and
skips rather than fails when a key or a self-hosted instance is absent.

## Licence

MIT. Platform endpoint notes in `docs/platform-notes.md` are derived from
[Agent-Reach](https://github.com/Panniantong/Agent-Reach) (MIT).
