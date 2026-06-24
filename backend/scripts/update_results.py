#!/usr/bin/env python3
"""
Pull completed ATP scores from The Odds API and update any matching
predictions in the store with the actual result.

Costs 1 credit per run regardless of how many results are found.
Run this daily (or after big match days) to track model accuracy.

The Odds API only reports scores for tournaments it still considers "active" —
once a tournament concludes, its sport key goes inactive and its matches can
never be settled this way, no matter the --days lookback. As a fallback, any
prediction still pending after the Odds API pass is checked against
stats.tennismylife.org's match results (same source used to extend
ATP_Matches/), which has no such "active tournament" limitation.

Usage:
    cd backend && python scripts/update_results.py
    cd backend && python scripts/update_results.py --days 5  # look back 5 days
"""
import argparse
import csv
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from data.store  import load_all, update_result, summary
from odds_client import fetch_scores

TML_DATA_URL = "https://stats.tennismylife.org/data/{year}.csv"


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


def _fetch_tml_matches(year: int) -> list[dict]:
    """Download stats.tennismylife.org's match results for one year. No API key needed."""
    resp = httpx.get(TML_DATA_URL.format(year=year), timeout=20)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def _find_tml_result(rows: list[dict], player1: str, player2: str, commence_iso: str) -> Optional[str]:
    """
    Search TML rows for a match between player1/player2, closest in tourney_date
    to the prediction's commence_time (tourney_date is the tournament's start date,
    not the individual match date, so an exact-date match isn't expected).
    Returns the winner's name as recorded by TML, or None if no match found.
    """
    commence_date = datetime.fromisoformat(commence_iso.replace("Z", "+00:00")).date()

    best_row, best_diff = None, None
    for row in rows:
        w, l = row.get("winner_name", ""), row.get("loser_name", "")
        same_pair = (_names_match(w, player1) and _names_match(l, player2)) or \
                    (_names_match(w, player2) and _names_match(l, player1))
        if not same_pair:
            continue
        try:
            tourney_date = datetime.strptime(row["tourney_date"], "%Y%m%d").date()
        except (KeyError, ValueError):
            continue
        diff = abs((tourney_date - commence_date).days)
        if diff > 21:  # longer than any ATP tournament, including slop
            continue
        if best_diff is None or diff < best_diff:
            best_row, best_diff = row, diff

    return best_row["winner_name"] if best_row else None


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

    # --- Fallback: predictions still pending past their match time (likely
    # because The Odds API stopped tracking their now-concluded tournament) ---
    now = datetime.now(timezone.utc)
    predictions = load_all()  # reload in case the pass above updated anything
    still_pending = [
        (mid, p) for mid, p in predictions.items()
        if not p.get("result")
        and datetime.fromisoformat(p["commence_time"].replace("Z", "+00:00")) < now
    ]

    if still_pending:
        years = sorted({
            datetime.fromisoformat(p["commence_time"].replace("Z", "+00:00")).year
            for _, p in still_pending
        })
        print(f"\n{len(still_pending)} pending prediction(s) past their match time — "
              f"checking stats.tennismylife.org fallback (year(s) {years})…")

        tml_rows: list[dict] = []
        for year in years:
            try:
                tml_rows.extend(_fetch_tml_matches(year))
            except Exception as e:
                print(f"  ⚠  Could not fetch TML data for {year}: {e}")

        tml_updated = 0
        for match_id, pred in still_pending:
            winner_name = _find_tml_result(
                tml_rows, pred["player1"], pred["player2"], pred["commence_time"]
            )
            if not winner_name:
                continue

            predicted = pred["prediction"]["predicted_winner"]
            correct   = _names_match(winner_name, predicted)
            update_result(match_id, winner_name, correct)

            mark = "✓" if correct else "✗"
            print(f"  {mark}  {pred['player1'].split()[-1]} vs {pred['player2'].split()[-1]} "
                  f"(via TML)  Actual: {winner_name}")
            tml_updated += 1

        print(f"  {tml_updated} result(s) recorded via TML fallback")

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
