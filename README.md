<p align="center"><b>简体中文</b> | <a href="README_en.md">English</a></p>

<h1 align="center">globalpercent</h1>

<p align="center">
  <b>全球宏观预期概率面板 — 2 数据源 · 5 端点 · 10 模块 · 零鉴权零账户</b>
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
  <a href="#架构一口气讲完">架构</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#5-个端点全部公开--零鉴权--只读">端点</a> ·
  <a href="#10-个模块taxonomy">模块</a> ·
  <a href="#faq">FAQ</a> ·
  <a href="./CHANGELOG.md">更新日志</a>
</p>

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

## 作者正在寻找工作机会

作者目前关注腾讯等大型科技企业在深圳的 AI 相关岗位，希望加入一支热爱 AI 开发的团队，继续从事 AI / Agent 产品开发、应用落地及 AI 咨询工作。

联系：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

---

## 快速开始

**2 步，给你的 AI 助手喂这份 skill。**

```bash
# 1. 创建 skill 目录
mkdir -p ~/.claude/skills/globalpercent

# 2. 把整个仓库克隆/下载进去（SKILL.md + code/ + reference/）
git clone https://github.com/simonlin1212/globalpercent.git \
  ~/.claude/skills/globalpercent
```

然后对 AI 助手说一句：

> 「用 globalpercent 这份 skill，把一块全球宏观预期概率面板搭进我的 app。」

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
| 搭面板 | 「用 globalpercent 把一块宏观预期概率面板搭进我的 dashboard」 |
| 只接 Polymarket | 「只接 Polymarket Gamma，先跑通地缘和 AI 两个模块」 |
| 加 Kalshi 宏观 | 「再接上 Kalshi 的 Fed/CPI/就业，做成异步刷新」 |
| 调分类 | 「帮我把 taxonomy 的关键词改成更偏 A 股投研的模块」 |
| 趋势图 | 「给 Polymarket 行加一条概率趋势折线图」 |
| 纯英文 | 「我不需要中文翻译，删掉 translate 那一步」 |

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

**Q: 国内网络访问 Polymarket / Kalshi 超时或连不上？**
这是网络环境问题，不是端点挂了——`gamma-api.polymarket.com` 等 API 域名在中国大陆网络环境下通常无法直连（端点本身存活，2026-07-10 实测 200）。后端需要跑在能访问境外网络的环境里，两个常见做法：
1. **给后端配代理（代码零改动）**：参考代码全部走 `httpx`，默认读取系统代理环境变量。启动后端前设置 `HTTPS_PROXY`（指向你环境里可用的 HTTP 代理地址）即可。
2. **后端部署在境外服务器 / 云函数**，前端面板照常访问自家后端，数据拉取发生在服务端。

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

## 免责声明

本项目仅提供**公开预期概率数据的获取与可视化工具**，是一块情绪 / 风险温度计，**不构成任何投资建议，也不是交易信号**。所有数据来自第三方公开 API，准确性与可用性以来源为准。市场有风险，决策需谨慎。

---

## 赞赏

如果这份 skill 帮到了你的投研工作流，欢迎请作者喝杯咖啡 ☕

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>

> 想接更多预期概率源（Manifold / 自定义）或更多模块？欢迎开 [Issue](https://github.com/simonlin1212/globalpercent/issues) 提需求，赞助者的 Issue 优先处理。

---

## License

[Apache License 2.0](./LICENSE) — 自由使用，注明出处即可。

**作者：** Simon 林 · X [@linsizhen](https://x.com/linsizhen) · 邮箱：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)
