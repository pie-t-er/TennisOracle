# TennisOracle — Claude Context Pack

## Project identity
ATP tennis match predictor. Logistic Regression / XGBoost trained on 2010–2023 ATP data
(~786 player profiles, Jeff Sackmann dataset). Predicts match-winner probabilities and
compares them against live bookmaker odds (The Odds API).
Developer: Pieter Alley.

Currently **local-only** — no deployed instance yet.

---

## Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (`backend/main.py`), port 8000 |
| ML | scikit-learn LogisticRegression + XGBoost, isotonic calibration, joblib |
| Frontend | Next.js 15 (`frontend/`), port 3000 |
| Odds data | The Odds API (free tier, 500 credits/month) |
| Data | Static ATP CSVs 2010–2023 (`ATP_Matches/`) |

---

## Directory map
```
backend/
  data/loader.py       Builds player profiles from CSVs at startup
  data/store.py         Append-only predictions store (live_predictions.json)
  ml/train.py           Trains LR + XGBoost, 10-fold CV, picks best, isotonic calibration
  ml/features.py         Feature engineering (shared train + inference)
  ml/model.joblib        Pre-trained model, committed to repo
  routers/players.py     GET /api/players
  routers/predict.py     POST /api/predict
  routers/odds.py         GET /api/odds/*
  scripts/collect.py      Fetch upcoming matches → predict → save (idempotent, never overwrites)
  scripts/update_results.py  Fetch completed scores → settle predictions
  scripts/backtest.py      Retroactive accuracy report against fixtures/sample_matches.json
  odds_client.py          The Odds API wrapper, caching, surface inference
frontend/app/             Routes: /, /players, /players/[slug]
notebooks/                model_v1.ipynb, model_v2.ipynb — exploration only, not in app
```

---

## Current state (what actually works)
- Model: XGBoost selected over LR. 2023 holdout accuracy 0.689, log-loss 0.601.
- Backtest on 13 confirmed out-of-sample 2024 matches: **84.6% accuracy** (90.9% excluding
  retirements). Flat-bet ROI +41% on matches where model edge > 5% — but this is a tiny,
  hand-picked 13-match sample, not a real track record.
- Live workflow (`collect.py` → `update_results.py`) exists and works, but has only been run
  ad hoc — `live_predictions.json` does not yet hold a meaningful history.
- **The original goal was finding systematic value edges vs. bookmakers — that didn't pan out.**
  Bookmaker odds are already efficient; the model's calibrated probabilities track them closely
  rather than beating them. This is a true and useful finding, not a failure to hide.

---

## Portfolio vision — polish, deploy, demo

### 1. Reframe the pitch (do this first, it's free)
Lead with **"the model is accurate and well-calibrated"**, not **"it beats the bookmakers."**
The honest, interesting story: an XGBoost model independently lands on probabilities close to
what a mature betting market converges on — that's a meaningful result for a portfolio piece
(it demonstrates the model is *good*, not that pricing tennis is easy to exploit). Don't oversell
edge-finding; one paragraph acknowledging "I looked for value gaps and largely didn't find
durable ones, which itself validates the model's calibration" reads as more senior than a
forced "look, alpha!" framing.

### 2. Build real prediction history via a scheduled job
`collect.py` / `update_results.py` already do the work — they just aren't running on a schedule.
Add a cron (or Cloud Scheduler / GitHub Actions scheduled workflow once deployed) that:
- Runs `collect.py` once daily during ATP season (within free-tier budget: ~4 credits/day
  leaves ~380/month headroom — don't run more than a few times/day).
- Runs `update_results.py` daily to settle completed matches.
- Accumulates `live_predictions.json` into a real, growing accuracy record rather than the
  one-off 13-match backtest — this is what makes the deployed site's "running accuracy" stat
  credible over time instead of static.

### 3. Add behind-the-scenes model visualizations (currently none exist outside notebooks)
Nothing in the frontend currently shows *how* the model thinks — that's the biggest gap for a
recruiter-facing demo. Worth adding to a `/model` or `/about` route:
- Feature importance (XGBoost `feature_importances_` or SHAP values)
- Calibration curve (predicted probability vs. actual outcome rate — ties directly into the
  "well-calibrated" pitch above)
- Accuracy-over-time chart, fed by the accumulated `live_predictions.json` history from #2
- Optional: per-surface accuracy breakdown (hard/clay/grass)

### 4. Deploy
No deployment target chosen yet. Natural split: Next.js frontend → Vercel; FastAPI backend →
Render/Railway/Fly.io/Cloud Run (model.joblib is small enough to ship in the container image).
Needs `ODDS_API_KEY` set as a deployed secret; consider lowering `ODDS_CACHE_TTL` headroom
once the scheduled job is also consuming credits.

### Order of operations
Reframe pitch (free) → ship the scheduled job so history starts accumulating immediately →
build visualizations in parallel → deploy once there's at least a few days of real history to show.
