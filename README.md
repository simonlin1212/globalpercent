# global-percent

全球宏观预期概率面板 —— 2 数据源 · 5 端点 · 10 模块 · 零鉴权零账户

一个自包含的 **AI Skill（搭建指南 + 参考代码）**，教你的 AI 编程助手把 **Polymarket + Kalshi** 两个公开预期概率源的数据，整合成投研系统里的一块「**全球宏观预期概率面板**」：自动分类成宏观模块（货币政策 / 宏观经济 / 地缘 / 政治选举 / 股指大宗 / AI 科技…），一眼看清全市场的预期概率状态，作为**情绪 / 风险温度计**叠加层。

> **它是温度计，不是交易信号。** 一份合约报价 0.62 = 市场用真金白银押注该事件有 62% 的预期概率发生。读这些数字**完全免费、无需账户、无需钱包**——只有「下场交易」才需要账户。所以你能零成本拿到一份全球、资金背书的宏观情绪读数（Fed 决议、地缘、AI 里程碑…），用来读「市场情绪/周期位置/催化剂时点」，而不是用来决定买什么。

> 这不是一次 API 调用就完事。价值在于**系统**：统一 schema、分类、去重、多源合并、快照缓存、异步刷新、标题翻译，以及十几个每个都要花真实调试时间才能踩明白的坑——全部封装在这份 Skill 里，你不用重新发现一遍。

> 兼容 [Claude Code](https://github.com/anthropics/claude-code) · [Codex](https://github.com/openai/codex) · [OpenClaw](https://github.com/anthropics/openclaw)
>
> Skill 文件本质是结构化 Markdown + 内嵌 Python/React，任何支持上下文注入的 AI 编程助手都能用。
>
> 所有接口已于 **2026-06-05 对照线上 API 实测验证**（字段名会变——尤其 Kalshi 已改过一次，贴代码前请用一行 curl 复验）。

---

## 架构（一口气讲完）

```
全球宏观预期概率面板 · 数据管道
│
Polymarket Gamma API ─┐
                      ├─► 每个源的 fetcher 把每条市场整形成同一套 schema
Kalshi events API ────┘        (question, prob_yes, change_24h, volume_24h, source, …)
                                          │
                          共享 taxonomy 把每条分到一个模块
                          (货币政策/宏观经济/地缘政治/政治选举/股指大宗/AI科技 + 参考组)
                                          │
                          聚合器：合并 → 按模块分组 → 限流刷屏 →
                          翻译标题 → 钉一份磁盘 SNAPSHOT
                                          │
                          /pulse/overview  (快照秒开；刷新 = 后台异步重建)
                                          │
                          React 面板：模块分区 + 来源徽章 + 趋势图
```

---

## 快速开始

**2 步，给你的 AI 助手喂这份 skill。**

```bash
# 1. 创建 skill 目录
mkdir -p ~/.claude/skills/global-percent

# 2. 把整个仓库克隆/下载进去（SKILL.md + code/ + reference/）
git clone https://github.com/simonlin1212/global-percent.git \
  ~/.claude/skills/global-percent
```

然后对 AI 助手说一句：

> 「用 global-percent 这份 skill，把一块全球宏观预期概率面板搭进我的 app。」

它会读 `reference/apis.md`（端点 + 字段 + 每个坑）和 `reference/architecture.md`（设计 + 异步刷新 + 空拉不覆盖等铁律），再把 `code/` 里的后端 + 前端移植进你的技术栈。

> **依赖**：后端只用 `httpx`（异步 HTTP）。翻译步骤可选（要么接你自己的 LLM，要么直接删掉走英文）。前端是 React + echarts，可换成你自己的图表库。

> **Codex / OpenClaw 用户：** 把 SKILL.md + reference/ 的内容贴入系统 prompt 或项目上下文，内嵌代码可直接移植。

---

## 5 个端点（全部公开 · 零鉴权 · 只读）

> 读预期概率不需要账户；只有「交易」才需要 Key。下列端点 2026-06-05 实测全部可用。

### Polymarket（加密结算 · 真金白银 · 地缘/选举/加密/体育最深）

| 端点 | 数据 | 实测状态 |
|------|------|----------|
| Gamma `/markets` | 每条市场的 question / outcomes / **outcomePrices（=概率）** / volume24hr / clobTokenIds / 24h&7d 变动 / slug / 到期日 | ✅ 服务端按 `volume24hr` 排序，`limit≤100` 翻页 |
| CLOB `/prices-history` | 单个 outcome token 的概率时间序列 `{t, p}`（趋势图用） | ✅ `interval=1d/1w/1m/max` + `fidelity` |
| CLOB `/midpoint` | 单 token 的实时中间价 | ✅ 返回 `{mid}` |

> ⚠️ Polymarket 的 `outcomes` / `outcomePrices` / `clobTokenIds` 是 **JSON 编码的字符串**，不是数组——要 `json.loads()`（见 `_parse_json_field`）。

### Kalshi（美国 CFTC 监管 · 真金白银 · 宏观经济结构最干净）

| 端点 | 数据 | 实测状态 |
|------|------|----------|
| `/events?with_nested_markets=true` | 每个 event 带原生 `category` + 嵌套 markets（含 `*_dollars` 报价 + 成交量），分页 cursor | ✅ 慢且重（200 event/页，2–16s/页，全量 1–8 分钟→必须异步刷新） |
| `/markets?series_ticker=KXFED` | 按系列过滤的市场（如 Fed），快（~2s） | ✅ `series_ticker` 可用；`category` 过滤器**失效**、**无成交量排序** |

> ⚠️⚠️ **Kalshi 字段已在 2026-06 改名为 `*_dollars`**：旧的 cents 字段（`last_price` / `yes_bid` / `yes_ask`）现在返回 `None`。要用 `yes_ask_dollars` / `last_price_dollars` / `previous_price_dollars` / `volume_24h_fp` / `liquidity_dollars` 等。本仓库代码已全部按新字段名实现并实测通过。

---

## 10 个模块（taxonomy）

分类**关键词优先、Kalshi 原生 category 兜底**，高信号先判（地缘 在 选举 前、加密 在 股指 前、货币 在 宏观 前），world cup/FIFA 最先判进体育。

| 核心模块（展开显示） | 参考模块（折叠显示） |
|---|---|
| 货币政策 · 宏观经济 · 地缘政治 · 政治选举 · 股指大宗 · AI科技 | 加密 · 体育 · 娱乐 · 其他 |

每个模块按 24h 成交量限 top-N（`MODULE_CAPS`），防止「LA 市长」「每日油价/天气」这类刷屏事件淹没宏观信号。

---

## 使用示例

跟你的 AI 助手说这些话就能驱动这份 skill：

| 场景 | 说什么 |
|------|--------|
| 搭面板 | 「用 global-percent 把一块宏观预期概率面板搭进我的 dashboard」 |
| 只接 Polymarket | 「只接 Polymarket Gamma，先跑通地缘和 AI 两个模块」 |
| 加 Kalshi 宏观 | 「再接上 Kalshi 的 Fed/CPI/就业，做成异步刷新」 |
| 调分类 | 「帮我把 taxonomy 的关键词改成更偏 A 股投研的模块」 |
| 趋势图 | 「给 Polymarket 行加一条概率趋势折线图」 |
| 纯英文 | 「我不需要中文翻译，删掉 translate 那一步」 |

---

## V1.0 亮点

| 能力 | 说明 |
|------|------|
| **双源合并** | Polymarket（地缘/选举/加密深度）+ Kalshi（宏观经济结构）整形成同一套 schema，「加第三个源」= 加一个 `*_signals.py` |
| **多腿/标量事件折叠** | 油价/CPI/气温这类被拆成 10–40 个阈值腿的标量事件，折叠到**最接近 50% 的那条腿**（市场隐含中位水平），并打 `pick_label` 标签（「53% 概率油价高于 $4.20」），不会出现「油价: 2%」这种无意义数字 |
| **快照模型** | 一次拉取+翻译要数秒到数分钟，所以聚合结果钉到磁盘 JSON，普通访问秒开（无网络、无 LLM、重启不丢），只有刷新按钮才重拉 |
| **异步刷新** | Kalshi 全量 1–8 分钟，刷新立即返回旧快照 + `updating:true`，后台 `asyncio.create_task` 重建，前端轮询直到 `as_of` 推进 |
| **空拉永不覆盖（铁律）** | Kalshi 边缘节点会间歇性 `HTTP 000`/`SSLEOFError`，每页重试 + **一旦拉到 0 条绝不落盘、返回上一份好快照**——「API 短暂挂了」绝不能变成「我们把数据删了」 |
| **翻译限流** | 标题按英文原文缓存（永久），小批量(4)+批间延迟(~0.8s)+多轮重试(连续两轮无进展才停)+每批落盘，绕开推理模型大批量返空 + provider 限流两个坑 |

---

## 数据源优先级 / 取舍

| venue | 公开 API | 结论 |
|---|---|---|
| **Polymarket** | ✅ Gamma + CLOB，全公开 | 真金白银，地缘/加密/选举最深 —— **首选** |
| **Kalshi** | ✅ events/markets，只读无需 Key | 真金白银，美国 CFTC 监管，宏观经济结构最干净 —— **首选** |
| Manifold | ✅ `api.manifold.markets/v0/markets` | 玩具币 → 信号噪声大，只作补充 |
| Metaculus | 有 API 但 `403` Cloudflare 拦服务器/curl | 预测社区（非资金），需浏览器/UA 绕过 |
| PredictIt | `403` Cloudflare + 平台衰退 | 跳过 |

> **结论：Polymarket + Kalshi 是两个免费、无鉴权、资金背书、值得搭建的源，且互补**——Polymarket 管地缘/加密/选举深度，Kalshi 管干净的宏观经济结构。

---

## FAQ

**Q: 这能直接跑起来吗？**
这是**搭建指南 + 参考代码** Skill（类似 a-stock-data 的形态），不是开箱即用的 app。把 `code/` 移植进你自己的 FastAPI + React 栈，有 3 个环境相关的替换点（数据目录 / LLM 客户端 / UI 组件库），SKILL.md 里都标注了。

**Q: 为什么是温度计不是交易工具？**
70–84% 的预期概率市场参与者是亏钱的，优势属于做市的高频，不属于「预测得准的 AI」。把面板当作「市场情绪如何」来读，永远不要当买卖信号。

**Q: Kalshi 拉取怎么这么慢？**
Kalshi 没有服务端成交量排序，热门市场被几千个一日体育/天气合约埋着，所以必须把整个 open event book（~7000 event，~35 页）全拉下来客户端排序。全量 1–8 分钟——这就是刷新必须异步的原因。

**Q: 字段名会不会又变？**
会。Kalshi 2026-06 刚把价格字段改成 `*_dollars`，旧字段返回 None。贴代码前用一行 curl 复验字段名（README 顶部端点表给了实测日期）。

**Q: 翻译步骤必须要吗？**
不要。受众读英文的话，直接删掉 translate 那一步走纯英文。它是纯辅助层。

**Q: 不用 Claude Code 能用吗？**
能。SKILL.md + reference/ 是 Markdown，code/ 是标准 Python/React，任何 AI 编程助手或人工都能读取移植。

---

## 更新日志

见 [CHANGELOG.md](./CHANGELOG.md)。

---

## Donate

如果这份 skill 帮到了你的投研工作流，欢迎请作者喝杯咖啡 ☕

<p align="center">
  <img src="./assets/wechat-sponsor.jpg" width="240" alt="微信赞赏码">
</p>
<p align="center">
  <a href="https://ifdian.net/a/simonlin">爱发电</a> ·
  <a href="https://buymeacoffee.com/simonlin1212">Buy Me a Coffee</a>
</p>

> 想接更多预期概率源（Manifold / 自定义）或更多模块？欢迎开 [Issue](https://github.com/simonlin1212/global-percent/issues) 提需求，赞助者的 Issue 优先处理。

---

## Disclaimer

本项目仅提供**公开预期概率数据的获取与可视化工具**，是一块情绪 / 风险温度计，**不构成任何投资建议，也不是交易信号**。所有数据来自第三方公开 API，准确性与可用性以来源为准。市场有风险，决策需谨慎。

---

## License

[Apache License 2.0](./LICENSE) — 自由使用，注明出处即可。

**作者：** Simon 林 · 抖音「Simon林」 · 公众号「硅基世纪」

---

<details>
<summary><b>🇬🇧 English</b></summary>

# global-percent

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
mkdir -p ~/.claude/skills/global-percent
git clone https://github.com/simonlin1212/global-percent.git \
  ~/.claude/skills/global-percent
```

Then tell your agent: *"Use the global-percent skill to build a macro-probability panel into my app."* It reads `reference/apis.md` + `reference/architecture.md`, then ports `code/` into your stack (3 documented env-specific swap points: data dir / LLM client / UI components). Backend needs only `httpx`; translation is optional; frontend is React + echarts.

## 5 Endpoints (all public · no auth · read-only)

**Polymarket** — Gamma `/markets` (question / outcomes / **outcomePrices = probability** / volume24hr / clobTokenIds / 24h&7d change / slug), CLOB `/prices-history` (`{t,p}` series for the trend chart), CLOB `/midpoint`. ⚠️ `outcomes`/`outcomePrices`/`clobTokenIds` come back as **JSON-encoded strings** — `json.loads()` them.

**Kalshi** — `/events?with_nested_markets=true` (native `category` + nested markets with `*_dollars` prices, cursor-paginated; slow: 1–8 min full book → async refresh), `/markets?series_ticker=KXFED` (series filter works & is fast; `category` filter is broken, no volume sort). ⚠️⚠️ Prices were renamed to **`*_dollars`** in 2026-06 — old cents fields (`last_price`/`yes_bid`) now return None. The code uses the new names and is verified.

## 10 Modules

Keyword-first classification with Kalshi's native `category` as fallback. Core (expanded): monetary policy, macro economy, geopolitics, elections, indices & commodities, AI & tech. Reference (collapsed): crypto, sports, entertainment, other. Each module capped to top-N by 24h volume so floods don't drown the macro signal.

## V1.0 Highlights

- **Two-source merge** into one schema — adding a third source = one new `*_signals.py`.
- **Multi-leg / scalar collapse** — gas/CPI/temp scalar events fold to the leg **nearest 50%** with a `pick_label` ("53% chance gas is above $4.20"), never a meaningless "gas: 2%".
- **Snapshot model** — finished result pinned to disk JSON; normal loads are instant (no network, no LLM, survives restart); only refresh re-pulls.
- **Async refresh** — Kalshi's full book takes 1–8 min, so refresh returns the old snapshot + `updating:true` and rebuilds in a background task; the frontend polls until `as_of` advances.
- **Empty-pull-never-overwrites** — Kalshi's edge flakes (`HTTP 000`/`SSLEOFError`); retry each page, and a zero-row pull NEVER overwrites the good snapshot.
- **Translation rate-limit handling** — titles cached by English text forever; small batches (4) + inter-batch delay + multi-round retry + save-after-each.

## Data Sources

Polymarket + Kalshi are the two free, no-auth, money-backed sources worth building on — complementary (Polymarket = geopolitics/crypto/elections depth, Kalshi = clean macro-economics structure). Manifold is play-money (noisy); Metaculus/PredictIt are Cloudflare-blocked from servers.

## Disclaimer

This project provides tools to **fetch and visualize public expected-probability data** — a sentiment/risk thermometer. It does **not** constitute investment advice and is **not** a trading signal. All data comes from third-party public APIs; accuracy and availability depend on the source. Markets carry risk.

## License

[Apache License 2.0](./LICENSE)

**Author:** Simon Lin · TikTok [@simonlin121212](https://www.tiktok.com/@simonlin121212) · Douyin "Simon林" · WeChat Official Account "硅基世纪"

</details>
