"""Feature engineering for inference. Must stay in sync with train.py."""
from typing import Dict, Optional

import numpy as np

FEATURE_NAMES = [
    # Player 1
    "p1_hand",
    "p1_bmi",
    "p1_rank",
    "p1_rank_points",
    "p1_career_win_pct",
    "p1_career_matches",
    "p1_minutes_per_match",
    "p1_ace_rate",
    "p1_recent_win_pct",
    "p1_surface_win_pct",
    "p1_h2h_win_pct",
    # Player 2
    "p2_hand",
    "p2_bmi",
    "p2_rank",
    "p2_rank_points",
    "p2_career_win_pct",
    "p2_career_matches",
    "p2_minutes_per_match",
    "p2_ace_rate",
    "p2_recent_win_pct",
    "p2_surface_win_pct",
    "p2_h2h_win_pct",
    # Derived
    "rank_diff",
    "rank_points_diff",
]

N_FEATURES = len(FEATURE_NAMES)  # 24


def _hand(h: str) -> float:
    return {"R": 1.0, "L": 0.0}.get(str(h).upper(), 0.5)


def _bmi(age: float, height_cm: float) -> float:
    h = max(float(height_cm or 185.0), 100.0)
    a = max(float(age or 25.0), 15.0)
    return a / (h / 100.0) ** 2


def build_feature_vector(
    p1: Dict,
    p2: Dict,
    surface: str,
    h2h_win_pct_p1: float = 0.5,
) -> np.ndarray:
    """
    Build a 24-element feature vector for (p1 vs p2) on surface.
    h2h_win_pct_p1 is p1's historical win % against p2 (0.5 if no history).
    """
    r1 = float(p1.get("rank") or 500)
    r2 = float(p2.get("rank") or 500)
    rp1 = float(p1.get("rank_points") or 0)
    rp2 = float(p2.get("rank_points") or 0)

    surf1 = p1.get("surface_stats", {}).get(surface, {}).get("win_pct", p1.get("career_win_pct", 0.5))
    surf2 = p2.get("surface_stats", {}).get(surface, {}).get("win_pct", p2.get("career_win_pct", 0.5))

    feats = [
        _hand(p1.get("hand", "U")),
        _bmi(p1.get("age", 25.0), p1.get("height", 185.0)),
        r1,
        rp1,
        float(p1.get("career_win_pct", 0.5)),
        float(p1.get("career_matches", 0)),
        float(p1.get("minutes_per_match", 90.0)),
        float(p1.get("ace_rate", 0.0)),
        float(p1.get("recent_win_pct", 0.5)),
        float(surf1),
        float(h2h_win_pct_p1),

        _hand(p2.get("hand", "U")),
        _bmi(p2.get("age", 25.0), p2.get("height", 185.0)),
        r2,
        rp2,
        float(p2.get("career_win_pct", 0.5)),
        float(p2.get("career_matches", 0)),
        float(p2.get("minutes_per_match", 90.0)),
        float(p2.get("ace_rate", 0.0)),
        float(p2.get("recent_win_pct", 0.5)),
        float(surf2),
        float(1.0 - h2h_win_pct_p1),

        r1 - r2,
        rp1 - rp2,
    ]
    return np.array(feats, dtype=np.float32)
