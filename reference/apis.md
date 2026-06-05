# Prediction Market APIs — verified reference

> Everything here was verified against the live APIs in **2026-06**. These APIs change
> (field names have already changed once — see Kalshi). **Re-verify with a quick curl
> before trusting any field.** All read endpoints below are public, no auth, no account.

---

## Polymarket

Crypto-settled, real money. Deepest on geopolitics, elections, crypto, sports.

### Gamma API — markets + current probability + metadata
```
GET https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100&offset=0&order=volume24hr&ascending=false
```
- Returns a JSON **array** of markets. Supports `order=volume24hr` (server-side volume sort ✅),
  `limit` capped at 100/page → paginate with `offset` (0,100,200…).
- Key fields per market:

| field | meaning | example |
|---|---|---|
| `question` | the market question | "Fed decision in June?" |
| `outcomes` | JSON-**string** array | `"[\"Yes\",\"No\"]"` |
| `outcomePrices` | JSON-**string** array — **this is the probability** (0–1) | `"[\"0.62\",\"0.38\"]"` → Yes 62% |
| `volume24hr` | 24h volume (sort/rank by this) | `54098308` |
| `liquidity` | liquidity | |
| `clobTokenIds` | JSON-string array; **first element = Yes token id**, needed for history | `"[\"4366...\",\"3672...\"]"` |
| `oneDayPriceChange` / `oneWeekPriceChange` | 24h / 7d change in probability (points) | `0.013` |
| `slug` | for the public URL `polymarket.com/event/<slug>` | |
| `endDateIso` / `endDate` | resolution date | |

- ⚠️ `outcomes`, `outcomePrices`, `clobTokenIds` come back as **JSON-encoded strings**, not
  arrays — `json.loads()` them (see `_parse_json_field` in `polymarket_signals.py`).

### Events grouping (optional)
```
GET https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100&order=volume24hr&ascending=false
```
Groups related markets under one event (`title`, `volume24hr`, nested `markets[]`). The
reference code pulls at the **market** level (each row = one specific bracket question,
which is what you want), not events.

### CLOB API — probability history (trend chart) + live mid
```
GET https://clob.polymarket.com/prices-history?market=<clobTokenIds[0]>&interval=1w&fidelity=720
   → { "history": [ {"t": <unix>, "p": <prob 0-1>}, ... ] }
GET https://clob.polymarket.com/midpoint?token_id=<id>
```
- `market=` takes the **token id** (first of `clobTokenIds`), not the market id.
- `interval`: `1d` / `1w` / `1m` / `max`.

---

## Kalshi

US CFTC-regulated, real money. Strongest on **macro economics** (Fed/CPI/jobs/recession),
commodities, and US elections. Public market data needs no key (only trading does).

Base: `https://api.elections.kalshi.com/trade-api/v2`

### ⚠️⚠️ Field names were renamed to `*_dollars` (2026-06)
The old cents-based fields (`last_price`, `yes_bid`, `yes_ask`) now return **None**. Use:
- `yes_ask_dollars`, `yes_bid_dollars`, `no_bid_dollars`, `no_ask_dollars`
- `last_price_dollars`, `previous_price_dollars`, `previous_yes_ask_dollars`
- `volume_fp` (total), `volume_24h_fp` (24h — often the string `"0.00"`), `liquidity_dollars`, `open_interest_fp`

Values are dollars 0–1 = probability. `yes_ask_dollars: "0.6740"` → 67.4%.
**This rename already broke us once. Re-check field names before trusting them.**

### Markets endpoint
```
GET .../markets?limit=200&status=open[&series_ticker=KXFED]
   → { "markets": [...], "cursor": "..." }
```
- ⚠️ **No server-side volume sort.** No `order_by`/`sort`/`min_volume` — they're silently
  ignored. Default order buries hot markets behind thousands of dead single-day sports
  contracts. You cannot ask Kalshi for "top markets by volume."
- `series_ticker=` filter **works and is fast** (~2s). `category=` filter is **broken**
  (returns everything regardless).

### Events endpoint (what the reference code uses)
```
GET .../events?limit=200&status=open&with_nested_markets=true[&cursor=...]
   → { "events": [...], "cursor": "..." }
```
- Each event carries a native **`category`** (Economics, Financials, Commodities, Companies,
  Elections, Politics, World, Crypto, Sports, Entertainment, Climate and Weather, Health,
  Social, Transportation, Science and Technology, Mentions) — use it to seed classification.
- `with_nested_markets=true` embeds the event's markets (with the `*_dollars` prices + volume).
- `mutually_exclusive` field exists but is unreliable for detecting scalar events — detect
  "multi-leg" simply by `len(markets) > 1`.
- ⚠️ **Slow + heavy**: 200 events with nested markets is a large payload — **~2s to ~16s per
  page** depending on Kalshi load, and the full open book is ~35 pages (~7000 events). A full
  pull can take **1–8 minutes**. This is why refresh must be async (see architecture.md).
- ⚠️ **Flaky edge**: intermittent `HTTP 000` / `SSLEOFError` / whole-API outages. Retry each
  page; never let a failed pull overwrite good cached data (see architecture.md).

### History (trend chart)
Kalshi candlesticks need `series_ticker` + market `ticker` + a `start_ts`/`end_ts` range and
are fiddly. The reference code gives Polymarket rows a trend chart and skips Kalshi trends
(Kalshi rows show the snapshot probability only). Add later if needed.

### Scalar / multi-leg events (CRITICAL for sane display)
Many Kalshi markets are **scalar** — one underlying value (gas price, oil, BTC price,
temperature, CPI) split into 10–40 threshold legs, each a Yes/No:

| leg (`yes_sub_title`) | `yes_ask_dollars` |
|---|---|
| Above $4.10 | 0.95 |
| **Above $4.20** | **0.53** ← nearest 50% |
| Above $4.30 | 0.08 |

A bare event-level number is meaningless ("gas: 2%" — 2% of *what*?). The reference code
collapses a multi-leg event to the **leg whose probability is nearest 50%** — the
market-implied level / median ("53% chance gas is above $4.20") — and surfaces that leg's
label (`pick_label`) so the UI can show what the % refers to. Single-leg binary events
(Recession? Fed decision?) are self-describing and get no label.

---

## Other venues (evaluated, mostly not worth it)

| venue | public API? | verdict |
|---|---|---|
| **Manifold** | ✅ `api.manifold.markets/v0/markets` (`probability` field, fully open) | play-money → noisy signal; use only as a supplement |
| **Metaculus** | has API but `403` Cloudflare-blocks server/curl | forecaster community (not money); needs browser/UA workaround |
| **PredictIt** | `403` Cloudflare + platform in decline | skip |

**Bottom line: Polymarket + Kalshi are the two free, no-auth, money-backed sources worth
building on.** They're complementary — Polymarket for geopolitics/crypto/elections depth,
Kalshi for clean macro-economics structure.
