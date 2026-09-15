# webspec — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** 4 of 6 complete — ClayHome wired, zero regressions

> **New session? Read this file first.** It is the source of truth for where the
> build stands. The approved plan lives at
> `~/.claude/plans/or-just-build-it-imperative-sprout.md`.

---

## Status by step

- [x] **1. Repo scaffold** — pyproject, src layout, py.typed, tooling — done 2026-09-15
- [x] **2. Extract from ClayHome** — SSRF guard, URL helpers, neutral DTOs, ports, HTML extraction — done 2026-09-15
- [x] **3. Keyless platform modules** — GitHub, RSS/Atom, YouTube, Reader, SearXNG, Brave — done 2026-09-15
- [x] **4. Wire ClayHome** — generic logic delegated, 466 tests unchanged — done 2026-09-15
- [ ] **4b. Rung 2 browser renderer** — Playwright behind the existing `BrowserProvider` ABC
- [ ] **5. Wire JARVIS** — new `jarvis-tools-web` plugin, `ctx.http` transport, ADR
- [ ] **6. Platform notes** — distil Agent-Reach's endpoint documentation

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**Step 4 is complete and verified.** ClayHome depends on `webspec` and runs its
code in production paths. **466 passed, 10 skipped — byte-identical to the
baseline taken before any change.** ruff clean across `packages/` and `apps/`.
Net effect on ClayHome: **210 lines deleted, 90 added.**

Confirmed by introspection rather than assumption — `normalize_url`, `url_hash`,
`host_of`, `root_url` and `is_public_address` all resolve to `webspec.safety.*`,
and the fetcher's `_extract` calls `webspec.extract.extract_content`.

### A baseline worth recording

The first run of ClayHome's suite gave 364 passed with **102 errors**. Those
were not regressions: its Postgres was simply not running. Starting
`clayhome-postgres-1` and `clayhome-redis-1` gave the true baseline of 466
passed, and every later comparison used that. Comparing against the broken run
would have hidden real breakage in the noise.

### What deliberately did *not* move

- **`resolve_public_target` stays async in ClayHome.** webspec's is sync, and
  calling it from the fetcher would block the event loop on every DNS lookup —
  a genuine regression under concurrency that no test would have caught. Only
  the pure parts (`validate_url_shape`, `is_public_address`) are shared.
- **`registrable_domain`, `is_aggregator`, `is_plausible_company_domain`,
  `same_site`** stay local: they need `tldextract` plus curated aggregator and
  free-mail lists, which is prospecting knowledge.
- **The `allow_private` escape hatch** stays, mapped onto webspec's named-host
  allowlist.

### ClayHome gained something

Legacy IPv4 literals — `127.1`, `0x7f000001`, `2130706433`, `0xA9FEA9FE` — are
now rejected at parse time. Previously they were caught only because DNS
resolution returned a private address.

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
