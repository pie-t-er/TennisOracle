#!/usr/bin/env python3
"""
Recompute predictions for still-pending matches using the current model.

Run this after retraining (ml/train.py) so pending predictions reflect the
new model rather than whatever was loaded at collection time. Settled
matches are never touched - rewriting what an improved model would have
guessed for a known outcome would corrupt the historical track record
rather than reflect it (data.store.update_prediction enforces this).

Usage:
    cd backend && python scripts/remodel_pending.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
from data.loader import load_all_matches, PlayerDB
from data.store  import load_all, update_prediction
from ml.features import build_feature_vector

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "model.joblib"


def match_player(name: str, db: PlayerDB):
    """Exact → last-name → substring fallback. Mirrors collect.py's resolver."""
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


def best_odds_for(bookmakers: dict, name: str):
    """Best decimal odds across all bookmakers for a player, or None."""
    prices = [book[name] for book in bookmakers.values() if name in book]
    return max(prices) if prices else None


def run() -> None:
    print("Loading player database…")
    df    = load_all_matches()
    db    = PlayerDB(df)
    model = joblib.load(MODEL_PATH)
    print(f"  {len(db.profiles):,} profiles  |  model loaded\n")

    predictions = load_all()
    pending = [(mid, p) for mid, p in predictions.items() if not p.get("result")]
    print(f"{len(pending)} pending prediction(s) to remodel\n")

    updated = no_match = 0

    for match_id, pred in pending:
        p1 = match_player(pred["player1"], db)
        p2 = match_player(pred["player2"], db)
        if not p1 or not p2:
            missing = [n for n, p in [(pred["player1"], p1), (pred["player2"], p2)] if p is None]
            print(f"  ⚠  Not in DB: {', '.join(missing)}  ({pred['player1']} vs {pred['player2']})")
            no_match += 1
            continue

        h2h    = db.h2h_win_pct(p1["name"], p2["name"])
        fv     = build_feature_vector(p1, p2, pred["surface"], h2h).reshape(1, -1)
        probs  = model.predict_proba(fv)[0]
        p1_prob = round(float(probs[1]), 4)
        p2_prob = round(float(probs[0]), 4)
        margin  = abs(p1_prob - p2_prob)
        conf    = "high" if margin >= 0.20 else "medium" if margin >= 0.08 else "low"
        winner  = p1["name"] if p1_prob >= p2_prob else p2["name"]

        p1_odds = best_odds_for(pred["bookmakers"], pred["player1"])
        p2_odds = best_odds_for(pred["bookmakers"], pred["player2"])
        p1_edge = round(p1_prob - 1 / p1_odds, 4) if p1_odds else None
        p2_edge = round(p2_prob - 1 / p2_odds, 4) if p2_odds else None

        old_winner = pred["prediction"]["predicted_winner"]
        new_prediction = {
            "p1_name":          p1["name"],
            "p2_name":          p2["name"],
            "p1_prob":          p1_prob,
            "p2_prob":          p2_prob,
            "predicted_winner": winner,
            "confidence":       conf,
            "p1_edge":          p1_edge,
            "p2_edge":          p2_edge,
        }

        if update_prediction(match_id, new_prediction):
            changed = " (pick changed)" if winner != old_winner else ""
            print(f"  {pred['player1'].split()[-1]} vs {pred['player2'].split()[-1]}  →  "
                  f"{winner.split()[-1]} ({p1_prob:.0%}/{p2_prob:.0%}, {conf}){changed}")
            updated += 1

    print(f"\n  Remodeled {updated}  |  {no_match} skipped (no DB match)")


if __name__ == "__main__":
    run()
