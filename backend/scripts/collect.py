#!/usr/bin/env python3
"""
Fetch upcoming ATP matches from The Odds API, run the model, and save
predictions to backend/data/live_predictions.json.

Safe to run repeatedly — already-stored predictions are never overwritten.

Usage:
    cd backend && python scripts/collect.py
    cd backend && python scripts/collect.py --force   # bypass odds cache
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import joblib
from data.loader import load_all_matches, PlayerDB
from data.store  import upsert, summary
from ml.features import build_feature_vector
from odds_client import (
    fetch_upcoming,
    all_book_odds,
    best_odds,
    infer_surface,
)

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "model.joblib"


def match_player(name: str, db: PlayerDB):
    """Exact → last-name → substring fallback."""
    p = db.get_player(name)
    if p:
        return p
    last = name.split()[-1].lower()
    for pname, profile in db.profiles.items():
        if pname.split()[-1].lower() == last:
            return profile
    for pname, profile in db.profiles.items():
        if name.lower() in pname.lower() or pname.lower() in name.lower():
            return profile
    return None


def run(force: bool = False) -> None:
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        print("ERROR: ODDS_API_KEY not set — add it to backend/.env")
        sys.exit(1)

    print("Loading player database…")
    df    = load_all_matches()
    db    = PlayerDB(df)
    model = joblib.load(MODEL_PATH)
    print(f"  {len(db.profiles):,} profiles  |  model loaded\n")

    ttl = int(os.getenv("ODDS_CACHE_TTL", "900"))
    print("Fetching upcoming ATP odds" + (" (forced, bypassing cache)…" if force else "…"))
    try:
        events = fetch_upcoming(api_key, ttl=ttl, force=force)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"  {len(events)} upcoming events\n")

    saved = skipped = no_match = 0

    for ev in events:
        home    = ev.get("home_team", "")
        away    = ev.get("away_team", "")
        title   = ev.get("_sport_title", ev.get("sport_title", "")) or ""
        surface = infer_surface(sport_key=ev.get("_sport_key", ""), title=title)

        p1 = match_player(home, db)
        p2 = match_player(away, db)

        if not p1 or not p2:
            missing = [n for n, p in [(home, p1), (away, p2)] if p is None]
            print(f"  ⚠  Not in DB: {', '.join(missing)}  ({home} vs {away})")
            no_match += 1
            continue

        h2h    = db.h2h_win_pct(p1["name"], p2["name"])
        fv     = build_feature_vector(p1, p2, surface, h2h).reshape(1, -1)
        probs  = model.predict_proba(fv)[0]
        p1_prob = round(float(probs[1]), 4)
        p2_prob = round(float(probs[0]), 4)
        margin  = abs(p1_prob - p2_prob)
        conf    = "high" if margin >= 0.20 else "medium" if margin >= 0.08 else "low"
        winner  = p1["name"] if p1_prob >= p2_prob else p2["name"]

        # Value edge vs best available odds
        best = best_odds(ev)
        p1_edge = p2_edge = None
        if home in best:
            p1_edge = round(p1_prob - 1 / best[home], 4)
        if away in best:
            p2_edge = round(p2_prob - 1 / best[away], 4)

        entry = {
            "match_id":      ev["id"],
            "commence_time": ev.get("commence_time"),
            "tournament":    title,
            "surface":       surface,
            "player1":       home,
            "player2":       away,
            "bookmakers":    all_book_odds(ev),
            "prediction": {
                "p1_name":          p1["name"],
                "p2_name":          p2["name"],
                "p1_prob":          p1_prob,
                "p2_prob":          p2_prob,
                "predicted_winner": winner,
                "confidence":       conf,
                "p1_edge":          p1_edge,
                "p2_edge":          p2_edge,
            },
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "result":       None,
        }

        is_new = upsert(ev["id"], entry)
        if is_new:
            p1_last = home.split()[-1]
            p2_last = away.split()[-1]
            edge_str = ""
            top_edge = max(
                (e for e in [p1_edge, p2_edge] if e is not None),
                default=None,
            )
            if top_edge is not None:
                edge_str = f"  edge {top_edge:+.1%}"
            print(f"  + {p1_last} vs {p2_last}  →  {winner.split()[-1]} "
                  f"({p1_prob:.0%}/{p2_prob:.0%}, {conf}){edge_str}")
            saved += 1
        else:
            skipped += 1

    stats = summary()
    print(f"\n  Saved {saved} new  |  {skipped} already stored  |  {no_match} skipped (no DB match)")
    print(f"  Store total: {stats['total']} predictions  "
          f"({stats['settled']} settled, {stats['pending']} pending)")
    if stats["accuracy"] is not None:
        print(f"  Running accuracy: {stats['accuracy']:.1%}  "
              f"({stats['correct']}/{stats['settled']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Bypass odds cache and fetch fresh data (costs 1 credit)")
    run(force=parser.parse_args().force)
