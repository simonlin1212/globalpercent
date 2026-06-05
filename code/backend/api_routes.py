"""FastAPI route snippets for the event-probability panel.

Drop these into your existing FastAPI app (or translate to your web framework).
The routes are READ-ONLY public data, so they need no auth — mirror however your
other read-only endpoints are declared.
"""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/pulse/overview")
async def get_pulse_overview(
    refresh: bool = Query(False, description="Bypass the snapshot and re-pull both sources"),
):
    """Whole-market probability overview: Polymarket + Kalshi merged, grouped by module.

    Read-only public market data (no auth, no account). Normal loads serve a pinned
    snapshot instantly; refresh kicks off an async background rebuild and returns the
    current snapshot with ``updating: true`` (the frontend polls until ``as_of`` advances).
    """
    from market_pulse import fetch_overview

    try:
        return await fetch_overview(force=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market pulse fetch failed: {exc}")


@router.get("/polymarket/history")
async def get_polymarket_history(
    token_id: str = Query(..., description="CLOB token id (Yes outcome) from the overview"),
    interval: str = Query("1w", description="1d, 1w, 1m, or max"),
):
    """Probability time series for one Polymarket outcome (the trend chart).

    Kalshi has no equivalent simple history token, so only Polymarket rows carry a
    ``token_id_yes`` and therefore a trend chart.
    """
    from polymarket_signals import fetch_history

    try:
        return {"history": await fetch_history(token_id=token_id, interval=interval)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Polymarket history fetch failed: {exc}")
