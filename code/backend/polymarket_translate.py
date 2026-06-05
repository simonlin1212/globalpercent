"""Translate Polymarket question titles to Chinese via the repo's configured LLM.

Uses ``build_llm()`` (the same MiMo client the dashboard already runs on) and a
persistent JSON cache keyed by the English question — titles are stable, so each
is translated once and reused across restarts. Best-effort: on any config / LLM /
parse error it returns no translation and the panel falls back to English only.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Small batches: mimo-v2.5-pro is a reasoning model; large batches can exhaust the
# completion budget on reasoning tokens and return empty content. A batch of 8 also
# runs ~12s — right at the panel's translation budget, so the server often banks
# zero batches before the timeout. Batch=4 finishes in ~half that, so 2+ batches
# reliably complete and save within the budget, and the cache accumulates each load.
_BATCH = 4
_MAX_TOKENS = 4000
_BATCH_DELAY = 0.8  # pause between batches — bursting all batches trips MiMo's rate limit
_CACHE: dict[str, str] | None = None


def _cache_path() -> Path:
    try:
        from src.config.paths import get_data_dir

        return get_data_dir() / "polymarket_translations.json"
    except Exception:
        return Path.home() / ".vibe-trading" / "polymarket_translations.json"


def _load_cache() -> dict[str, str]:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(_cache_path().read_text("utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            _CACHE = {}
    return _CACHE


def _save_cache() -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_CACHE, ensure_ascii=False), "utf-8")
    except OSError as exc:
        logger.warning("polymarket translation cache save failed: %s", exc)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if "```" in text:
        # pull the block between the first pair of fences
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


async def _translate_batch(questions: list[str]) -> dict[str, str]:
    """One LLM call: numbered EN titles -> {en_question: zh}. Empty on any failure."""
    try:
        from src.providers.llm import build_llm
    except Exception:
        return {}

    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    prompt = (
        "把下面的预测市场标题逐条翻译成简洁自然的中文。"
        "保留人名、地名、机构、缩写（如 Fed、GDP、Nvidia、OpenAI）原样。"
        '只返回一个 JSON 对象，key 为序号字符串，value 为中文译文，不要任何解释或代码块标记。\n\n'
        f"{numbered}"
    )
    try:
        # bind() reliably forwards max_tokens to the API; leave room for reasoning + JSON.
        resp = await build_llm().bind(max_tokens=_MAX_TOKENS).ainvoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        data = _extract_json(text)
    except Exception as exc:  # noqa: BLE001 — best-effort translation
        logger.warning("polymarket translation batch failed: %s", exc)
        return {}

    out: dict[str, str] = {}
    for i, question in enumerate(questions):
        value = data.get(str(i + 1))
        if isinstance(value, str) and value.strip():
            out[question] = value.strip()
    return out


async def _translate_missing(missing: list[str], cache: dict[str, str], max_rounds: int = 6) -> None:
    """Translate uncached titles in batches, saving after each batch (so a timeout
    still banks finished work). A small pause between batches keeps MiMo from
    rate-limiting (bursting every batch back-to-back is what left most titles
    English on a full rebuild). Repeats up to ``max_rounds`` to sweep up stragglers,
    stopping only after two *consecutive* no-progress rounds so one transient
    rate-limited round doesn't abort the whole sweep."""
    stalls = 0
    for _ in range(max_rounds):
        remaining = [q for q in missing if q not in cache]
        if not remaining:
            return
        progressed = False
        for i in range(0, len(remaining), _BATCH):
            before = len(cache)
            cache.update(await _translate_batch(remaining[i : i + _BATCH]))
            _save_cache()
            if len(cache) > before:
                progressed = True
            await asyncio.sleep(_BATCH_DELAY)
        stalls = 0 if progressed else stalls + 1
        if stalls >= 2:
            return


async def translate_questions(questions: list[str], llm_timeout: float = 20.0) -> dict[str, str]:
    """Return ``{en_question: zh}`` for the given titles.

    Cached titles resolve instantly; only uncached ones hit the LLM, and *only that
    work* is bounded by ``llm_timeout``. On timeout we still return every cache hit —
    the old design wrapped the whole call in the timeout, so a few slow LLM batches
    would discard the ready cache hits too (panel went all-English). Uncached titles
    self-heal into the cache across later loads.
    """
    cache = _load_cache()
    unique = list(dict.fromkeys(q for q in questions if q))
    missing = [q for q in unique if q not in cache]
    if missing:
        try:
            await asyncio.wait_for(_translate_missing(missing, cache), timeout=llm_timeout)
        except Exception:  # noqa: BLE001 — best-effort (incl. asyncio.TimeoutError)
            pass  # finished batches are already in `cache`; hits returned below
    return {q: cache[q] for q in unique if q in cache}
