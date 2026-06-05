"""Multi-source probability overview — the 'event probability' panel's backend.

Merges Polymarket + Kalshi into one module-grouped view so the dashboard can show
the whole market's probability state at a glance (each module = 货币政策 / 宏观经济 /
地缘政治 / 政治选举 / 股指大宗 / AI科技, plus a collapsed reference group for
crypto / sports / pop-culture).

Both sources are public, read-only, no auth. Classification is centralised in
``market_taxonomy`` so the two feeds land in the same buckets. Chinese titles reuse
the existing translation cache. A pinned snapshot keeps normal loads instant; the
refresh button (``force=True``) re-pulls both sources and re-pins.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import kalshi_signals
import market_taxonomy
import polymarket_signals

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300
_CACHE: dict[str, tuple[float, Any]] = {}


def _snapshot_path() -> Path:
    try:
        from src.config.paths import get_data_dir

        return get_data_dir() / "pulse_snapshot.json"
    except Exception:
        return Path.home() / ".vibe-trading" / "pulse_snapshot.json"


def _load_snapshot() -> dict[str, Any] | None:
    try:
        data = json.loads(_snapshot_path().read_text("utf-8"))
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def _save_snapshot(overview: dict[str, Any]) -> None:
    try:
        path = _snapshot_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(overview, ensure_ascii=False), "utf-8")
    except OSError as exc:
        logger.warning("pulse snapshot save failed: %s", exc)


async def _shaped_polymarket(force: bool) -> list[dict[str, Any]]:
    """Polymarket raw markets shaped + classified by the shared taxonomy.

    Uses ``pull_raw_markets`` (not ``fetch_markets``) so classification/caps are the
    aggregator's job and nothing is pre-dropped — this keeps international elections
    etc. that the legacy panel's narrower classifier discarded.
    """
    raw = await polymarket_signals.pull_raw_markets(pages=3, force=force)
    shaped: list[dict[str, Any]] = []
    for market in raw:
        question = market.get("question") or ""
        module = market_taxonomy.classify(question)
        row = polymarket_signals._shape(market, module)
        row["source"] = "polymarket"
        shaped.append(row)
    return shaped


def _group_by_module(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bucket markets into ordered modules, cap floods, summarise each module."""
    buckets: dict[str, list[dict[str, Any]]] = {m: [] for m in market_taxonomy.MODULES}
    for market in markets:
        module = market.get("topic")
        buckets.setdefault(module, []).append(market)

    modules: list[dict[str, Any]] = []
    for key in market_taxonomy.MODULES:
        group = buckets.get(key, [])
        group.sort(key=lambda m: m.get("volume_24h") or 0.0, reverse=True)
        cap = market_taxonomy.MODULE_CAPS.get(key)
        if cap is not None:
            group = group[:cap]
        if not group:
            continue
        source_counts: dict[str, int] = {}
        for market in group:
            src = market.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        modules.append({
            "key": key,
            "core": key in market_taxonomy.CORE_SET,
            "market_count": len(group),
            "volume_24h": sum(m.get("volume_24h") or 0.0 for m in group),
            "source_counts": source_counts,
            "markets": group,
        })
    return modules


async def _translate(markets: list[dict[str, Any]]) -> None:
    """Attach Chinese titles in-place (best-effort, bounded, self-healing cache)."""
    try:
        from polymarket_translate import translate_questions

        questions = [m["question"] for m in markets if m.get("question")]
        # Refresh is async/background now, so we can afford to translate *everything*
        # before pinning — the panel keeps serving the old snapshot meanwhile. The cache
        # warms permanently, so only brand-new titles cost time on later rebuilds.
        zh_map = await translate_questions(questions, llm_timeout=300.0)
        for market in markets:
            market["question_zh"] = zh_map.get(market.get("question"))
    except Exception:  # noqa: BLE001 — degrade to English
        pass


_rebuilding = False  # guards against piling up concurrent background rebuilds


async def _build() -> dict[str, Any]:
    """Pull both sources, classify, translate, group, and pin. The slow path
    (Kalshi's full event book can take 1-8 min when the API is loaded)."""
    pm, ks = await asyncio.gather(
        _shaped_polymarket(force=True),
        kalshi_signals.fetch_shaped(force=True),
    )
    merged = pm + ks
    await _translate(merged)
    overview = {
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "sources": ["polymarket", "kalshi"],
        "module_order": market_taxonomy.MODULES,
        "core_modules": market_taxonomy.CORE_MODULES,
        "modules": _group_by_module(merged),
    }
    _save_snapshot(overview)
    return overview


async def _background_rebuild() -> None:
    global _rebuilding
    try:
        await _build()
    except Exception as exc:  # noqa: BLE001 — best-effort; snapshot keeps serving
        logger.warning("pulse background rebuild failed: %s", exc)
    finally:
        _rebuilding = False


async def fetch_overview(force: bool = False) -> dict[str, Any]:
    """The merged, module-grouped probability overview for the panel.

    Normal loads serve the pinned snapshot instantly. ``force=True`` (refresh button)
    kicks off a background rebuild and returns the current snapshot immediately with
    ``updating: True`` — Kalshi's full-book pull is too slow to block on, and the panel
    is a slow-moving gauge, so the frontend polls until ``as_of`` advances. Cold start
    with no snapshot builds synchronously (nothing else to show).
    """
    global _rebuilding
    snap = _load_snapshot()

    if snap is None:
        return await _build()

    if force and not _rebuilding:
        _rebuilding = True
        asyncio.create_task(_background_rebuild())

    if force or _rebuilding:
        return {**snap, "updating": True}
    return snap
