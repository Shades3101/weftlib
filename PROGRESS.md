# webspec — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** complete — all 6 steps done, both consumers wired

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
- [x] **5. Wire JARVIS** — `jarvis-tools-web`, ADR 0020, 868 tests pass — done 2026-09-15
- [x] **6. Platform notes** — `docs/platform-notes.md` — done 2026-09-15

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**All six steps are complete.** Both consumers run on `webspec`.

| | Tests | Lint / types |
|---|---|---|
| webspec | 102 pass | ruff clean, mypy --strict clean (20 files) |
| ClayHome | 473 pass, 10 skipped | ruff clean |
| JARVIS | 868 pass, 59 skipped | ruff clean, mypy clean, 4/4 import contracts kept |

ClayHome's baseline before any change was 466 — the 7 extra are the new rung-2
escalation tests. JARVIS's was 854; the 14 extra are the new web tools'.

### Step 5: the JARVIS plugin

`plugins/jarvis-tools-web` provides `web.read` (v1.0.0) and `web.search`
(v2.0.0), registered through the same entry-point seam a third party would use.
ADR 0020 records the reasoning. `web.search` replaces
`jarvis_tools_core.WebSearchTool`, whose DuckDuckGo scraping its own comment
already flagged as being answered with a 202 and a JS challenge.

**The ambient-authority scan passes unchanged**, and `lint-imports` keeps all
four contracts including *"Agents have no direct egress — all authority arrives
via ToolContext"*. That is the whole no-I/O design paying off: a library that
opened its own sockets could not have been imported there at all.

Each tool allowlists **one host** — `r.jina.ai` and `searxng` — which is broad
reach through a narrow grant.

### The bug this design nearly introduced

`web.read` asks a third party to fetch a URL. The egress policy only ever sees
`r.jina.ai`, so it *cannot* catch a request to fetch `169.254.169.254` by
proxy — the tool would have been an SSRF laundering service.
`reader_request()` validates the target before building the request, and the
tool returns `web.unsafe_target` with `ExternalState.NOT_APPLICABLE`. Tested
for the metadata endpoint, loopback, internal hostnames and `file://`, each
asserting that **nothing left the process**.

### Step 6: platform notes

`docs/platform-notes.md` — what works per platform, what does not, and why,
with live checks dated. Agent-Reach's endpoint research distilled; its code
deliberately not ported.

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

Stated plainly, because a PROGRESS file that only lists wins is not useful.

- **webspec's own suite still makes no network request.** Every test injects a
  fake resolver or a fixture. The live checks were one-off scripts, recorded
  above but not automated — nothing will catch it when an endpoint's shape
  changes.
- ClayHome and JARVIS are untouched; neither depends on `webspec` yet.
- The name `webspec` is still the placeholder from the plan. Renaming is
  cheapest now, before either consumer imports it.
