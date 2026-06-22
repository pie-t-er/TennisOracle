#!/usr/bin/env python3
"""
Pull completed ATP scores from The Odds API and update any matching
predictions in the store with the actual result.

Costs 1 credit per run regardless of how many results are found.
Run this daily (or after big match days) to track model accuracy.

Usage:
    cd backend && python scripts/update_results.py
    cd backend && python scripts/update_results.py --days 5  # look back 5 days
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from data.store  import load_all, update_result, summary
from odds_client import fetch_scores


def _winner_from_scores(score_list: list) -> str | None:
    """
    The Odds API returns scores like [{"name": "Sinner", "score": "3"}, ...].
    For tennis the score is sets won, so the player with the higher number won.
    Returns the winner's name, or None if the scores can't be parsed.
    """
    if not score_list or len(score_list) < 2:
        return None
    try:
        entries = [(s["name"], int(s.get("score") or 0)) for s in score_list]
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries[0][0]
    except (KeyError, ValueError, TypeError):
        return None


def _names_match(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a in b or b in a


def run(days: int = 3) -> None:
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        print("ERROR: ODDS_API_KEY not set — add it to backend/.env")
        sys.exit(1)

    print(f"Fetching scores for the last {days} day(s)…")
    try:
        all_scores = fetch_scores(api_key, days_from=days)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    completed = [s for s in all_scores if s.get("completed")]
    print(f"  {len(completed)} completed matches\n")

    predictions = load_all()
    updated = already = not_in_store = 0

    for match in completed:
        match_id = match["id"]

        if match_id not in predictions:
            not_in_store += 1
            continue

        pred = predictions[match_id]
        if pred.get("result"):
            already += 1
            continue

        winner_name = _winner_from_scores(match.get("scores", []))
        if not winner_name:
            print(f"  ⚠  Could not parse winner for {pred['player1']} vs {pred['player2']}")
            continue

        predicted = pred["prediction"]["predicted_winner"]
        correct   = _names_match(winner_name, predicted)

        update_result(match_id, winner_name, correct)

        mark = "✓" if correct else "✗"
        p1l  = pred["player1"].split()[-1]
        p2l  = pred["player2"].split()[-1]
        print(f"  {mark}  {p1l} vs {p2l}")
        print(f"     Predicted: {predicted.split()[-1]}  "
              f"({pred['prediction']['p1_prob']:.0%} / {pred['prediction']['p2_prob']:.0%})")
        print(f"     Actual:    {winner_name}")
        print()
        updated += 1

    print(f"  {updated} results recorded  |  "
          f"{already} already settled  |  "
          f"{not_in_store} completed matches not in store")

    stats = summary()
    if stats["settled"]:
        acc = stats["accuracy"]
        print(f"\n  Running accuracy: {acc:.1%}  "
              f"({stats['correct']}/{stats['settled']} settled)")
        print(f"  Pending results:  {stats['pending']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3,
                        help="Days to look back for completed matches (default: 3, max: 3 on free plan)")
    run(days=parser.parse_args().days)
