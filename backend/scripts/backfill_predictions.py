#!/usr/bin/env python3
"""
Generate model predictions for recently completed ATP matches, independent of
The Odds API entirely.

The Odds API only covers Slams/Masters/the bigger 500s — lower-tier ATP 250s
never appear there, so collect.py's prediction stream never sees them. This
script instead scans stats.tennismylife.org's results (same source used to
extend ATP_Matches/, covers every tournament level) for matches not yet in
our store, and predicts each one. Since the match already happened by the
time it shows up there, the result is known immediately — these entries are
stored already-settled, with no odds (bookmakers: {}) since none exist for
most of what this finds.

A match already collected via the Odds-API path (collect.py) is skipped here
even if it's also in TML's results — update_results.py's existing passes
settle those.

No API key needed. Costs zero Odds API credits.

Usage:
    cd backend && python scripts/backfill_predictions.py
    cd backend && python scripts/backfill_predictions.py --days 30
"""
import argparse
import csv
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import joblib

from data.loader  import load_all_matches, PlayerDB
from data.store   import load_all, upsert, summary
from ml.features  import build_feature_vector

MODEL_PATH    = Path(__file__).resolve().parent.parent / "ml" / "model.joblib"
TML_DATA_URL  = "https://stats.tennismylife.org/data/{year}.csv"
DEDUP_DAYS    = 21  # generous window; tourney_date is the tournament's start, not the match date


def _fetch_tml_matches(year: int) -> list[dict]:
    """Download stats.tennismylife.org's match results for one year. No API key needed."""
    resp = httpx.get(TML_DATA_URL.format(year=year), timeout=20)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def _names_match(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a in b or b in a


def _already_covered(predictions: dict, player1: str, player2: str, tourney_date) -> bool:
    """True if an existing store entry (from collect.py's Odds-API path) already covers this pairing."""
    for pred in predictions.values():
        same_pair = (_names_match(pred["player1"], player1) and _names_match(pred["player2"], player2)) or \
                    (_names_match(pred["player1"], player2) and _names_match(pred["player2"], player1))
        if not same_pair:
            continue
        commence_date = datetime.fromisoformat(pred["commence_time"].replace("Z", "+00:00")).date()
        if abs((commence_date - tourney_date).days) <= DEDUP_DAYS:
            return True
    return False


def run(days: int = 14) -> None:
    print("Loading player database…")
    df    = load_all_matches()
    db    = PlayerDB(df)
    model = joblib.load(MODEL_PATH)
    print(f"  {len(db.profiles):,} profiles  |  model loaded\n")

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    year   = datetime.now(timezone.utc).year

    print(f"Fetching {year} results from stats.tennismylife.org…")
    try:
        rows = _fetch_tml_matches(year)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    recent = []
    for row in rows:
        try:
            tourney_date = datetime.strptime(row["tourney_date"], "%Y%m%d").date()
        except (KeyError, ValueError):
            continue
        if tourney_date >= cutoff:
            recent.append((row, tourney_date))
    print(f"  {len(recent)} match(es) within the last {days} day(s)\n")

    predictions = load_all()
    added = skipped_dup = skipped_covered = skipped_no_match = 0

    for row, tourney_date in recent:
        match_id = f"tml-{row.get('tourney_id', '')}-{row.get('match_num', '')}"
        if match_id in predictions:
            skipped_dup += 1
            continue

        winner_raw = row.get("winner_name", "")
        loser_raw  = row.get("loser_name", "")

        if _already_covered(predictions, winner_raw, loser_raw, tourney_date):
            skipped_covered += 1
            continue

        winner = db.get_player(winner_raw)
        loser  = db.get_player(loser_raw)
        if not winner or not loser:
            missing = [n for n, p in [(winner_raw, winner), (loser_raw, loser)] if p is None]
            print(f"  ⚠  Not in DB: {', '.join(missing)}  ({winner_raw} vs {loser_raw})")
            skipped_no_match += 1
            continue

        surface = row.get("surface") or "Hard"
        h2h     = db.h2h_win_pct(winner["name"], loser["name"])
        fv      = build_feature_vector(winner, loser, surface, h2h).reshape(1, -1)
        probs   = model.predict_proba(fv)[0]
        p1_prob = round(float(probs[1]), 4)
        p2_prob = round(float(probs[0]), 4)
        margin  = abs(p1_prob - p2_prob)
        conf    = "high" if margin >= 0.20 else "medium" if margin >= 0.08 else "low"
        predicted_winner = winner["name"] if p1_prob >= p2_prob else loser["name"]
        correct = predicted_winner == winner["name"]

        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "match_id":      match_id,
            "commence_time": datetime.combine(tourney_date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            "tournament":    row.get("tourney_name", ""),
            "surface":       surface,
            "player1":       winner["name"],
            "player2":       loser["name"],
            "bookmakers":    {},
            "prediction": {
                "p1_name":          winner["name"],
                "p2_name":          loser["name"],
                "p1_prob":          p1_prob,
                "p2_prob":          p2_prob,
                "predicted_winner": predicted_winner,
                "confidence":       conf,
                "p1_edge":          None,
                "p2_edge":          None,
            },
            "collected_at": now,
            "result": {
                "winner":     winner["name"],
                "correct":    correct,
                "settled_at": now,
            },
        }

        upsert(match_id, entry)
        mark = "✓" if correct else "✗"
        print(f"  {mark}  {winner['name'].split()[-1]} d. {loser['name'].split()[-1]}  "
              f"({row.get('tourney_name', '')})  "
              f"predicted: {predicted_winner.split()[-1]} ({p1_prob:.0%}/{p2_prob:.0%}, {conf})")
        added += 1

    print(f"\n  Added {added}  |  {skipped_dup} already stored  |  "
          f"{skipped_covered} already covered via odds  |  {skipped_no_match} no DB match")

    stats = summary()
    print(f"  Store total: {stats['total']} predictions  "
          f"({stats['settled']} settled, {stats['pending']} pending)")
    if stats["accuracy"] is not None:
        print(f"  Running accuracy: {stats['accuracy']:.1%}  "
              f"({stats['correct']}/{stats['settled']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14,
                        help="Look back this many days for new completed matches (default: 14)")
    run(days=parser.parse_args().days)
