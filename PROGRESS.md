# webspec — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** 3 of 6 complete — platform modules, live-verified

> **New session? Read this file first.** It is the source of truth for where the
> build stands. The approved plan lives at
> `~/.claude/plans/or-just-build-it-imperative-sprout.md`.

---

## Status by step

- [x] **1. Repo scaffold** — pyproject, src layout, py.typed, tooling — done 2026-09-15
- [x] **2. Extract from ClayHome** — SSRF guard, URL helpers, neutral DTOs, ports, HTML extraction — done 2026-09-15
- [x] **3. Keyless platform modules** — GitHub, RSS/Atom, YouTube, Reader, SearXNG, Brave — done 2026-09-15
- [ ] **4. Wire ClayHome** — its fetcher becomes a `webspec` transport
- [ ] **4b. Rung 2 browser renderer** — Playwright behind the existing `BrowserProvider` ABC
- [ ] **5. Wire JARVIS** — new `jarvis-tools-web` plugin, `ctx.http` transport, ADR
- [ ] **6. Platform notes** — distil Agent-Reach's endpoint documentation

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**Step 3 is complete and verified.** 102 tests pass; `ruff` and `mypy --strict`
clean across 20 source files. Six platform modules exist, each a
request-builder/response-parser pair with no I/O:

`github` · `rss` (RSS 2.0 + Atom) · `youtube` · `reader` (Jina, rung 1.5) ·
`search.searxng` · `search.brave`

### Verified against the real endpoints, not just fixtures

A one-off script sent the built requests with `urllib` and fed the real
responses back to the parsers:

| Endpoint | Result |
|---|---|
| GitHub repo API | ✅ parsed `astral-sh/ruff` — 49,632 stars, Rust, MIT, topics, rate-limit headers |
| RSS 2.0 (Hacker News) | ✅ 20 entries with correct RFC-822 dates |
| Atom (GitHub Blog) | ✅ 10 entries, alternate link preferred over `rel=self` |
| YouTube oEmbed | ✅ title and author for a real video |
| YouTube watch page | ❌ **HTTP 429 on three consecutive attempts** |

**The YouTube transcript path does not work from this machine.** YouTube blocks
unauthenticated watch-page reads from cloud IP ranges. Metadata via oEmbed is
unaffected.

This is recorded rather than fixed. Getting past it needs cookies, a PO token,
and ongoing maintenance as the checks change — which is `yt-dlp`'s entire job.
**For transcripts at any volume, shell out to yt-dlp.** The module stays for the
case of one transcript from an unblocked IP, and it at least fails loudly: a 429
raises `ParseError` rather than returning an empty tuple, so "blocked" is never
recorded as "this video has no captions".

### A deviation from the plan, deliberately

The plan said to split ClayHome's five paid search providers into request-build
and parse halves. **I did not.** Those providers work and are tested; moving
them now would risk ClayHome regressions to gain nothing this step. Instead
`search/` has SearXNG — the actual gap, since JARVIS's DuckDuckGo scraping is
already blocked — plus Brave, to prove the shape generalises to a keyed backend.
The remaining four can move later, incrementally, if there is ever a reason.

### Two things worth knowing about the code

- **`reader.reader_request()` validates its target before building the URL.**
  Without that it is an SSRF laundering service: the caller's own guard only
  ever sees `r.jina.ai` and would happily pass along a request asking Jina to
  fetch `169.254.169.254` on our behalf. Tested.
- **`searxng.parse_search()` treats an HTML response as a configuration error**,
  not as zero results. JSON output is off by default in SearXNG, and the naive
  reading of that is an empty result set forever.

## Decisions locked

- **No I/O in this library.** It builds request descriptions and parses
  responses; callers execute them. Driven by JARVIS's rule that a tool may only
  reach the network through `ctx.http` and must not import an HTTP client.
  `safety/` resolving DNS is the one deliberate exception.
- **No identity.** Credentials are passed in per call by the caller. OAuth,
  token storage and user accounts belong to the consuming application. The
  first version is entirely keyless, so the credential shape stays undecided
  until the first authenticated platform lands.
- **Extract, do not rewrite.** ClayHome's provider layer is already this
  library; its `core/net.py` SSRF guard resolves DNS and validates the resolved
  addresses, which is stronger than Agent-Reach's literal-IP check.
- **Agent-Reach is a reference, not a dependency.** Its lasting value is the
  platform endpoint notes and the Jina Reader idea (`r.jina.ai` — keyless
  server-side JS rendering, and the only rung JARVIS can reach).

---

## Not yet true

- Nothing has made a real network request through this library. Every test
  injects a fake resolver or a fixture string.
- ClayHome and JARVIS are untouched; neither depends on `webspec` yet.
- The name `webspec` is still the placeholder from the plan. Renaming is
  cheapest now, before either consumer imports it.
