import { useEffect, useMemo, useState } from "react";
import { Activity, TrendingUp, TrendingDown, ExternalLink, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import { ProbabilityTrend } from "@/components/charts/ProbabilityTrend";

type Source = "polymarket" | "kalshi";

interface Market {
  question: string | null;
  question_zh: string | null;
  topic: string;
  outcomes: string[];
  prices: (number | null)[];
  prob_yes: number | null;
  pick_label?: string | null;
  change_24h: number | null;
  change_7d: number | null;
  volume_24h: number | null;
  liquidity: number | null;
  end_date: string | null;
  slug: string | null;
  series_ticker?: string | null;
  token_id_yes: string | null;
  source: Source;
  kalshi_category?: string | null;
}

interface ModuleGroup {
  key: string;
  core: boolean;
  market_count: number;
  volume_24h: number;
  source_counts: Partial<Record<Source, number>>;
  markets: Market[];
}

interface Overview {
  as_of: string;
  sources: string[];
  module_order: string[];
  core_modules: string[];
  modules: ModuleGroup[];
  updating?: boolean;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface TrendPoint {
  t: number | null;
  p: number | null;
}

export function Polymarket() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showReference, setShowReference] = useState(false);

  const [selected, setSelected] = useState<Market | null>(null);
  const [history, setHistory] = useState<TrendPoint[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    request<Overview>("/pulse/overview")
      .then((res) => alive && setOverview(res))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  // Refresh kicks off a slow server-side rebuild (Kalshi's full book takes 1-2 min) that
  // returns the current snapshot immediately with ``updating``. Poll until ``as_of`` advances.
  const refresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    const prevAsOf = overview?.as_of;
    try {
      const res = await request<Overview>("/pulse/overview?refresh=true");
      setOverview(res);
      setError(null);
      if (res.updating) {
        for (let i = 0; i < 24; i++) {
          await sleep(20000);
          try {
            const fresh = await request<Overview>("/pulse/overview");
            if (fresh.as_of && fresh.as_of !== prevAsOf && !fresh.updating) {
              setOverview(fresh);
              break;
            }
          } catch { /* transient — keep polling */ }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "刷新失败");
    } finally {
      setRefreshing(false);
    }
  };

  const selectMarket = (m: Market) => {
    setSelected(m);
    setHistory([]);
    if (!m.token_id_yes) return; // Kalshi has no PM-style trend token in v1
    setHistoryLoading(true);
    request<{ history: TrendPoint[] }>(`/polymarket/history?token_id=${encodeURIComponent(m.token_id_yes)}&interval=1m`)
      .then((res) => setHistory(res.history ?? []))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  };

  const coreModules = useMemo(() => (overview?.modules ?? []).filter((m) => m.core), [overview]);
  const refModules = useMemo(() => (overview?.modules ?? []).filter((m) => !m.core), [overview]);
  const refCount = refModules.reduce((n, m) => n + m.market_count, 0);

  return (
    <div className="flex flex-col gap-5 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <Activity className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">事件概率 · 全市场概率总览</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Polymarket + Kalshi 双源合并 · 按模块看全市场宏观情绪温度（货币政策 / 宏观 / 地缘 / 政治 / 大宗 / AI）。看概率做推断，<b>非交易</b>。
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-sm hover:border-primary disabled:opacity-60 transition-colors"
            title="重新拉取两站最新概率"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "更新中…" : "更新"}
          </button>
          {refreshing ? (
            <span className="text-[11px] text-primary/80">双源重建中（Kalshi 全量约 1-2 分钟，完成自动刷新）</span>
          ) : overview?.as_of ? (
            <span className="text-[11px] text-muted-foreground/70">数据时点 {overview.as_of.replace("T", " ")}</span>
          ) : null}
        </div>
      </div>

      {error && (
        <div className="text-sm text-danger border border-danger/30 rounded p-3 bg-danger/5">{error}</div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Module sections */}
        <div className="flex flex-col gap-5">
          {loading ? (
            [1, 2, 3].map((i) => <div key={i} className="h-40 rounded-lg bg-muted/50 animate-pulse" />)
          ) : (
            <>
              {coreModules.map((g) => (
                <ModuleSection key={g.key} group={g} selected={selected} onSelect={selectMarket} />
              ))}

              {/* Reference group (crypto / sports / pop-culture) — collapsed by default */}
              {refModules.length > 0 && (
                <div className="border-t pt-4">
                  <button
                    onClick={() => setShowReference((v) => !v)}
                    className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showReference ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    其他 · 参考（加密 / 体育 / 娱乐）· {refCount} 个
                    <span className="text-[11px] text-muted-foreground/60">非投资锚，仅参考</span>
                  </button>
                  {showReference && (
                    <div className="mt-4 flex flex-col gap-5">
                      {refModules.map((g) => (
                        <ModuleSection key={g.key} group={g} selected={selected} onSelect={selectMarket} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail / trend */}
        <div className="lg:sticky lg:top-4 self-start w-full">
          {!selected ? (
            <div className="border rounded-lg p-6 text-sm text-muted-foreground">
              点选左侧任一事件查看详情。Polymarket 事件附 Yes 概率历史趋势；Kalshi 事件展示当前概率。
            </div>
          ) : (
            <DetailPanel market={selected} history={history} historyLoading={historyLoading} />
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground/70 border-t pt-3">
        数据来自 Polymarket + Kalshi 公开 API（免登录只读）。已剔除体育/世界杯/加密刷屏（折叠到参考组），各模块按 24h 成交取热门。
        仅作全球宏观情绪参考，<b>非投资建议</b>。涨跌按 A股习惯红涨绿跌。
      </p>
    </div>
  );
}

interface ModuleSectionProps {
  group: ModuleGroup;
  selected: Market | null;
  onSelect: (m: Market) => void;
}

function ModuleSection({ group, selected, onSelect }: ModuleSectionProps) {
  const pm = group.source_counts.polymarket ?? 0;
  const ks = group.source_counts.kalshi ?? 0;
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center gap-2.5">
        <span className={`h-2.5 w-2.5 rounded-full ${moduleAccent(group.key)}`} />
        <h2 className="text-base font-semibold">{group.key}</h2>
        <span className="text-[11px] text-muted-foreground">{group.market_count} 个</span>
        <span className="text-[11px] text-muted-foreground/70">成交 {fmtVol(group.volume_24h)}</span>
        <span className="ml-auto flex items-center gap-1.5 text-[10px]">
          {pm > 0 && <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400">PM {pm}</span>}
          {ks > 0 && <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400">Kalshi {ks}</span>}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {group.markets.map((m) => (
          <MarketRow
            key={`${m.source}-${m.slug ?? m.question}`}
            market={m}
            active={selected?.slug === m.slug && selected?.source === m.source}
            onClick={() => onSelect(m)}
          />
        ))}
      </div>
    </section>
  );
}

interface MarketRowProps {
  market: Market;
  active: boolean;
  onClick: () => void;
}

function MarketRow({ market, active, onClick }: MarketRowProps) {
  const pct = market.prob_yes != null ? Math.round(market.prob_yes * 100) : null;
  return (
    <button
      onClick={onClick}
      className={`text-left border rounded-lg p-2.5 transition-colors ${
        active ? "border-primary bg-primary/5" : "hover:border-primary/50"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <SourceBadge source={market.source} />
        <span className="text-[10px] text-muted-foreground/70">{fmtDate(market.end_date)}</span>
      </div>
      <p className="text-[13px] font-medium leading-snug line-clamp-2">
        {market.question}
      </p>
      {market.question_zh && (
        <p className="mt-0.5 text-[11px] text-muted-foreground leading-snug line-clamp-2">
          {market.question_zh}
        </p>
      )}
      {market.pick_label && (
        <p className="mt-1 inline-block rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-600 dark:text-amber-400">
          档位 · {market.pick_label}（市场预期线）
        </p>
      )}
      <div className="mt-1.5 flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${pct ?? 0}%` }} />
        </div>
        <span className="text-[13px] font-semibold tabular-nums w-11 text-right">{fmtPct(market.prob_yes)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
        <ChangeBadge value={market.change_24h} suffix="24h" />
        <span className="ml-auto">成交 {fmtVol(market.volume_24h)}</span>
      </div>
    </button>
  );
}

function DetailPanel({ market, history, historyLoading }: { market: Market; history: TrendPoint[]; historyLoading: boolean }) {
  const url =
    market.source === "polymarket" && market.slug
      ? `https://polymarket.com/event/${market.slug}`
      : market.source === "kalshi" && market.series_ticker
      ? `https://kalshi.com/markets/${market.series_ticker}`
      : null;
  return (
    <div className="border rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SourceBadge source={market.source} />
            <span className="text-[11px] text-muted-foreground">{market.topic}</span>
          </div>
          <h2 className="text-sm font-semibold leading-snug">{market.question}</h2>
          {market.question_zh && (
            <p className="mt-0.5 text-xs text-muted-foreground leading-snug">{market.question_zh}</p>
          )}
        </div>
        {url && (
          <a href={url} target="_blank" rel="noreferrer" className="shrink-0 text-muted-foreground hover:text-primary" title="查看原始市场">
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold">{fmtPct(market.prob_yes)}</span>
        <span className="text-sm text-muted-foreground">
          {market.pick_label ? `P（${market.pick_label}）` : "Yes 概率"}
        </span>
        <ChangeBadge value={market.change_24h} suffix="24h" />
      </div>
      {market.pick_label && (
        <p className="text-xs text-muted-foreground/80">
          多档位事件：展示「市场预期线」（概率最接近 50% 的档位 = 市场隐含水平）。其余档位见原始市场。
        </p>
      )}
      {market.source === "polymarket" ? (
        historyLoading ? (
          <div className="h-[280px] rounded bg-muted/40 animate-pulse" />
        ) : (
          <ProbabilityTrend points={history} />
        )
      ) : (
        <div className="text-xs text-muted-foreground border rounded p-3 bg-muted/20">
          Kalshi 暂无趋势曲线（v1）。当前为快照概率，点右上角可在 Kalshi 查看历史。
        </div>
      )}
    </div>
  );
}

function SourceBadge({ source }: { source: Source }) {
  const isPm = source === "polymarket";
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
        isPm ? "bg-violet-500/15 text-violet-600 dark:text-violet-400" : "bg-sky-500/15 text-sky-600 dark:text-sky-400"
      }`}
    >
      {isPm ? "Polymarket" : "Kalshi"}
    </span>
  );
}

function ChangeBadge({ value, suffix }: { value: number | null; suffix: string }) {
  if (value == null || value === 0) {
    return <span className="text-muted-foreground/60">— {suffix}</span>;
  }
  const up = value > 0;
  // A-share convention: red = up, green = down.
  const cls = up ? "text-danger" : "text-success";
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-0.5 ${cls}`}>
      <Icon className="h-3 w-3" />
      {(value > 0 ? "+" : "")}{(value * 100).toFixed(1)}pt {suffix}
    </span>
  );
}

function moduleAccent(key: string): string {
  const map: Record<string, string> = {
    货币政策: "bg-amber-500",
    宏观经济: "bg-orange-500",
    地缘政治: "bg-red-500",
    政治选举: "bg-blue-500",
    股指大宗: "bg-emerald-500",
    AI科技: "bg-violet-500",
    加密: "bg-yellow-500",
    体育: "bg-slate-400",
    娱乐: "bg-pink-400",
    其他: "bg-gray-400",
  };
  return map[key] ?? "bg-gray-400";
}

function fmtPct(p: number | null): string {
  return p == null ? "—" : `${(p * 100).toFixed(1)}%`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function fmtVol(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

// Local request helper — endpoints are public (no auth), mirrors Correlation.tsx.
async function request<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" } });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}
