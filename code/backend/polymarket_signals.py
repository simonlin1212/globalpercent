"""Polymarket public-API signal fetcher for the Vibe-Trading dashboard.

Read-only, no auth, no account required. Pulls active markets from the Gamma API,
keeps only macro / geopolitics / AI markets that are useful as a global
"sentiment thermometer" for mid-term A-share swing trading, and tags each by
topic. Probability time series (for the trend chart) comes from the CLOB
prices-history endpoint.

Everything here is public market data — nothing places trades.
Verified against the live API on 2026-05-29.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
CLOB_HISTORY_URL = "https://clob.polymarket.com/prices-history"

# Only surface markets relevant as a macro / risk overlay; filter out
# sports / celebrity / pop-culture noise.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    # 顺序 = 分类优先级（_classify 取第一个命中）：地缘 在 美国大选 前（Trump+Iran 归地缘）；世界杯 在 体育 前。
    "货币政策": ["fed", "interest rate", "rate cut", "rate hike", "fomc", "powell", "basis point"],
    "地缘政治": ["china", "taiwan", "tariff", "trade war", "xi jinping", "hormuz", "iran", "venezuela", "russia", "ukraine", "blockade", "north korea", "israel", "gaza", "middle east", "nato"],
    # 美国专属：泛词 president/election 会吞掉秘鲁/哥伦比亚/首尔等外国选举，故只用美国特征词。
    "美国大选": ["trump", "2028", "democratic nominee", "republican nominee", "democratic presidential", "republican presidential", "us presidential", "us senate", "us house", "potus", "white house", "newsom", "jd vance", "desantis", "maga", "midterm", "impeach"],
    "宏观经济": ["recession", "gdp", "inflation", "cpi", "unemployment", "jobs report"],
    "AI科技": ["nvidia", "openai", "agi", "semiconductor", "tsmc", "chip", "anthropic", "gpt", "chatgpt", "llm", "grok", "gemini", "claude", "deepmind", "artificial intelligence", "humanoid robot"],
    # 2026 FIFA 世界杯（6/11-7/19 美加墨），当下第二热事件；必须在"体育"前，否则被泛体育关键词吞掉。
    "世界杯": ["world cup", "fifa"],
    "体育": ["nba", "nfl", " mlb", "world series", "super bowl", "stanley cup", "tennis", "atp", "wta", "roland garros", "wimbledon", "us open", "french open", "australian open", "ufc", "boxing", "premier league", "la liga", "serie a", "bundesliga", "champions league", "grand prix", " pga ", "esports", " lol ", "cs2", "csgo", "valorant", "dota", "iem ", " vs. ", " vs "],
    "加密": ["bitcoin", "btc", "ethereum", "crypto", "microstrategy", "mstr", "solana", "dogecoin", "coinbase", "stablecoin", "ripple", "xrp"],
}

_TTL_SECONDS = 300  # 5 min cache — respect Polymarket rate limits
_CACHE: dict[str, tuple[float, Any]] = {}

# Some events spawn dozens of near-duplicate markets (e.g. the Iran situation:
# many "US-Iran peace deal by <date>" variants). Keep only the N largest of
# each flood-prone cluster so the panel stays a thermometer, not a wall of dupes.
CLUSTER_CAPS: dict[str, int] = {"iran": 4, "world cup": 8}

# 决定每个 cluster 保留哪 N 个时的排序依据（默认 volume_24h）。
# 世界杯有 30+ 个"Will X win?"近重复市场，按成交量留会选到一堆冷门(1%)；
# 按 prob_yes 留 = 展示夺冠热门(西/阿/法/巴…)，才是有意义的温度计。
CLUSTER_RANK_KEY: dict[str, str] = {"world cup": "prob_yes"}

# 每个分类整体最多展示 N 个：体育(海量单场)/加密(MSTR等多变体)/大选(多候选人)易刷屏 → 留 top-N(按成交量)。
TOPIC_CAPS: dict[str, int] = {"体育": 6, "加密": 6, "美国大选": 6}


def available_topics() -> list[str]:
    return list(TOPIC_KEYWORDS.keys())


def _cache_get(key: str) -> Any | None:
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < _TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


# --- Pinned snapshot -------------------------------------------------------
# The panel is a slow-moving sentiment gauge, and a fresh fetch+translate takes
# 10-20s, so opening the page used to show empty/loading every time. Instead we
# persist the last fetched+translated result to disk: normal page loads serve
# this pinned version instantly (no network, no LLM, survives backend restart),
# and only the refresh button (force=True) re-pulls and re-pins.
def _snapshot_path() -> Path:
    try:
        from src.config.paths import get_data_dir

        return get_data_dir() / "polymarket_snapshot.json"
    except Exception:
        return Path.home() / ".vibe-trading" / "polymarket_snapshot.json"


def _load_snapshot() -> list[dict[str, Any]] | None:
    try:
        data = json.loads(_snapshot_path().read_text("utf-8"))
        return data if isinstance(data, list) else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def _save_snapshot(markets: list[dict[str, Any]]) -> None:
    try:
        path = _snapshot_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(markets, ensure_ascii=False), "utf-8")
    except OSError as exc:
        logger.warning("polymarket snapshot save failed: %s", exc)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_json_field(raw: Any, default: Any) -> Any:
    """Gamma returns some array fields as JSON-encoded strings."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default
    return raw if raw is not None else default


def _classify(question: str) -> str | None:
    q = question.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return topic
    return None


def _cap_clusters(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cap flood-prone clusters to their top-N, then return all markets by 24h volume desc.

    Each capped cluster keeps only its top-N, ranked by ``CLUSTER_RANK_KEY`` (default
    ``volume_24h``; world cup uses ``prob_yes`` so the favourites surface, not random
    long-shots). Final list is volume-sorted so the panel stays "hottest first".
    """
    def cluster_of(market: dict[str, Any]) -> str | None:
        q = (market.get("question") or "").lower()
        for keyword in CLUSTER_CAPS:
            if keyword in q:
                return keyword
        return None

    capped: dict[str, list[dict[str, Any]]] = {}
    kept: list[dict[str, Any]] = []
    for market in markets:
        kw = cluster_of(market)
        if kw is None:
            kept.append(market)
        else:
            capped.setdefault(kw, []).append(market)

    for kw, group in capped.items():
        rank_key = CLUSTER_RANK_KEY.get(kw, "volume_24h")
        group.sort(key=lambda m: m.get(rank_key) or 0.0, reverse=True)
        kept.extend(group[: CLUSTER_CAPS[kw]])

    kept.sort(key=lambda m: m.get("volume_24h") or 0.0, reverse=True)
    return kept


def _cap_topics(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Limit each ``TOPIC_CAPS`` topic to its top-N by 24h volume; others pass through."""
    ordered = sorted(markets, key=lambda m: m.get("volume_24h") or 0.0, reverse=True)
    counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for market in ordered:
        topic = market.get("topic")
        cap = TOPIC_CAPS.get(topic)
        if cap is not None:
            counts[topic] = counts.get(topic, 0) + 1
            if counts[topic] > cap:
                continue
        kept.append(market)
    return kept


def _shape(market: dict[str, Any], topic: str) -> dict[str, Any]:
    outcomes = _parse_json_field(market.get("outcomes"), [])
    prices = _parse_json_field(market.get("outcomePrices"), [])
    token_ids = _parse_json_field(market.get("clobTokenIds"), [])
    return {
        "question": market.get("question"),
        "question_zh": None,  # filled in by the translation step
        "topic": topic,
        "outcomes": outcomes,
        "prices": [_safe_float(p) for p in prices],
        "prob_yes": _safe_float(prices[0]) if prices else None,
        "change_24h": _safe_float(market.get("oneDayPriceChange")),
        "change_7d": _safe_float(market.get("oneWeekPriceChange")),
        "volume_24h": _safe_float(market.get("volume24hr")),
        "liquidity": _safe_float(market.get("liquidity")),
        "end_date": market.get("endDateIso") or market.get("endDate"),
        "slug": market.get("slug"),
        "token_id_yes": token_ids[0] if token_ids else None,
    }


async def pull_raw_markets(pages: int = 3, force: bool = False) -> list[dict[str, Any]]:
    """Raw Gamma markets (top ``pages`` x 100 by 24h volume), deduped by id.

    Shared by ``fetch_markets`` and the multi-source pulse aggregator. Cached for
    ``_TTL_SECONDS``; ``force`` bypasses the cache.
    """
    cache_key = f"markets:{pages}"
    raw = None if force else _cache_get(cache_key)
    if raw is not None:
        return raw
    raw = []
    seen_ids: set[str] = set()
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (vibe-trading)"}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for page in range(pages):
            params = {
                "active": "true",
                "closed": "false",
                "limit": "100",
                "offset": str(page * 100),
                "order": "volume24hr",
                "ascending": "false",
            }
            resp = await client.get(GAMMA_MARKETS_URL, params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not isinstance(batch, list):
                batch = batch.get("data", []) if isinstance(batch, dict) else []
            if not batch:
                break
            for market in batch:
                mid = market.get("id")
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    raw.append(market)
    _cache_set(cache_key, raw)
    return raw


async def fetch_markets(topics: list[str] | None = None, pages: int = 3, force: bool = False) -> list[dict[str, Any]]:
    """Active macro/geo/AI markets, tagged by topic, sorted by 24h volume.

    Scans the top ``pages`` x 100 markets by 24h volume (Gamma caps each page at
    100), so quieter-but-relevant macro markets aren't missed.

    Snapshot model: normal loads (``force=False``) return the last pinned snapshot
    from disk instantly — no network, no translation, never empty, survives backend
    restart. ``force=True`` (the panel's refresh button) re-pulls from Polymarket,
    re-translates, and re-pins the snapshot. The panel is a slow-moving sentiment
    gauge, so a pinned version between manual refreshes is the intended behavior.

    ``topics`` keeps only the given buckets (subset of ``TOPIC_KEYWORDS`` keys);
    empty/None keeps all matched markets.
    """
    wanted = set(topics) if topics else None

    # Normal load → serve the pinned snapshot (instant). Only the refresh button
    # (force=True) repulls. Cold start with no snapshot yet falls through to a fetch.
    if not force:
        snapshot = _load_snapshot()
        if snapshot is not None:
            return [m for m in snapshot if wanted is None or m.get("topic") in wanted]

    raw = await pull_raw_markets(pages=pages, force=force)

    # Build the full set (all topics) so the pinned snapshot is complete; the
    # request's topic filter is applied at return.
    shaped: list[dict[str, Any]] = []
    for market in raw:
        topic = _classify(market.get("question") or "")
        if topic is None:
            continue
        shaped.append(_shape(market, topic))

    shaped = _cap_clusters(shaped)
    shaped = _cap_topics(shaped)

    # Attach Chinese translations (cached). Bounded by a hard timeout so a slow/down
    # LLM never hangs the panel — degrades to English-only, translations self-heal
    # into the cache on later loads once the LLM responds.
    try:
        from polymarket_translate import translate_questions

        # translate_questions bounds only the LLM (uncached) work internally and
        # always returns cache hits — so cached titles show Chinese even when the
        # slow uncached batches time out.
        # 20s budget: some political questions take ~15s for the reasoning model,
        # so a 12s budget never banked them and they stayed English forever. Once a
        # title is cached it's instant, so this only bites during cache warming.
        zh_map = await translate_questions(
            [m["question"] for m in shaped if m["question"]],
            llm_timeout=20.0,
        )
        for market in shaped:
            market["question_zh"] = zh_map.get(market["question"])
    except Exception:  # noqa: BLE001 — best-effort
        pass

    # Pin this fresh, translated set so subsequent normal loads are instant.
    _save_snapshot(shaped)
    return [m for m in shaped if wanted is None or m.get("topic") in wanted]


async def fetch_history(token_id: str, interval: str = "1w", fidelity: int = 720) -> list[dict[str, Any]]:
    """Probability time series for one outcome token (for the trend chart)."""
    cache_key = f"history:{token_id}:{interval}:{fidelity}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    params = {"market": token_id, "interval": interval, "fidelity": str(fidelity)}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(CLOB_HISTORY_URL, params=params, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    history = data.get("history", []) if isinstance(data, dict) else []
    points = [{"t": p.get("t"), "p": _safe_float(p.get("p"))} for p in history]
    _cache_set(cache_key, points)
    return points
