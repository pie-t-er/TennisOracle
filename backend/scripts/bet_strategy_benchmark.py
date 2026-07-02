#!/usr/bin/env python3
"""
Benchmark betting-selection strategies against the settled prediction history.

Two independent sweeps:
  1. Confidence margin (all settled predictions) — how accuracy and simulated
     P&L change as we raise the required |p1_prob - p2_prob| threshold.
     P&L is computed at fair odds (1 / model_prob) since most backfill
     predictions have no bookmaker lines; this shows whether selectivity
     helps the model itself, independent of market pricing.

  2. Edge threshold (settled predictions WITH bookmaker odds only) — sweeps
     the minimum "model edge" (model_prob − market_implied_prob) required to
     place a bet, using best available bookmaker decimal odds for actual P&L.
     Also tests combinations with a confidence floor.

Usage:
    cd backend && python scripts/bet_strategy_benchmark.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.store import load_all

STAKE = 10.0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _margin(pred: dict) -> float:
    p = pred["prediction"]
    return abs(p["p1_prob"] - p["p2_prob"])


def _winner_prob(pred: dict) -> float:
    p = pred["prediction"]
    return p["p1_prob"] if p["predicted_winner"] == p["p1_name"] else p["p2_prob"]


def _winner_edge(pred: dict) -> float | None:
    p = pred["prediction"]
    if p["predicted_winner"] == p["p1_name"]:
        return p.get("p1_edge")
    return p.get("p2_edge")


def _best_odds_for_player(bookmakers: dict, name: str) -> float | None:
    target = name.lower()
    best = None
    for book in bookmakers.values():
        for player, odds in book.items():
            if player.lower() == target and (best is None or odds > best):
                best = odds
    return best


def _bet_pnl(pred: dict) -> float | None:
    """Actual P&L at best bookmaker decimal odds. None if no odds available."""
    bm = pred.get("bookmakers") or {}
    if not bm:
        return None
    winner_name = pred["prediction"]["predicted_winner"]
    odds = _best_odds_for_player(bm, winner_name)
    if odds is None:
        return None
    return round(STAKE * (odds - 1), 2) if pred["result"]["correct"] else -STAKE


def _fair_pnl(pred: dict) -> float:
    """Simulated P&L at fair odds (1 / model_prob). Always available."""
    p = _winner_prob(pred)
    fair_odds = 1.0 / p if p > 0 else 1.0
    return round(STAKE * (fair_odds - 1), 2) if pred["result"]["correct"] else -STAKE


def _stats(subset: list[dict], use_real_odds: bool = False) -> dict:
    if not subset:
        return dict(n=0, accuracy=0.0, pnl=0.0, roi=0.0)
    correct = sum(1 for p in subset if p["result"]["correct"])
    if use_real_odds:
        pnls = [_bet_pnl(p) for p in subset]
        pnls = [x for x in pnls if x is not None]
        pnl = sum(pnls)
        staked = len(pnls) * STAKE
        n = len(pnls)
    else:
        pnls = [_fair_pnl(p) for p in subset]
        pnl = sum(pnls)
        staked = len(subset) * STAKE
        n = len(subset)
    return dict(
        n=n,
        accuracy=correct / len(subset) if subset else 0.0,
        pnl=round(pnl, 2),
        roi=round(pnl / staked * 100, 1) if staked > 0 else 0.0,
    )


def _fmt(s: dict) -> str:
    return (f"n={s['n']:>4}  acc={s['accuracy']:.1%}  "
            f"P&L={s['pnl']:>+8.2f}  ROI={s['roi']:>+6.1f}%")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run() -> None:
    all_preds = load_all()
    settled = [v for v in all_preds.values() if v.get("result")]
    settled_odds = [v for v in settled if v.get("bookmakers")]

    print(f"Settled predictions: {len(settled)}")
    print(f"  → with bookmaker odds: {len(settled_odds)}")
    print()

    # -----------------------------------------------------------------------
    # Section 1: Accuracy + fair-odds P&L by confidence margin threshold
    # (all settled, no real-money bookmaker required)
    # -----------------------------------------------------------------------
    print("=" * 68)
    print("SWEEP 1 — Confidence margin threshold (all settled, fair-odds P&L)")
    print("          Higher threshold = more selective = fewer bets")
    print("=" * 68)
    print(f"  threshold   {'n':>4}   accuracy   fair P&L    fair ROI")
    print("-" * 68)

    thresholds = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    for t in thresholds:
        subset = [p for p in settled if _margin(p) >= t]
        s = _stats(subset)
        label = f"≥{t:.2f}"
        print(f"  {label:<10}  {_fmt(s)}")

    # -----------------------------------------------------------------------
    # Section 2: By confidence label
    # -----------------------------------------------------------------------
    print()
    print("=" * 68)
    print("SWEEP 2 — By model confidence label (all settled, fair-odds P&L)")
    print("=" * 68)
    print(f"  label         {'n':>4}   accuracy   fair P&L    fair ROI")
    print("-" * 68)
    for label in ("high", "medium", "low"):
        subset = [p for p in settled if p["prediction"]["confidence"] == label]
        s = _stats(subset)
        print(f"  {label:<14}  {_fmt(s)}")

    # -----------------------------------------------------------------------
    # Section 3: Edge threshold (settled-with-odds only, real bookmaker P&L)
    # -----------------------------------------------------------------------
    if not settled_odds:
        print("\n  (No settled predictions with bookmaker odds — skipping edge sweep)")
        return

    print()
    print("=" * 68)
    print("SWEEP 3 — Model-edge threshold (settled-with-odds, real-odds P&L)")
    print("          Edge = model_prob − market_implied_prob for predicted winner")
    print("=" * 68)
    print(f"  min edge    {'n':>4}   accuracy   real P&L    real ROI")
    print("-" * 68)

    edge_thresholds = [-0.20, -0.10, 0.00, 0.05, 0.10, 0.15, 0.20, 0.25]
    for t in edge_thresholds:
        subset = [p for p in settled_odds
                  if (_winner_edge(p) is not None and _winner_edge(p) >= t)]
        s = _stats(subset, use_real_odds=True)
        label = f"≥{t:+.2f}"
        print(f"  {label:<10}  {_fmt(s)}")

    # -----------------------------------------------------------------------
    # Section 4: Combined margin + edge (settled-with-odds, real P&L)
    # -----------------------------------------------------------------------
    print()
    print("=" * 68)
    print("SWEEP 4 — Combined: margin threshold × edge threshold (real-odds P&L)")
    print("=" * 68)
    margin_floors = [0.10, 0.20, 0.30]
    edge_floors   = [0.00, 0.05, 0.10, 0.15]

    header = f"  {'margin':>8}  {'edge':>6}  " + "  ".join(f"{'n':>4} acc P&L ROI" for _ in edge_floors)
    print(f"  {'margin':>8}  ", end="")
    for ef in edge_floors:
        print(f"  edge≥{ef:+.2f}  ", end="")
    print()
    print("-" * 68)

    for mf in margin_floors:
        print(f"  margin≥{mf:.2f}  ", end="")
        for ef in edge_floors:
            subset = [
                p for p in settled_odds
                if _margin(p) >= mf
                and (_winner_edge(p) is not None and _winner_edge(p) >= ef)
            ]
            s = _stats(subset, use_real_odds=True)
            print(f"  n={s['n']:>3} acc={s['accuracy']:.0%} P&L={s['pnl']:>+7.1f} ROI={s['roi']:>+5.1f}%  ", end="")
        print()

    # -----------------------------------------------------------------------
    # Section 5: Surface breakdown (all settled)
    # -----------------------------------------------------------------------
    print()
    print("=" * 68)
    print("SWEEP 5 — Surface breakdown (all settled, fair-odds P&L)")
    print("=" * 68)
    print(f"  surface       {'n':>4}   accuracy   fair P&L    fair ROI")
    print("-" * 68)
    surfaces = sorted({p.get("surface", "Unknown") for p in settled})
    for surf in surfaces:
        subset = [p for p in settled if p.get("surface") == surf]
        s = _stats(subset)
        print(f"  {surf:<14}  {_fmt(s)}")

    # -----------------------------------------------------------------------
    # Section 6: Individual settled-with-odds bets (detail view)
    # -----------------------------------------------------------------------
    if settled_odds:
        print()
        print("=" * 68)
        print("DETAIL — All settled predictions with bookmaker odds")
        print("=" * 68)
        print(f"  {'Match':<32}  {'margin':>6}  {'edge':>6}  {'odds':>5}  {'P&L':>7}  {'correct'}")
        print("-" * 68)
        for p in sorted(settled_odds, key=lambda x: x["commence_time"]):
            pred = p["prediction"]
            name = f"{pred['predicted_winner'].split()[-1]} vs {(pred['p2_name'] if pred['predicted_winner'] == pred['p1_name'] else pred['p1_name']).split()[-1]}"
            odds = _best_odds_for_player(p["bookmakers"], pred["predicted_winner"])
            edge = _winner_edge(p)
            pnl  = _bet_pnl(p)
            print(f"  {name:<32}  {_margin(p):>6.3f}  {edge:>+6.3f}  "
                  f"{(odds or 0):>5.2f}  {(pnl or 0):>+7.2f}  {'✓' if p['result']['correct'] else '✗'}")


if __name__ == "__main__":
    run()
