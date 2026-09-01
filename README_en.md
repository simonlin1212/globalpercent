<p align="center"><a href="README.md">简体中文</a> | <b>English</b></p>

<h1 align="center">globalpercent</h1>

<p align="center">
  <b>Global macro expectation-probability panel — 2 sources · 5 endpoints · 10 modules · zero-auth</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <a href="https://github.com/simonlin1212/globalpercent/stargazers"><img src="https://img.shields.io/github/stars/simonlin1212/globalpercent?style=social" alt="Stars"></a>
  <br>
  <img src="https://img.shields.io/badge/sources-2-2ea44f.svg" alt="sources">
  <img src="https://img.shields.io/badge/endpoints-5-2ea44f.svg" alt="endpoints">
  <img src="https://img.shields.io/badge/modules-10-2ea44f.svg" alt="modules">
  <img src="https://img.shields.io/badge/auth-zero-success.svg" alt="Zero Auth">
</p>

<p align="center">
  <a href="#architecture">Architecture</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#5-endpoints-all-public--no-auth--read-only">Endpoints</a> ·
  <a href="./CHANGELOG.md">Changelog</a>
</p>

A global-macro-probability panel — 2 sources · 5 endpoints · 10 modules · zero auth, zero account.

A self-contained **AI Skill (build guide + reference code)** that teaches your AI coding agent to merge public probability data from **Polymarket + Kalshi** into a single **global-macro-probability panel** for an investment-research system: it classifies every market into macro modules (monetary policy / macro economy / geopolitics / elections / indices & commodities / AI…) and surfaces the whole market's expected-probability state at a glance as a **sentiment / risk overlay**.

> **It's a thermometer, not a trading signal.** A contract trading at $0.62 means the market bets $0.62 = 62% probability the event happens. Reading those numbers is **free, no account, no wallet** — only *trading* needs one. So you get a global, money-backed read on macro mood (Fed, geopolitics, AI milestones…) at zero cost — to read regime/cycle/catalyst-timing, not to pick what to buy.

> It is NOT a single API call. The value is the *system*: one common schema, classification, dedup, multi-source merge, snapshot caching, async refresh, translation, and a dozen non-obvious gotchas — all captured so you don't rediscover them.

> Compatible with [Claude Code](https://github.com/anthropics/claude-code) · [Codex](https://github.com/openai/codex) · [OpenClaw](https://github.com/anthropics/openclaw).
>
> All endpoints were **verified against the live APIs on 2026-06-05** (field names change — Kalshi already renamed once; re-verify with a quick curl before trusting any field).

## Architecture

```
Polymarket Gamma API ─┐
                      ├─► per-source fetchers shape every market into ONE common schema
Kalshi events API ────┘        (question, prob_yes, change_24h, volume_24h, source, …)
                                          │
                          shared taxonomy classifies each into a module
                          (monetary/macro/geo/elections/indices/AI + reference group)
                                          │
                          aggregator: merge → group by module → cap floods →
                          translate titles → pin a disk SNAPSHOT
                                          │
                          /pulse/overview  (instant from snapshot; refresh = async rebuild)
                                          │
                          React panel: module sections + source badges + trend chart
```

## Quick Start

```bash
mkdir -p ~/.claude/skills/globalpercent
git clone https://github.com/simonlin1212/globalpercent.git \
  ~/.claude/skills/globalpercent
```

Then tell your agent: *"Use the globalpercent skill to build a macro-probability panel into my app."* It reads `reference/apis.md` + `reference/architecture.md`, then ports `code/` into your stack (3 documented env-specific swap points: data dir / LLM client / UI components). Backend needs only `httpx`; translation is optional; frontend is React + echarts.

## 5 Endpoints (all public · no auth · read-only)

**Polymarket** — Gamma `/markets` (question / outcomes / **outcomePrices = probability** / volume24hr / clobTokenIds / 24h&7d change / slug), CLOB `/prices-history` (`{t,p}` series for the trend chart), CLOB `/midpoint`. ⚠️ `outcomes`/`outcomePrices`/`clobTokenIds` come back as **JSON-encoded strings** — `json.loads()` them.

**Kalshi** — `/events?with_nested_markets=true` (native `category` + nested markets with `*_dollars` prices, cursor-paginated; slow: 1–8 min full book → async refresh), `/markets?series_ticker=KXFED` (series filter works & is fast; `category` filter is broken, no volume sort). ⚠️⚠️ Prices were renamed to **`*_dollars`** in 2026-06 — old cents fields (`last_price`/`yes_bid`) now return None. The code uses the new names and is verified.

## 10 Modules

Keyword-first classification with Kalshi's native `category` as fallback. Core (expanded): monetary policy, macro economy, geopolitics, elections, indices & commodities, AI & tech. Reference (collapsed): crypto, sports, entertainment, other. Each module capped to top-N by 24h volume so floods don't drown the macro signal.


## Data Sources

Polymarket + Kalshi are the two free, no-auth, money-backed sources worth building on — complementary (Polymarket = geopolitics/crypto/elections depth, Kalshi = clean macro-economics structure). Manifold is play-money (noisy); Metaculus/PredictIt are Cloudflare-blocked from servers.

---

## The Author Is Open to Opportunities

The author is open to AI roles at Tencent and other leading technology companies in Shenzhen, and hopes to join a team passionate about AI development. Areas of interest include AI / Agent product development, real-world deployment, and AI consulting.

Contact: [simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

---

## Disclaimer

This project provides tools to **fetch and visualize public expected-probability data** — a sentiment/risk thermometer. It does **not** constitute investment advice and is **not** a trading signal. All data comes from third-party public APIs; accuracy and availability depend on the source. Markets carry risk.

---

## Support

If this tool saved you time, a coffee is appreciated ☕

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>

> Need something that isn't here? Open an [Issue](https://github.com/simonlin1212/globalpercent/issues); sponsors' issues go first.

---

## License

[Apache License 2.0](./LICENSE)

**Author:** Simon Lin · X [@linsizhen](https://x.com/linsizhen) · Email: [simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)
