# webspec — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** 2 of 6 complete — safety, ports and extraction

> **New session? Read this file first.** It is the source of truth for where the
> build stands. The approved plan lives at
> `~/.claude/plans/or-just-build-it-imperative-sprout.md`.

---

## Status by step

- [x] **1. Repo scaffold** — pyproject, src layout, py.typed, tooling — done 2026-09-15
- [x] **2. Extract from ClayHome** — SSRF guard, URL helpers, neutral DTOs, ports, HTML extraction — done 2026-09-15
- [ ] **3. Keyless platform modules** — YouTube, RSS, GitHub, SearXNG search
- [ ] **4. Wire ClayHome** — its fetcher becomes a `webspec` transport
- [ ] **4b. Rung 2 browser renderer** — Playwright behind the existing `BrowserProvider` ABC
- [ ] **5. Wire JARVIS** — new `jarvis-tools-web` plugin, `ctx.http` transport, ADR
- [ ] **6. Platform notes** — distil Agent-Reach's endpoint documentation

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**Step 2 is complete and verified.** 55 tests pass; `ruff` and `mypy --strict`
are clean across 12 source files.

What now exists, all of it pure logic with no I/O:

- `safety/ssrf.py` — the guard, ported from ClayHome `core/net.py`. Rejects
  non-HTTP schemes, URL credentials, odd ports, every private/loopback/
  link-local/reserved literal, named internal hosts, and — after DNS — any host
  where *any* resolved address is non-public.
- `safety/urls.py` — `normalize_url`, `url_hash`, `host_of`, `root_url`.
- `ports/dto.py` — `HttpRequest`, `HttpResponse`, `FetchedPage`, `SearchRequest`,
  `SearchHit`, `SearchResponse`, `FetchMethod`.
- `ports/protocols.py` — `Transport`, `AsyncTransport`, `Renderer`, `Cache`,
  as `Protocol`s so an existing class satisfies them by shape.
- `extract/html.py` — title, readable text, declared language via selectolax.
- `extract/antibot.py` — challenge-page detection.
- `extract/escalation.py` — `should_escalate()`, the decision to pay for a
  higher rung.

### Three deliberate improvements on the source material

1. **Legacy IPv4 literals are rejected without DNS.** ClayHome catches `127.1`,
   `0x7f000001` and `2130706433` only because resolution returns 127.0.0.1;
   webspec also parses them with `inet_aton` at shape-check time, which is what
   Agent-Reach's weaker guard did better. Both paths now hold.
2. **The internal-endpoint exemption is a host allowlist, not a boolean.**
   ClayHome has `fetch_allow_private_networks`, which its own
   `validate_runtime()` refuses to allow in production — correctly, because it
   disables the guard wholesale. webspec takes named hosts instead, so a
   self-hosted SearXNG is reachable while everything else stays guarded. Tested
   explicitly: the exemption does not leak to `127.0.0.1` or to
   `metadata.google.internal`, and it still enforces scheme and credential
   rules.
3. **The escalation decision is extracted and unit-tested.** It refuses to
   escalate on an honest 404 or a transport error, and distinguishes a
   JavaScript shell (little text, many bytes) from a genuinely small page.

### One boundary drawn differently from the plan

The plan said to port `core/urls.py`. Its public-suffix helpers —
`registrable_domain`, `is_aggregator`, `is_plausible_company_domain`,
`same_site` — **stayed in ClayHome**. They need `tldextract` plus curated lists
of aggregator and free-mail domains, which is prospecting knowledge rather than
web access. Porting them would have added a dependency to a package that
otherwise needs none, and put ClayHome's business rules in a shared library.

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
