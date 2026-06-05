# Architecture & hard-won gotchas

The design that makes this work, and the dozen non-obvious things that each cost real
debugging time. Read this before porting — most of it is invisible until it bites.

---

## 1. One common schema for every source

Both fetchers shape every market into the **same dict**, so the aggregator never cares
which venue it came from. This is what makes "add a third source" a one-file change.

```python
{
  "question": str,            # English title (the precise source of truth)
  "question_zh": str | None,  # optional translation (helper, filled later)
  "topic": str,               # module key from the taxonomy
  "outcomes": [str, str],     # ["Yes","No"] or for multi-leg, [pick_label, "No"]
  "prices": [float, float],
  "prob_yes": float | None,   # 0–1 — the headline probability
  "pick_label": str | None,   # which bracket/threshold the prob refers to (multi-leg only)
  "change_24h": float | None, # probability points
  "volume_24h": float | None, # for ranking/caps
  "end_date": str | None,
  "slug": str | None,         # for the public link
  "token_id_yes": str | None, # Polymarket only → enables the trend chart
  "source": "polymarket" | "kalshi",
}
```

## 2. Classification — keyword-first, native-category fallback

`market_taxonomy.classify(question, kalshi_category=None)`:
- An ordered keyword check runs **highest-signal-first** so overlaps resolve sanely:
  geopolitics **before** elections (so "Iran nuclear deal" → 地缘, not 政治 via "Iran"…),
  crypto before indices (bitcoin → 加密, not 股指 via "stock"), monetary before macro
  (fed rate → 货币政策, not 宏观 via generic econ words).
- If no keyword hits, fall back to Kalshi's native `category` (Polymarket has none).
- Special guards learned the hard way:
  - **World Cup / FIFA → sports, checked FIRST** — otherwise "Will Iran win the World Cup?"
    lands in 地缘 via "iran". Any country-named sports market needs this.
  - **`" gold"` matched "Golden Knights"** (a hockey team) → 股指大宗. Use `"gold "` / `"gold price"`,
    not bare `" gold"`. Watch every short keyword for substring collisions.

Modules split into `CORE_MODULES` (shown expanded) and `REFERENCE_MODULES` (sports / crypto /
entertainment — folded into a collapsed group so ball games don't drown the macro signal).
`MODULE_CAPS` limits each module to its top-N by 24h volume (Kalshi floods otherwise — a
single "LA mayor" event spawns dozens of derivative markets; gas/weather spawn daily ones).

## 3. Snapshot model — normal loads must be instant

A fresh pull + translate takes seconds to **minutes**. Opening the page should never wait.
So the aggregator **pins the finished result to a JSON file on disk**. Normal loads read
that snapshot (no network, no LLM, survives restart). Only an explicit refresh re-pulls.
Same pattern in each source fetcher (their own snapshot) and in `market_pulse` (the merged
overview snapshot). `_load_snapshot` reads the file on every call, so an out-of-band rebuild
is picked up immediately with no restart.

## 4. Async refresh — the slow pull must NOT block

**Why**: Kalshi has no volume-sort, so to find the hot markets you must pull the *entire*
open event book (~7000 events, ~35 pages, 2–16s each) = **1–8 minutes**. A synchronous
refresh endpoint times out and feels broken.

**How** (`market_pulse.fetch_overview(force=True)`):
1. Return the **current snapshot immediately** with `"updating": true`.
2. Kick off the rebuild in a background task (`asyncio.create_task`), guarded by a module-level
   `_rebuilding` flag so refreshes don't pile up.
3. The frontend sees `updating`, then **polls** `/pulse/overview` every ~20s until `as_of`
   advances (cap the poll window at ~8 min for the slow first build).
4. Cold start with no snapshot builds synchronously (nothing else to show).

## 5. Translation (optional) — and the rate-limit trap

Titles are translated once and cached forever by English text (stable keys), so only brand-new
titles ever cost time. Two traps:
- **Reasoning models return empty on big batches** → keep batches small (4) with enough
  `max_tokens` for reasoning + JSON.
- **Bursting all batches back-to-back trips the provider's rate limit** — works in isolation,
  fails under burst, leaving most titles untranslated. Fix: a **small delay (~0.8s) between
  batches** + **multi-round retry** that stops only after *two consecutive* no-progress rounds
  (so one transient rate-limited round doesn't abort the sweep). Save the cache after every
  batch so partial progress survives a timeout. Because refresh is async, give translation a
  generous timeout (e.g. 300s) and let it finish before pinning.
- If your audience reads English, **delete translation entirely** — it's pure helper.

## 6. ⚠️ Robustness — a failed pull must NEVER overwrite good data

The single worst bug we hit: Kalshi's edge had a transient outage (`HTTP 000` / `SSLEOFError`),
the pull returned empty, and the code **saved the empty result over the good snapshot** — one
refresh wiped the entire Kalshi source from the panel. Two rules, both non-negotiable:
1. **Retry each page** a few times with backoff before giving up (transient TLS blips are common).
2. **If a pull yields zero rows, do NOT save — return the previous snapshot instead.** Never let
   "the API was briefly down" turn into "we deleted the data." Apply this to *every*
   pull→persist path.

## 7. Multi-leg / scalar events — show WHICH bracket the % means

(See `apis.md` → "scalar / multi-leg events".) A scalar event (gas/oil/BTC/temp/CPI) is dozens
of "Above $X" legs. Collapsing to one number without a label produces "gas: 2%" which is
meaningless. Pick the **leg nearest 50%** (the market-implied level / median) and surface its
label as `pick_label`. The UI shows it as e.g. "档位 · Above $4.20（market line）" so 53% reads
as "53% chance gas is above $4.20." Single-leg binary events get no label (self-describing).

## 8. Frontend plumbing

- **Path-prefix proxy trap**: if the panel *page* and its *API* share a prefix (e.g. a page at
  `/polymarket` and APIs under it), a naive dev-proxy swallows the browser navigation and 404s.
  Use an "HTML fallback" proxy: serve `index.html` when `Accept: text/html`, otherwise proxy to
  the backend. (Pure-API prefixes like `/pulse` need only a plain proxy.)
- **EN primary, CN secondary**: show the **English title on top (bold), translation below
  (muted)**. Translations lose precision ("5月CPI" hides the direction/threshold); the English
  is the source of truth, the translation is a glance aid. Don't make the translation primary.
- Module sections with source badges (color-code Polymarket vs Kalshi), a collapsed reference
  group, A-share red=up/green=down (flip for Western audiences), and a trend chart for
  Polymarket rows (Kalshi rows show the snapshot probability).

## 9. Gotcha checklist (paste-ready memory)

- [ ] Polymarket `outcomes`/`outcomePrices`/`clobTokenIds` are **JSON strings** — parse them.
- [ ] Kalshi prices are **`*_dollars`** now (cents fields return None). Re-verify field names.
- [ ] Kalshi has **no volume sort** and a **broken `category` filter**; `series_ticker` works.
- [ ] Kalshi full-book pull is **slow (1–8 min)** → refresh must be **async**.
- [ ] Kalshi edge is **flaky** → retry pages; **empty pull never overwrites** the snapshot.
- [ ] Multi-leg events → pick the **nearest-50%** leg and show its **label**.
- [ ] World Cup/FIFA → sports first; watch short keywords (`gold`) for substring collisions.
- [ ] Translation: small batches + inter-batch delay + multi-round + cache-after-each.
- [ ] Snapshot on disk → instant normal loads; read file per request (no restart needed).
- [ ] It's a **thermometer, not a trading tool** — frame it that way everywhere.
```
