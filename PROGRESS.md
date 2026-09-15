# webcore — Build Progress

**Last updated:** 2026-09-15 · **Current phase:** 1 of 6 complete — scaffold verified

> **New session? Read this file first.** It is the source of truth for where the
> build stands. The approved plan lives at
> `~/.claude/plans/or-just-build-it-imperative-sprout.md`.

---

## Status by step

- [x] **1. Repo scaffold** — pyproject, src layout, py.typed, tooling — done 2026-09-15
- [ ] **2. Extract from ClayHome** — SSRF guard, URL helpers, neutral DTOs, ports, HTML extraction
- [ ] **3. Keyless platform modules** — YouTube, RSS, GitHub, SearXNG search
- [ ] **4. Wire ClayHome** — its fetcher becomes a `webcore` transport
- [ ] **4b. Rung 2 browser renderer** — Playwright behind the existing `BrowserProvider` ABC
- [ ] **5. Wire JARVIS** — new `jarvis-tools-web` plugin, `ctx.http` transport, ADR
- [ ] **6. Platform notes** — distil Agent-Reach's endpoint documentation

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Right now

**Step 1 is complete and verified.** The package installs editable into a clean
3.12 venv, imports, ships `py.typed`, and builds a wheel containing it. `ruff`
passes and `mypy --strict` reports no issues across 5 source files.

What exists is scaffold only: `ports/`, `safety/`, `extract/` and `platforms/`
are documented, importable, and **empty of behaviour**. No request has ever been
built and no response has ever been parsed. That is step 2 onward.

One deviation from the plan worth recording: the plan said "stdlib + selectolax
only", and that holds, but the system default interpreter here is 3.14.7 while
the project pins `>=3.12,<3.13` to match JARVIS. The venv is built explicitly
with `python3.12` (uv-managed, 3.12.14 — the same version JARVIS runs). A plain
`python3 -m venv` will fail the requires-python check, correctly.

---

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

- Nothing has made a real network request through this library.
- ClayHome and JARVIS are untouched; neither depends on `webcore` yet.
- The name `webcore` is still the placeholder from the plan. Renaming is
  cheapest now, before either consumer imports it.
