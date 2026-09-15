# webspec — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** 4b of 6 complete — rung 2 live-proven

> **New session? Read this file first.** It is the source of truth for where the
> build stands. The approved plan lives at
> `~/.claude/plans/or-just-build-it-imperative-sprout.md`.

---

## Status by step

- [x] **1. Repo scaffold** — pyproject, src layout, py.typed, tooling — done 2026-09-15
- [x] **2. Extract from ClayHome** — SSRF guard, URL helpers, neutral DTOs, ports, HTML extraction — done 2026-09-15
- [x] **3. Keyless platform modules** — GitHub, RSS/Atom, YouTube, Reader, SearXNG, Brave — done 2026-09-15
- [x] **4. Wire ClayHome** — generic logic delegated, 466 tests unchanged — done 2026-09-15
- [x] **4b. Rung 2 browser renderer** — Playwright, escalation wired, live-proven — done 2026-09-15
- [ ] **5. Wire JARVIS** — new `jarvis-tools-web` plugin, `ctx.http` transport, ADR
- [ ] **6. Platform notes** — distil Agent-Reach's endpoint documentation

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**Step 4b is complete and live-proven.** ClayHome: **473 passed, 10 skipped**
(466 baseline + 7 new). ruff clean.

`PlaywrightBrowserProvider` fills the `BrowserProvider` slot that had been
declared-but-empty since ClayHome's M3, and `HttpPageFetcher._maybe_escalate`
consults `webspec.extract.should_escalate` after each HTTP attempt.

### Proven against a real browser, not fixtures

A local JS-only fixture page, served over loopback:

| | Result |
|---|---|
| Rung 1 (HTTP) | **0 characters** of text from 6,666 bytes |
| `should_escalate` | `True` — reason `empty_body` |
| Rung 2 (Chromium) | **481 characters**, title parsed, heading present |

### Guards at this rung

- **The SSRF check runs again inside `render()`.** A browser follows redirects
  the first check never saw. Tested: a metadata-endpoint URL is refused and no
  browser is ever launched.
- **The size cap moves to the rendered result** — there is no wire to enforce
  it on at this rung.
- **Concurrency is bounded separately** by a new `browser_max_concurrency`
  setting. Browsers are memory-bound; the limit that keeps HTTP healthy will
  exhaust a machine here.
- **A failed render keeps the HTTP result**, so a timeout cannot lose the
  status already obtained.
- `image`, `media` and `font` requests are aborted — bandwidth for no text.

### The test that matters most

`test_good_page_is_not_escalated` asserts on **browser launch count**, not on
output. A pipeline that renders every page passes every pass/fail test and is
ruinous at volume; the only way that regression is visible is by counting
launches.

### A misreading worth recording

`ResearchBudget.max_browser_sessions` already existed and looked like a
concurrency limit. It is not — it is how many renders one research *job* may
spend, enforced at call sites by the budget service. Reusing it would have
conflated a per-job quota with a process-wide concurrency bound. Hence the new,
separately-named setting.

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
