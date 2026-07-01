"""
Optuna hyperparameter search for the XGBoost match predictor.
Run from backend/ directory:

  python ml/tune.py                        # 50 trials, optimise CV accuracy
  python ml/tune.py --objective logloss    # optimise CV log-loss instead
  python ml/tune.py --trials 20            # faster smoke-test
  python ml/tune.py --start 2010           # override training window start year
  python ml/tune.py --save                 # save if it beats current model

Objective choices:
  accuracy  — maximise 5-fold CV accuracy (default)
  logloss   — minimise 5-fold CV log-loss (better for calibration quality)
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import StratifiedKFold, cross_val_score

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.train import build_training_data
from ml.features import FEATURE_NAMES, N_FEATURES
from data.loader import load_all_matches

try:
    from xgboost import XGBClassifier
except ImportError:
    print("XGBoost is required for tuning.")
    sys.exit(1)

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("Install optuna: pip install optuna")
    sys.exit(1)

warnings.filterwarnings("ignore")

MODEL_PATH  = Path(__file__).parent / "model.joblib"
FI_PATH     = Path(__file__).parent / "feature_importance.json"


def objective(trial, X_train, y_train, metric: str):
    params = {
        "n_estimators":     trial.suggest_int("n_estimators",    100, 600),
        "max_depth":        trial.suggest_int("max_depth",         3,   8),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":        trial.suggest_float("subsample",      0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight",   1,  10),
        "gamma":            trial.suggest_float("gamma",           0.0, 1.0),
        "eval_metric":      "logloss",
        "random_state":     42,
    }
    clf    = XGBClassifier(**params)
    cv     = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    # neg_log_loss so higher = better (Optuna always maximises)
    scoring = "accuracy" if metric == "accuracy" else "neg_log_loss"
    scores  = cross_val_score(clf, X_train, y_train, cv=cv, scoring=scoring, n_jobs=-1)
    return scores.mean()


def save_model(calibrated, label: str):
    joblib.dump(calibrated, MODEL_PATH)
    print(f"Model saved → {MODEL_PATH}")

    try:
        importances = np.zeros(N_FEATURES)
        for cal_clf in calibrated.calibrated_classifiers_:
            clf = getattr(cal_clf.estimator, "named_steps", {}).get("clf", cal_clf.estimator)
            if hasattr(clf, "feature_importances_"):
                importances += clf.feature_importances_
        importances /= len(calibrated.calibrated_classifiers_)
        total = importances.sum()
        if total > 0:
            importances /= total
        fi_data = [
            {"feature": name, "importance": round(float(imp), 6)}
            for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
        ]
        with open(FI_PATH, "w") as f:
            json.dump(fi_data, f, indent=2)
        print(f"Feature importance saved → {FI_PATH}")
    except Exception as exc:
        print(f"  Warning: could not save feature importance: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials",    type=int,  default=50,       help="Number of Optuna trials")
    parser.add_argument("--start",     type=int,  default=2010,     help="Training window start year")
    parser.add_argument("--objective", choices=["accuracy","logloss"], default="accuracy",
                        help="CV metric to optimise (default: accuracy)")
    parser.add_argument("--save",      action="store_true",          help="Save model if it beats current holdout")
    args = parser.parse_args()

    print("Loading ATP match data...")
    df = load_all_matches()

    print("Building training features...")
    X, y, dates = build_training_data(df)

    train_mask = (dates.dt.year >= args.start) & (dates.dt.year <= 2024)
    test_mask  =  dates.dt.year == 2025
    X_train, y_train = X[train_mask], y[train_mask]
    X_test,  y_test  = X[test_mask],  y[test_mask]
    print(f"  Train ({args.start}–2024): {len(X_train):,} | Test (2025): {len(X_test):,}")

    metric = args.objective
    print(f"\nRunning {args.trials} Optuna trials (5-fold CV, optimising {metric})…")
    study = optuna.create_study(direction="maximize")
    study.optimize(
        lambda trial: objective(trial, X_train, y_train, metric),
        n_trials=args.trials,
        show_progress_bar=True,
    )

    best    = study.best_params
    best_cv = study.best_value
    # neg_log_loss is negative; convert for display
    cv_display = best_cv if metric == "accuracy" else -best_cv
    cv_label   = "Best CV accuracy" if metric == "accuracy" else "Best CV log-loss"
    print(f"\n{'─'*50}")
    print(f"{cv_label} : {cv_display:.4f}")
    print(f"Best params      :")
    for k, v in best.items():
        print(f"  {k:<22} {v}")

    print("\nFitting calibrated model on full training set with best params…")
    best_clf = XGBClassifier(**best, eval_metric="logloss", random_state=42)
    calibrated = CalibratedClassifierCV(best_clf, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    holdout_acc = accuracy_score(y_test, calibrated.predict(X_test))
    holdout_ll  = log_loss(y_test, calibrated.predict_proba(X_test))
    print(f"2025 holdout — accuracy: {holdout_acc:.4f} | log-loss: {holdout_ll:.4f}")

    if args.save:
        existing_acc = existing_ll = None
        if MODEL_PATH.exists():
            try:
                existing     = joblib.load(MODEL_PATH)
                existing_acc = accuracy_score(y_test, existing.predict(X_test))
                existing_ll  = log_loss(y_test, existing.predict_proba(X_test))
                print(f"Current model — accuracy: {existing_acc:.4f}  log-loss: {existing_ll:.4f}")
            except Exception:
                pass

        if metric == "accuracy":
            better = existing_acc is None or holdout_acc > existing_acc
            reason = f"accuracy {holdout_acc:.4f} vs {existing_acc:.4f}"
        else:
            better = existing_ll is None or holdout_ll < existing_ll
            reason = f"log-loss {holdout_ll:.4f} vs {existing_ll:.4f}"

        if better:
            print(f"Tuned model is better ({reason}) — saving.")
            save_model(calibrated, label=f"tuned {args.start}–2024")
        else:
            print(f"Tuned model doesn't improve on current ({reason}) — not saved.")


if __name__ == "__main__":
    main()
