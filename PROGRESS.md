# weft — Build Progress

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

**All six steps are complete.** Both consumers run on `weft`.

| | Tests | Lint / types |
|---|---|---|
| weft | 102 pass | ruff clean, mypy --strict clean (20 files) |
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

## Step 7: rename, credential seam, live tests, distribution

Closing the four gaps the previous section listed.

**Renamed `webspec` → `weft`**, done before either consumer imports it, which
was the whole reason to do it now. Package, imports, docs and config; 102 tests
passed before and after.

**A credential seam** (`weft.ports.credentials`). `Credential` is a
`Protocol` with one method, `apply(request) -> request`, so a caller's existing
credential type qualifies by shape without importing weft. Three
implementations ship — `ApiKey`, `BearerToken`, `QueryKey` — with redacted
`repr` that keeps the *length* visible, because the usual credential bug is an
empty value or a trailing newline and a fully masked repr hides both. Brave now
takes either `api_key=` or `auth=`, and raises when given both rather than
silently preferring one.

Deliberately **still keyless**: the shape is decided, no new authenticated
platform shipped. There is no refresh, no expiry, no disk — all of which would
require I/O.

**A live suite** (`tests/live/`), opt-in twice over: the `live` marker is
deselected by default *and* `WEFT_LIVE=1` must be set. Its transport is
`urllib` from the standard library — a live suite that reached for httpx would
quietly weaken "works with any client" into "works with the one we tested".
Runs weekly in CI, never on pull requests.

**It found a real bug on its first run.** YouTube answers a refused caption
fetch with **200 and a zero-length body**, on a video whose tracks the watch
page had *just* listed. weft reported that as `ParseError: did not return valid
JSON`, sending you hunting for a parser bug that was never there. It now names
the condition — an IP-based block, needing different egress — and the
fixture-based suite covers it. This is exactly the class of breakage the old
"Not yet true" entry predicted, and it took one run to surface.

**Distribution.** `import weft` exports the seam types and pulls in no HTTP
client and no `selectolax`, asserted in a subprocess by `tests/test_public_api.py`
so it cannot rot. A CI job builds the wheel, installs it into a clean venv and
imports it from outside the source tree — the claim the README makes, checked
rather than asserted. The public name list is pinned, so an accidental rename
breaks here instead of in a consumer's build.

161 tests, ruff and mypy clean across `src` and `tests`.

## Not yet true

Stated plainly, because a PROGRESS file that only lists wins is not useful.

- **The rename broke both consumers, and they are not yet repaired.** The
  previous "Not yet true" entry claimed neither depended on this library. That
  was stale: ClayHome imports it in 6 places via `path = "../webspec"`, and
  JARVIS in 6 more via a pinned git rev. Both still say `webspec`.
  JARVIS is pinned to `1d13ff0` so it keeps working until someone bumps the
  rev; ClayHome breaks on its next install. Renaming *was* right to do before
  wider adoption, but it was not free, and the repair is outstanding.
- **The live suite cannot see what it is blocked from.** YouTube transcripts
  skip from this machine and will skip from GitHub Actions too — datacentre IPs
  are exactly what YouTube refuses. The weekly run therefore proves less about
  that path than about the others, and a skip is easy to stop reading.
- **Brave and SearXNG go unchecked in CI** without a key and a reachable
  instance. Both skip cleanly, which is honest, but an untested parser is
  untested however politely it declines.
- **The repository is still called `webspec`** on GitHub, though the package is
  `weft`. Cosmetic, and cheap to fix, but confusing until it is.
