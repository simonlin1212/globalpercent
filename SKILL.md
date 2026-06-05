---
name: global-percent
description: >-
  GlobalPercent — build a global-macro-probability panel for an investment research
  system. Merges public probability data from prediction markets (Polymarket + Kalshi),
  classifies every market into macro modules (monetary policy / macro economy / AI /
  etc.), and shows the whole market's expected-probability state at a glance as a
  sentiment/risk overlay (not a trading signal). Use when building a macro-probability
  or "event probability" dashboard, or wiring Polymarket/Kalshi APIs. Includes verified
  API details, the full architecture, hard-won gotchas, and adaptable reference code
  (Python backend + React panel).
---

> 📦 项目主页：https://github.com/simonlin1212/global-percent — 更新、反馈、支持作者
>
> 作者：Simon 林 · 抖音「Simon林」· 公众号「硅基世纪」

# GlobalPercent — a global-macro-probability panel for your research system

This skill packages everything needed to build a panel that reads **prediction-market
probabilities** from **Polymarket + Kalshi** (both public, read-only, no account) and
presents them as a **macro sentiment thermometer** grouped by module.

It is NOT a single API call. The value is in the *system*: classification, dedup,
multi-source merge, snapshot caching, async refresh, translation, and a dozen
non-obvious gotchas that each cost real debugging time. All of that is captured here
so you don't rediscover it.

## The one idea

A prediction market's **price IS a probability**. A contract trading at $0.62 means the
market collectively bets 62% the event happens. Reading those numbers is free, needs no
wallet or account — only *trading* does. So you can pull a global, money-backed sentiment
read on Fed decisions, geopolitics, AI milestones, etc. for zero cost.

**Use it as a thermometer, not a trading tool.** 70–84% of prediction-market traders lose
money; the edge belongs to HFT market-makers, not "AI that predicts well." Frame the panel
as *"what is the market's mood?"*, never as a buy/sell signal.

## When to use this skill

- Building an "event probability" / "sentiment" / "macro mood" dashboard panel
- Integrating Polymarket or Kalshi probability data into any app
- Anyone asks for prediction-market odds, election/Fed/geopolitics probabilities as data

## What you're building (architecture in one breath)

```
Polymarket Gamma API ─┐
                      ├─► per-source fetchers shape every market into ONE common schema
Kalshi events API ────┘        (question, prob_yes, change_24h, volume_24h, source, …)
                                          │
                          shared taxonomy classifies each into a module
                          (货币政策/宏观/地缘/政治/股指大宗/AI + reference group)
                                          │
                          aggregator: merge → group by module → cap floods →
                          translate titles → pin a disk SNAPSHOT
                                          │
                          /pulse/overview  (instant from snapshot; refresh = async rebuild)
                                          │
                          React panel: module sections + source badges + trend chart
```

## Build workflow

Follow in order. Read the two reference files first — they hold the details this overview
compresses.

1. **Read `reference/apis.md`** — exact endpoints, field names, and every API gotcha
   (Kalshi's `*_dollars` field rename, no volume-sort, broken `category` filter, etc.).
   *Verify the endpoints live before coding — these APIs change.*
2. **Read `reference/architecture.md`** — the design decisions and the hard-won gotchas
   (async refresh, translation rate-limiting, empty-pull-never-overwrite, multi-leg events).
3. **Port the backend** from `code/backend/` into your stack:
   - `market_taxonomy.py` — module list + keyword classifier (source-agnostic). Tune keywords.
   - `polymarket_signals.py` — Polymarket Gamma/CLOB fetch + shape + snapshot.
   - `kalshi_signals.py` — Kalshi events fetch + shape + snapshot (note the retry/empty-guard).
   - `polymarket_translate.py` — optional title translation (swap in your LLM client).
   - `market_pulse.py` — the aggregator + async-refresh snapshot model. This is the core.
   - `api_routes.py` — FastAPI routes (`/pulse/overview`, `/polymarket/history`).
4. **Port the frontend** from `code/frontend/`:
   - `EventProbabilityPanel.tsx` — module sections, source badges, EN-primary/CN-secondary
     titles, multi-leg "档位 (market line)" chips, collapsed reference group, async-refresh poll.
   - `ProbabilityTrend.tsx` — echarts line chart (swap for your chart lib if needed).
5. **Wire the proxy/route** so the panel page and its API share a path prefix without the
   browser navigation getting swallowed (see architecture.md → "frontend plumbing").
6. **Smoke test**: hit `/pulse/overview?refresh=true` once to build the first snapshot
   (can take minutes — Kalshi is slow), then confirm normal loads are instant and modules
   are populated and capped.

## Porting notes (the repo-specific bits to swap)

The reference code came from a working FastAPI + React dashboard. Three things are
environment-specific — find and replace them:

| In the code | What it is | Swap for |
|---|---|---|
| `from src.config.paths import get_data_dir` | where snapshots/cache live (has a `~/.vibe-trading` fallback) | your app's data dir |
| `from src.providers.llm import build_llm` (in `polymarket_translate.py`) | the LLM used to translate titles to Chinese | your LLM client, or drop translation entirely (English-only) |
| `ProbabilityTrend`, Tailwind classes, lucide icons, `@/` alias | UI stack | your component/design system |

Everything else (the API logic, taxonomy, aggregator, snapshot/async model, gotcha
handling) is portable as-is. The modules import each other by bare name (e.g.
`import market_taxonomy`) — keep them in the same package or adjust imports.

## Scope / customization

- **Sources**: Polymarket + Kalshi are the two free, no-auth, money-backed venues worth
  using. Manifold (play-money) is open too but noisy; Metaculus/PredictIt are
  Cloudflare-blocked from servers. Adding/removing a source = add/remove a `*_signals.py`.
- **Modules & filtering**: the taxonomy is a keyword map — retune `CORE_MODULES`,
  `REFERENCE_MODULES`, keyword lists, and `MODULE_CAPS` for your audience. The default
  folds sports/world-cup/crypto into a collapsed "reference" group.
- **Translation**: optional. If the audience reads English, delete the translate step.

Read `reference/apis.md` and `reference/architecture.md` next.

---

> 📦 https://github.com/simonlin1212/global-percent — Star ⭐ 是最好的支持
