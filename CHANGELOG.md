# Changelog

本项目遵循语义化版本。日期格式 YYYY-MM-DD。

## V1.0 — 2026-06-05

首次开源。一份「搭建指南 + 参考代码」AI Skill，把 Polymarket + Kalshi 两个公开预期概率源整合成投研系统里的全球宏观预期概率面板。

### 新增
- **SKILL.md** —— 哲学、搭建流程、移植说明（3 个环境相关替换点）。
- **reference/apis.md** —— Polymarket（Gamma + CLOB）+ Kalshi（events + markets）的实测端点、字段、每个坑。
- **reference/architecture.md** —— 统一 schema、关键词分类、快照模型、异步刷新、空拉不覆盖铁律、多腿事件折叠、前端管线、可直接抄的踩坑清单。
- **code/backend/** —— Python 参考实现：
  - `market_taxonomy.py` —— 10 模块（6 核心 + 4 参考）关键词分类器 + 原生 category 兜底 + 模块限流。
  - `polymarket_signals.py` —— Polymarket Gamma/CLOB 拉取 + 整形 + 快照。
  - `kalshi_signals.py` —— Kalshi events 拉取 + 整形 + 快照（含重试 / 空拉守卫 / 多腿折叠）。
  - `polymarket_translate.py` —— 可选标题翻译（接你自己的 LLM 客户端）。
  - `market_pulse.py` —— 聚合器 + 异步刷新快照模型（核心）。
  - `api_routes.py` —— FastAPI 路由（`/pulse/overview`、`/polymarket/history`）。
- **code/frontend/** —— React 面板：
  - `EventProbabilityPanel.tsx` —— 模块分区 + 来源徽章 + 英文主/中文次标题 + 多腿档位 chip + 折叠参考组 + 异步刷新轮询。
  - `ProbabilityTrend.tsx` —— echarts 概率趋势折线图。

### 实测验证（2026-06-05）
- Polymarket Gamma `/markets`：字段全部有效（`outcomePrices`=概率、`volume24hr`、`clobTokenIds`、`oneDayPriceChange`/`oneWeekPriceChange`、`slug`、`endDateIso`），服务端 `volume24hr` 排序可用。
- Polymarket CLOB `/prices-history`：返回 `{history:[{t,p}]}` 时间序列。
- Polymarket CLOB `/midpoint`：返回 `{mid}`。
- Kalshi `/events?with_nested_markets=true`：`*_dollars` 全部在位，旧 cents 字段（`last_price`/`yes_bid`/`yes_ask`）确认已返回 None。
- Kalshi `/markets?series_ticker=KXFED`：系列过滤器可用。
- 端到端跑通：Polymarket 单页 83 条命中分类、概率真实；Kalshi 单页整形 118 条、多腿 `pick_label` 正常、概率全部落在 [0,1]。
