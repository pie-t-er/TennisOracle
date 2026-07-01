"""
Training script. Run from backend/ directory:
  python ml/train.py                  # normal train + save
  python ml/train.py --start 2020     # override training window start year
  python ml/train.py --benchmark      # print numbers only, don't save model/fi
Produces ml/model.joblib (unless --benchmark).
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.loader import load_all_matches
from ml.features import FEATURE_NAMES, N_FEATURES

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("XGBoost not found — will use LogisticRegression only.")

warnings.filterwarnings("ignore")

MODEL_PATH = Path(__file__).parent / "model.joblib"
MIN_HISTORY = 10  # minimum prior matches required for a training sample


# ---------------------------------------------------------------------------
# Build event log with cumulative pre-match stats (no data leakage)
# ---------------------------------------------------------------------------

def build_event_log(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, match), sorted chronologically."""
    shared_cols = ["tourney_date", "surface", "minutes", "match_idx"]

    ew = df[shared_cols + [
        "winner_name", "loser_name",
        "winner_hand", "winner_ht", "winner_age", "winner_rank", "winner_rank_points",
        "w_ace", "w_SvGms",
    ]].copy()
    ew["player"] = ew["winner_name"]
    ew["opponent"] = ew["loser_name"]
    ew["won"] = 1
    ew["hand"] = ew["winner_hand"]
    ew["height"] = ew["winner_ht"]
    ew["age"] = ew["winner_age"]
    ew["rank"] = ew["winner_rank"]
    ew["rank_points"] = ew["winner_rank_points"]
    ew["aces"] = ew["w_ace"]
    ew["svgms"] = ew["w_SvGms"]

    el = df[shared_cols + [
        "loser_name", "winner_name",
        "loser_hand", "loser_ht", "loser_age", "loser_rank", "loser_rank_points",
        "l_ace", "l_SvGms",
    ]].copy()
    el["player"] = el["loser_name"]
    el["opponent"] = el["winner_name"]
    el["won"] = 0
    el["hand"] = el["loser_hand"]
    el["height"] = el["loser_ht"]
    el["age"] = el["loser_age"]
    el["rank"] = el["loser_rank"]
    el["rank_points"] = el["loser_rank_points"]
    el["aces"] = el["l_ace"]
    el["svgms"] = el["l_SvGms"]

    keep = ["match_idx", "tourney_date", "player", "opponent", "surface", "won",
            "hand", "height", "age", "rank", "rank_points",
            "minutes", "aces", "svgms"]
    events = pd.concat([ew[keep], el[keep]]).sort_values("tourney_date").reset_index(drop=True)
    return events


def add_cumulative_stats(events: pd.DataFrame) -> pd.DataFrame:
    """Add pre-match cumulative stats to each event row (no leakage)."""
    # Career cumulative (shift to exclude current match)
    events["career_wins_b"] = events.groupby("player")["won"].transform(
        lambda x: x.cumsum().shift(1).fillna(0)
    )
    events["career_matches_b"] = events.groupby("player").cumcount()

    # Recent form: rolling 20, shifted
    events["recent_wins_b"] = events.groupby("player")["won"].transform(
        lambda x: x.rolling(20, min_periods=1).sum().shift(1).fillna(0)
    )
    events["recent_n_b"] = events["career_matches_b"].clip(upper=20)

    # Minutes / aces / serve games (cumulative, shifted)
    for col in ["minutes", "aces", "svgms"]:
        events[f"{col}_b"] = events.groupby("player")[col].transform(
            lambda x: x.fillna(0).cumsum().shift(1).fillna(0)
        )

    # Surface-specific cumulative (within player+surface group, date-ordered)
    events["surf_wins_b"] = events.groupby(["player", "surface"])["won"].transform(
        lambda x: x.cumsum().shift(1).fillna(0)
    )
    events["surf_matches_b"] = events.groupby(["player", "surface"]).cumcount()

    # H2H cumulative (within player+opponent group, date-ordered)
    events["h2h_wins_b"] = events.groupby(["player", "opponent"])["won"].transform(
        lambda x: x.cumsum().shift(1).fillna(0)
    )
    events["h2h_matches_b"] = events.groupby(["player", "opponent"]).cumcount()

    return events


# ---------------------------------------------------------------------------
# Feature row builder (training time — uses pre-match stats)
# ---------------------------------------------------------------------------

def _hand(h) -> float:
    return {"R": 1.0, "L": 0.0}.get(str(h).upper(), 0.5) if pd.notna(h) else 0.5


def _bmi(age, ht) -> float:
    a = float(age) if pd.notna(age) else 25.0
    h = float(ht) if pd.notna(ht) else 185.0
    h = max(h, 100.0)
    return a / (h / 100.0) ** 2


def feature_row(p: pd.Series, opp: pd.Series, surface: str):
    pm = max(int(p["career_matches_b"]), 1)
    om = max(int(opp["career_matches_b"]), 1)

    career_wp = p["career_wins_b"] / pm
    career_wopp = opp["career_wins_b"] / om

    min_pm = p["minutes_b"] / pm
    min_opm = opp["minutes_b"] / om

    ace_p = p["aces_b"] / max(p["svgms_b"], 1)
    ace_opp = opp["aces_b"] / max(opp["svgms_b"], 1)

    recent_wp = p["recent_wins_b"] / max(p["recent_n_b"], 1)
    recent_wopp = opp["recent_wins_b"] / max(opp["recent_n_b"], 1)

    surf_wp = (p["surf_wins_b"] / max(p["surf_matches_b"], 1)
               if p["surf_matches_b"] > 0 else career_wp)
    surf_wopp = (opp["surf_wins_b"] / max(opp["surf_matches_b"], 1)
                 if opp["surf_matches_b"] > 0 else career_wopp)

    h2h_wp = (p["h2h_wins_b"] / max(p["h2h_matches_b"], 1)
              if p["h2h_matches_b"] > 0 else 0.5)
    h2h_wopp = (opp["h2h_wins_b"] / max(opp["h2h_matches_b"], 1)
                if opp["h2h_matches_b"] > 0 else 0.5)

    r1 = float(p["rank"]) if pd.notna(p["rank"]) else 500.0
    r2 = float(opp["rank"]) if pd.notna(opp["rank"]) else 500.0
    rp1 = float(p["rank_points"]) if pd.notna(p["rank_points"]) else 0.0
    rp2 = float(opp["rank_points"]) if pd.notna(opp["rank_points"]) else 0.0

    return [
        _hand(p["hand"]),
        _bmi(p["age"], p["height"]),
        r1, rp1,
        career_wp, pm, min_pm, ace_p,
        recent_wp, surf_wp, h2h_wp,

        _hand(opp["hand"]),
        _bmi(opp["age"], opp["height"]),
        r2, rp2,
        career_wopp, om, min_opm, ace_opp,
        recent_wopp, surf_wopp, h2h_wopp,

        r1 - r2,
        rp1 - rp2,
    ]


# ---------------------------------------------------------------------------
# Main training routine
# ---------------------------------------------------------------------------

def build_training_data(df: pd.DataFrame):
    df = df.copy()
    df["match_idx"] = range(len(df))

    events = build_event_log(df)
    events = add_cumulative_stats(events)

    winner_ev = events[events["won"] == 1].set_index("match_idx")
    loser_ev = events[events["won"] == 0].set_index("match_idx")

    X_rows, y_rows, dates = [], [], []

    for idx, row in df.iterrows():
        mid = row["match_idx"]
        if mid not in winner_ev.index or mid not in loser_ev.index:
            continue
        ws = winner_ev.loc[mid]
        ls = loser_ev.loc[mid]

        if ws["career_matches_b"] < MIN_HISTORY or ls["career_matches_b"] < MIN_HISTORY:
            continue

        surface = ws["surface"]
        X_rows.append(feature_row(ws, ls, surface))
        y_rows.append(1)
        dates.append(row["tourney_date"])

        X_rows.append(feature_row(ls, ws, surface))
        y_rows.append(0)
        dates.append(row["tourney_date"])

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.int32)
    dates = pd.Series(dates)
    return X, y, dates


def train(start_year: int = 2016, save: bool = True):
    print("Loading ATP match data...")
    df = load_all_matches()
    print(f"  {len(df):,} matches loaded ({df['tourney_date'].dt.year.min()}–{df['tourney_date'].dt.year.max()})")

    print("Building training features (this may take ~30s)...")
    X, y, dates = build_training_data(df)
    print(f"  {len(X):,} training samples built ({N_FEATURES} features each)")

    # Time-based split: train on start_year–2024, test on 2025.
    # 2026 is deliberately excluded — partial season, look-ahead leakage risk.
    TRAIN_START_YEAR = start_year
    train_mask = (dates.dt.year >= TRAIN_START_YEAR) & (dates.dt.year <= 2024)
    test_mask = dates.dt.year == 2025
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    print(f"  Train ({TRAIN_START_YEAR}–2024): {len(X_train):,} | Test (2025): {len(X_test):,}")

    cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)

    # --- Logistic Regression ---
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, max_iter=500, random_state=42)),
    ])
    lr_cv = cross_val_score(lr_pipe, X_train, y_train, cv=cv, scoring="accuracy")
    print(f"\nLogisticRegression  CV acc: {lr_cv.mean():.4f} ± {lr_cv.std():.4f}")

    best_model = lr_pipe
    best_cv = lr_cv.mean()

    # --- XGBoost (if available) ---
    if HAS_XGB:
        xgb_pipe = Pipeline([
            ("clf", XGBClassifier(
                n_estimators=300,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )),
        ])
        xgb_cv = cross_val_score(xgb_pipe, X_train, y_train, cv=cv, scoring="accuracy")
        print(f"XGBoost             CV acc: {xgb_cv.mean():.4f} ± {xgb_cv.std():.4f}")
        if xgb_cv.mean() > best_cv:
            best_model = xgb_pipe
            best_cv = xgb_cv.mean()
            print("  → XGBoost selected as best model")
        else:
            print("  → LogisticRegression selected as best model")

    # --- Calibrate and fit on full train set ---
    print("\nCalibrating and fitting on full training set...")
    calibrated = CalibratedClassifierCV(best_model, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    # --- Evaluate on 2025 holdout ---
    if len(X_test) > 0:
        test_acc = accuracy_score(y_test, calibrated.predict(X_test))
        test_ll = log_loss(y_test, calibrated.predict_proba(X_test))
        print(f"2025 holdout — accuracy: {test_acc:.4f} | log-loss: {test_ll:.4f}")

    # Sanity check: probabilities sum to 1
    sample_prob = calibrated.predict_proba(X_test[:5])
    assert np.allclose(sample_prob.sum(axis=1), 1.0), "predict_proba rows don't sum to 1"
    print("predict_proba sanity check passed ✓")

    if not save:
        return

    joblib.dump(calibrated, MODEL_PATH)
    print(f"\nModel saved → {MODEL_PATH}")

    # Save feature importance for the /model analytics page.
    fi_path = Path(__file__).parent / "feature_importance.json"
    try:
        importances = np.zeros(N_FEATURES)
        for cal_clf in calibrated.calibrated_classifiers_:
            clf = getattr(cal_clf.estimator, "named_steps", {}).get("clf", cal_clf.estimator)
            if hasattr(clf, "feature_importances_"):
                importances += clf.feature_importances_
            elif hasattr(clf, "coef_"):
                importances += np.abs(clf.coef_[0])
        importances /= len(calibrated.calibrated_classifiers_)
        total = importances.sum()
        if total > 0:
            importances /= total

        fi_data = [
            {"feature": name, "importance": round(float(imp), 6)}
            for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
        ]
        with open(fi_path, "w") as f:
            json.dump(fi_data, f, indent=2)
        print(f"Feature importance saved → {fi_path}")
    except Exception as exc:
        print(f"  Warning: could not save feature importance: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2010, help="First training year (default 2010)")
    parser.add_argument("--benchmark", action="store_true", help="Print numbers only, skip saving model")
    args = parser.parse_args()
    train(start_year=args.start, save=not args.benchmark)
