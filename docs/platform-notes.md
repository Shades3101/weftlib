# Platform notes

What actually works per platform, and what does not. Distilled from
[Agent-Reach](https://github.com/Panniantong/Agent-Reach) (MIT), from reading
each platform's behaviour, and from live checks — those are marked ✅ / ❌ and
dated, because this kind of knowledge goes stale. It did: the 2026-09-22
recheck contradicted the YouTube entry below within a week of writing it.

Those checks are now automated as `tests/live/`, run weekly in CI rather than
by hand. A dated note in a file is a claim; a test that runs is a claim that
keeps being checked.

Agent-Reach's endpoint research is the main thing worth keeping from it. Its
code is not: it is an installer for 13 third-party CLIs, and its SSRF guard is
weaker than the one in `weft.safety` (literal-IP parsing only, no DNS).

---

## Implemented in weft

### Generic web pages

Three rungs, cheapest first. `weft.extract.should_escalate` decides between
them; it escalates on a JavaScript shell or a bot challenge and on nothing else.

| Rung | Method | Cost | Notes |
|---|---|---|---|
| 1 | Plain HTTP | 1x | Fine for most of the web |
| 1.5 | `https://r.jina.ai/<url>` | ~10x | Renders JS server-side, returns markdown, keyless. **Your URL and its content pass through a third party.** Rate-limited without a key |
| 2 | Headless browser | ~100x | ClayHome only — a JARVIS tool cannot drive one |

Jina Reader answers **200 with an explanatory body** when the upstream page
blocked *it*. Parsed naively that is a successful fetch of nothing.
`weft.platforms.reader.parse_reader` detects it and returns an error.

### GitHub — ✅ live-verified 2026-09-15

`https://api.github.com`, keyless. Parsed `astral-sh/ruff` correctly: stars,
language, topics, licence, timestamps.

**The real constraint is 60 requests/hour/IP unauthenticated** (5,000 with a
token). `github.rate_limit_of()` reads the budget from *any* response,
including a 403 — which is exactly when it is needed. `remaining=None` means
unknown, `0` means exhausted; conflating them causes a permanent false backoff.

### RSS / Atom — ✅ live-verified 2026-09-15

Both formats, via stdlib `xml.etree` rather than `feedparser` — it will not
resolve external entities, so a hostile feed cannot make the parser read a
local file.

Atom puts the URL in an attribute and often offers several; prefer
`rel="alternate"` over `rel="self"`, or you get the feed's own address instead
of the article's.

### Search

| Backend | Key | Notes |
|---|---|---|
| SearXNG | none | Self-hosted, aggregates many engines behind **one host** — the reason it suits a sandbox allowlist. **JSON output is off by default**: add `json` to `search.formats`. Inherits upstream engines' rate limits at volume |
| Brave | free tier, 2k/month | Caps a page at 20 results. Key goes in a header, never the URL |

ClayHome additionally has Tavily, Exa, Serper and SerpAPI wired in its own
provider layer.

---

## Known-hard platforms

### YouTube — ❌ transcripts blocked, ✅ metadata works (rechecked 2026-09-22)

- **oEmbed** (`/oembed`) — stable, documented, keyless. Title, author,
  thumbnail. Works.
- **Watch page** — parsed cleanly on 2026-09-22 and listed both caption tracks
  for `jNQXAC9IVRw`. The 429s seen on 2026-09-15 were not reproduced, so the
  block is intermittent or IP-dependent rather than absolute.
- **Transcripts** — blocked, but **not** in the way the 2026-09-15 note
  assumed. The `timedtext` endpoint answers **HTTP 200 with a zero-length
  body** for a track the watch page has just listed. Listing a track and being
  served it are separate permissions, and the refusal carries a success status.

  This matters because a 200 is the one response a parser is least suspicious
  of. weft reported it as `ParseError: did not return valid JSON`, which sends
  you looking for a parser bug that does not exist; it now names the condition
  and says the caller needs different egress. Found by the live suite on its
  first run — precisely the drift a fixture cannot see.

Getting past that needs cookies, a PO token, and continuous maintenance as the
checks change — which is `yt-dlp`'s entire job. **For transcripts at any
volume, shell out to yt-dlp.** weft's module exists for one transcript from
an unblocked IP; it fails loudly (a 429 raises rather than returning an empty
tuple) so "blocked" is never recorded as "no captions".

The live suite skips rather than fails on the empty body: it is a fact about
the machine's egress, not a regression in weft. CI runs from a datacentre IP,
so that check will keep skipping there.

### LinkedIn — not implemented, deliberately

No keyless or cheap-key path exists. Scraping means ToS violation, fast IP
bans, and a litigation history. For contact data at volume the answer is a
licensed provider — Apollo, Hunter, People Data Labs — which is why ClayHome's
`EnrichmentProvider` is vendor-neutral and says so.

### Reddit — not implemented

The `.json` suffix on any URL still works but is heavily rate-limited and
blocks datacenter IPs, so it fails in production. The official OAuth app has a
free tier and is the supportable route.

Note if you ever add `rdt-cli`: it saves **every** `.reddit.com` cookie to
`~/.config/rdt-cli/credential.json`, and silently re-reads the browser every 7
days.

### Twitter/X, Instagram, Facebook — not implemented

All require an authenticated session. The X API is expensive; the Meta
platforms need app review. Agent-Reach reaches them through browser automation
against your own logged-in Chrome, which is viable for personal use and not for
a product.

---

## Recurring lessons

**"Blocked" and "empty" are different facts.** Almost every failure in this
area presents as a successful, empty response: a Cloudflare interstitial with a
2xx, a JS shell, SearXNG returning HTML, a DuckDuckGo 202 challenge. Collapse
the two and a pipeline reports clean empty answers forever, and nothing alerts.
Every parser here distinguishes them.

**Escalate on a signature, never on failure.** An honest 404 is an answer; a
browser will reproduce it at a hundred times the price.

**A reader service can launder an SSRF.** Asking a third party to fetch a URL
means your own egress policy only sees *that third party*. Validate the target
before handing it over — `reader_request()` does, and refuses.
