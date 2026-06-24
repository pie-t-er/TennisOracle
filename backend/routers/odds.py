"""
/api/odds/upcoming  — upcoming matches with live bookmaker odds + our prediction
/api/odds/predictions — all stored predictions (pending + settled)
/api/odds/summary   — accuracy stats
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from data.loader  import PlayerDB
from data.store   import load_all, summary as store_summary
from ml.features  import build_feature_vector
from odds_client  import (
    all_book_odds, best_odds, fetch_upcoming, infer_surface,
)

router = APIRouter(prefix="/api/odds")

_db:    Optional[PlayerDB] = None
_model = None


def init(db: PlayerDB, model) -> None:
    global _db, _model
    _db, _model = db, model


# ── Name matching ─────────────────────────────────────────────────────────────

def _match(name: str) -> Optional[dict]:
    """Exact → last-name → substring fallback into the player DB."""
    if _db is None:
        return None
    p = _db.get_player(name)
    if p:
        return p
    last = name.split()[-1].lower()
    for pname, profile in _db.profiles.items():
        if pname.split()[-1].lower() == last:
            return profile
    for pname, profile in _db.profiles.items():
        if name.lower() in pname.lower() or pname.lower() in name.lower():
            return profile
    return None


def _predict(p1_api: str, p2_api: str, surface: str) -> Optional[dict]:
    if _db is None or _model is None:
        return None
    p1 = _match(p1_api)
    p2 = _match(p2_api)
    if not p1 or not p2:
        return None

    h2h    = _db.h2h_win_pct(p1["name"], p2["name"])
    fv     = build_feature_vector(p1, p2, surface, h2h).reshape(1, -1)
    probs  = _model.predict_proba(fv)[0]
    p1_prob = round(float(probs[1]), 4)
    p2_prob = round(float(probs[0]), 4)
    margin  = abs(p1_prob - p2_prob)

    return {
        "p1_name":          p1["name"],
        "p2_name":          p2["name"],
        "p1_prob":          p1_prob,
        "p2_prob":          p2_prob,
        "predicted_winner": p1["name"] if p1_prob >= p2_prob else p2["name"],
        "confidence":       "high" if margin >= 0.20 else "medium" if margin >= 0.08 else "low",
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/upcoming")
def upcoming(
    force: bool = Query(False, description="Bypass cache — costs 1 credit"),
):
    """
    Upcoming ATP matches with bookmaker H2H odds and our model's prediction.
    Responses are cached for ODDS_CACHE_TTL seconds (default 15 min).

    Read-only — does not persist to the predictions store. Storage is handled
    solely by scripts/collect.py (run on a schedule via GitHub Actions) so the
    store stays in sync with git instead of drifting on Render's ephemeral
    disk between redeploys.
    """
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ODDS_API_KEY is not configured on the server")

    ttl = int(os.getenv("ODDS_CACHE_TTL", "900"))
    try:
        events = fetch_upcoming(api_key, ttl=ttl, force=force)
    except Exception as e:
        raise HTTPException(502, f"Odds API error: {e}")

    results = []
    for ev in events:
        home    = ev.get("home_team", "")
        away    = ev.get("away_team", "")
        title   = ev.get("_sport_title", ev.get("sport_title", "")) or ""
        surface = infer_surface(sport_key=ev.get("_sport_key", ""), title=title)

        pred  = _predict(home, away, surface)
        b_all = all_book_odds(ev)
        b_best = best_odds(ev)

        # Annotate prediction with value edges vs best available odds
        if pred and b_best:
            p1_odds = b_best.get(home)
            p2_odds = b_best.get(away)
            if p1_odds:
                pred["p1_edge"] = round(pred["p1_prob"] - 1 / p1_odds, 4)
            if p2_odds:
                pred["p2_edge"] = round(pred["p2_prob"] - 1 / p2_odds, 4)

        entry = {
            "match_id":      ev["id"],
            "commence_time": ev.get("commence_time"),
            "tournament":    title,
            "surface":       surface,
            "player1":       home,
            "player2":       away,
            "best_odds":     b_best,
            "bookmakers":    b_all,
            "prediction":    pred,
        }

        results.append(entry)

    return results


@router.get("/predictions")
def predictions(settled_only: bool = Query(False)):
    """All stored predictions, newest first. Pass settled_only=true for results only."""
    preds = list(load_all().values())
    if settled_only:
        preds = [p for p in preds if p.get("result")]
    preds.sort(key=lambda p: p.get("collected_at", ""), reverse=True)
    return preds


@router.get("/summary")
def accuracy_summary():
    """Running accuracy across all settled predictions."""
    return store_summary()
