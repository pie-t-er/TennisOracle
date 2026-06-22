#!/usr/bin/env python3
"""
TennisOracle — Retroactive Backtest
====================================
Runs the trained model against historical 2024 ATP matches and compares
predictions against actual results and approximate bookmaker odds.

Usage (from the repo root):
    cd backend && python scripts/backtest.py

Options:
    --edge <float>   Minimum model edge to qualify a simulated bet (default: 0.05 = 5%)
    --no-color       Disable ANSI colour output
"""
import sys
import os
import json
import argparse
from pathlib import Path

# Allow imports from backend/ regardless of working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import numpy as np
import joblib

from data.loader import load_all_matches, PlayerDB
from ml.features import build_feature_vector

MODEL_PATH = BACKEND_DIR / "ml" / "model.joblib"
FIXTURES   = BACKEND_DIR / "fixtures" / "sample_matches.json"

# ── Terminal colours ──────────────────────────────────────────────────────────

class C:
    GRN = "\033[92m"
    RED = "\033[91m"
    YLW = "\033[93m"
    BLD = "\033[1m"
    DIM = "\033[2m"
    RST = "\033[0m"

    @classmethod
    def disable(cls):
        cls.GRN = cls.RED = cls.YLW = cls.BLD = cls.DIM = cls.RST = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def implied_prob(decimal_odds: float) -> float:
    """Decimal odds → implied probability (raw, no vig removal)."""
    return 1.0 / decimal_odds


def _short(name: str) -> str:
    """'Carlos Alcaraz' → 'Alcaraz'"""
    return name.split()[-1]


# ── Core backtest ─────────────────────────────────────────────────────────────

def run(edge_threshold: float = 0.05) -> None:
    print(f"\n{C.BLD}Loading player database…{C.RST}")
    df = load_all_matches()
    db = PlayerDB(df)
    print(f"  {len(db.profiles):,} profiles | data through {df['tourney_date'].max().date()}")

    model = joblib.load(MODEL_PATH)
    print(f"  Model loaded from {MODEL_PATH.name}")

    with open(FIXTURES) as f:
        data = json.load(f)
    matches = data["matches"]
    print(f"  {len(matches)} fixtures loaded\n")

    rows    = []
    skipped = []

    for m in matches:
        p1_name, p2_name = m["player1"], m["player2"]
        p1 = db.get_player(p1_name)
        p2 = db.get_player(p2_name)

        if p1 is None or p2 is None:
            missing = [n for n, p in [(p1_name, p1), (p2_name, p2)] if p is None]
            skipped.append({"id": m["id"], "missing": missing})
            continue

        h2h  = db.h2h_win_pct(p1_name, p2_name)
        fv   = build_feature_vector(p1, p2, m["surface"], h2h).reshape(1, -1)
        prob = model.predict_proba(fv)[0]
        p1_prob = float(prob[1])
        p2_prob = float(prob[0])

        predicted = "player1" if p1_prob >= p2_prob else "player2"
        correct   = predicted == m["winner"]

        # Bookmaker analysis (use first book entry if multiple)
        book_data = None
        for book_name, odds in m.get("odds", {}).items():
            p1_odds = odds.get("player1")
            p2_odds = odds.get("player2")
            if p1_odds and p2_odds:
                p1_imp  = implied_prob(p1_odds)
                p2_imp  = implied_prob(p2_odds)
                book_data = {
                    "book":    book_name,
                    "p1_odds": p1_odds,
                    "p2_odds": p2_odds,
                    "p1_imp":  p1_imp,
                    "p2_imp":  p2_imp,
                    "p1_edge": p1_prob - p1_imp,
                    "p2_edge": p2_prob - p2_imp,
                }
                break

        rows.append({
            "match":     m,
            "p1_prob":   p1_prob,
            "p2_prob":   p2_prob,
            "predicted": predicted,
            "correct":   correct,
            "book":      book_data,
        })

    _print_report(rows, skipped, edge_threshold)


# ── Report ────────────────────────────────────────────────────────────────────

def _print_report(rows: list, skipped: list, edge_threshold: float) -> None:
    sep = "─" * 96

    print(f"{C.BLD}{'=' * 96}{C.RST}")
    print(f"{C.BLD}  TennisOracle — Retroactive Backtest  "
          f"(2024, out-of-sample){C.RST}")
    print(f"{C.BLD}{'=' * 96}{C.RST}\n")

    # ── Per-match table ───────────────────────────────────────────────────────
    hdr = (f"  {'Tournament':<22} {'Date':<12} {'Match':<26} "
           f"{'Our P1%':>8} {'Book P1%':>9} {'Edge':>7}  {'OK?':>4}")
    print(f"{C.BLD}{hdr}{C.RST}")
    print(f"  {sep}")

    for r in rows:
        m         = r["match"]
        p1s       = _short(m["player1"])
        p2s       = _short(m["player2"])
        match_str = f"{p1s} vs {p2s}"

        our_p1_pct   = f"{r['p1_prob']*100:5.1f}%"

        if r["book"]:
            bd           = r["book"]
            book_p1_pct  = f"{bd['p1_imp']*100:5.1f}%"
            edge         = bd["p1_edge"]
            edge_str     = f"{edge*100:+5.1f}%"
            edge_col     = C.GRN if edge > 0.03 else (C.YLW if edge > -0.03 else C.RED)
        else:
            book_p1_pct  = "   N/A"
            edge_str     = "   N/A"
            edge_col     = C.DIM

        ok_col = C.GRN if r["correct"] else C.RED
        ok_str = "✓" if r["correct"] else "✗"

        # Dim retired/injury-tainted matches
        dim = C.DIM if m.get("notes") and any(
            w in m["notes"].lower() for w in ("retired", "injury", "injured")
        ) else ""

        print(
            f"{dim}  {m['tournament']:<22} {m['date']:<12} {match_str:<26}"
            f"  {our_p1_pct:>8}  {book_p1_pct:>8} "
            f"{edge_col}{edge_str:>7}{C.RST}{dim}"
            f"  {ok_col}{ok_str}{C.RST}{dim}"
            + (f"  {C.DIM}({m['notes']}){C.RST}" if m.get("notes") else "")
        )

    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    total   = len(rows)
    correct = sum(1 for r in rows if r["correct"])

    # Exclude tainted results (retirement/injury) from accuracy calc
    clean_rows = [
        r for r in rows
        if not any(w in r["match"].get("notes", "").lower()
                   for w in ("retired", "injury", "injured"))
    ]
    clean_correct = sum(1 for r in clean_rows if r["correct"])

    print(f"{C.BLD}  ACCURACY{C.RST}")
    print(f"  {'─' * 44}")
    print(f"  All matches:        {correct}/{total} "
          f"({correct/total*100:.1f}%)")
    if len(clean_rows) != total:
        print(f"  Excl. retirements:  {clean_correct}/{len(clean_rows)} "
              f"({clean_correct/len(clean_rows)*100:.1f}%)")

    # Calibration buckets
    print(f"\n{C.BLD}  CALIBRATION — model confidence vs actual win rate{C.RST}")
    print(f"  {'─' * 44}")
    buckets = {"High (≥65%)": [], "Medium (55–65%)": [], "Low (<55%)": []}
    for r in rows:
        conf = max(r["p1_prob"], r["p2_prob"])
        won  = (r["predicted"] == r["match"]["winner"])
        if conf >= 0.65:
            buckets["High (≥65%)"].append(won)
        elif conf >= 0.55:
            buckets["Medium (55–65%)"].append(won)
        else:
            buckets["Low (<55%)"].append(won)
    for label, results in buckets.items():
        if results:
            rate = sum(results) / len(results) * 100
            bar  = "█" * int(rate / 5)
            print(f"  {label:<18}  {len(results):2d} bets  {rate:5.1f}%  {bar}")

    # ── Flat-bet simulation ───────────────────────────────────────────────────
    print(f"\n{C.BLD}  FLAT-BET SIMULATION  "
          f"(bet $100 where model edge > +{edge_threshold*100:.0f}%){C.RST}")
    print(f"  {'─' * 44}")

    bet_log = []
    for r in rows:
        if not r["book"]:
            continue
        bd = r["book"]
        # Bet whichever side we think has the edge
        if bd["p1_edge"] >= edge_threshold:
            bet_side = "player1"
            bet_odds = bd["p1_odds"]
            edge     = bd["p1_edge"]
        elif bd["p2_edge"] >= edge_threshold:
            bet_side = "player2"
            bet_odds = bd["p2_odds"]
            edge     = bd["p2_edge"]
        else:
            continue

        won = (bet_side == r["match"]["winner"])
        bet_log.append({
            "match":    r["match"],
            "side":     bet_side,
            "odds":     bet_odds,
            "edge":     edge,
            "won":      won,
        })

    if bet_log:
        n_bets  = len(bet_log)
        n_wins  = sum(1 for b in bet_log if b["won"])
        stake   = n_bets * 100
        returns = sum(b["odds"] * 100 for b in bet_log if b["won"])
        profit  = returns - stake
        roi     = profit / stake * 100
        col     = C.GRN if profit >= 0 else C.RED

        print(f"  Qualifying bets:  {n_bets}")
        print(f"  Won:              {n_wins}/{n_bets} "
              f"({n_wins/n_bets*100:.1f}%)")
        print(f"  Total staked:     ${stake:,.0f}")
        print(f"  Returns:          ${returns:,.0f}")
        print(f"  {col}P&L:              ${profit:+,.0f}  "
              f"({roi:+.1f}% ROI){C.RST}")

        print(f"\n  {'Side':<10} {'Match':<26} {'Odds':>6} {'Edge':>7}  Result")
        print(f"  {'─' * 60}")
        for b in bet_log:
            m    = b["match"]
            side = _short(m[b["side"]])
            res  = f"{C.GRN}WIN{C.RST}" if b["won"] else f"{C.RED}LOSS{C.RST}"
            print(f"  {side:<10} {_short(m['player1'])+' v '+_short(m['player2']):<26}"
                  f"  {b['odds']:>5.2f}  {b['edge']*100:>+5.1f}%  {res}")
    else:
        print(f"  No bets met the +{edge_threshold*100:.0f}% edge threshold.")

    # ── Skipped ───────────────────────────────────────────────────────────────
    if skipped:
        print(f"\n{C.YLW}  ⚠  Skipped {len(skipped)} matches (player not found in DB):{C.RST}")
        for s in skipped:
            print(f"     {s['id']}: {', '.join(s['missing'])}")
        print(f"{C.DIM}  Tip: these players may have very few matches in the 2010–2023 data.{C.RST}")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TennisOracle retroactive backtest")
    parser.add_argument("--edge",     type=float, default=0.05,
                        help="Min model edge to place a simulated bet (default: 0.05)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour output")
    args = parser.parse_args()

    if args.no_color:
        C.disable()

    run(edge_threshold=args.edge)
