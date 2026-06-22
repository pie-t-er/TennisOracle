# TennisOracle — Claude Context Pack

## Project identity
ATP tennis match predictor. Logistic Regression / XGBoost trained on 2010–2023 ATP data
(~786 player profiles, Jeff Sackmann dataset). Predicts match-winner probabilities and
compares them against live bookmaker odds (The Odds API).
Developer: Pieter Alley.

**Deployed**: frontend on [Vercel](https://tennis-oracle.vercel.app/), backend on
[Render](https://tennisoracle.onrender.com). Live predictions accumulate automatically via a
daily GitHub Actions job (see `.github/workflows/live-predictions.yml`).

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

## Current state
- Model: XGBoost selected over LR. 2023 holdout accuracy 0.689, log-loss 0.601.
- Backtest on 13 confirmed out-of-sample 2024 matches: **84.6% accuracy** (90.9% excluding
  retirements). Flat-bet ROI +41% on matches where model edge > 5% — but this is a tiny,
  hand-picked 13-match sample, not a real track record.
- Live workflow (`collect.py` → `update_results.py`) now runs automatically once a day via
  GitHub Actions, so `live_predictions.json` is accumulating a real, growing history instead of
  one-off ad hoc runs.
- **The original goal was finding systematic value edges vs. bookmakers — that didn't pan out.**
  Bookmaker odds are already efficient; the model's calibrated probabilities track them closely
  rather than beating them. This is a true and useful finding, not a failure to hide.

---

## Portfolio vision — polish, deploy, demo

**Status: reframe, scheduled job, and deploy are done. Visualizations (#3) are the remaining item.**

### 1. Reframe the pitch — done
Lead with **"the model is accurate and well-calibrated"**, not **"it beats the bookmakers."**
The honest, interesting story: an XGBoost model independently lands on probabilities close to
what a mature betting market converges on — that's a meaningful result for a portfolio piece
(it demonstrates the model is *good*, not that pricing tennis is easy to exploit). Don't oversell
edge-finding; one paragraph acknowledging "I looked for value gaps and largely didn't find
durable ones, which itself validates the model's calibration" reads as more senior than a
forced "look, alpha!" framing.

### 2. Build real prediction history via a scheduled job — done
`.github/workflows/live-predictions.yml` runs daily (cron `0 11 * * *` + manual
`workflow_dispatch`): settles yesterday's matches via `update_results.py --days 2`, collects new
upcoming matches via `collect.py`, then commits the updated `live_predictions.json` back to the
repo. Render's build filter on `backend/**` picks up that commit and redeploys automatically, so
the live site's "running accuracy" stat stays current without a persistent volume. Budget: ~4–8
credits/day, well inside the 500/month free tier.

### 3. Add behind-the-scenes model visualizations (currently none exist outside notebooks)
Nothing in the frontend currently shows *how* the model thinks — that's the biggest gap for a
recruiter-facing demo. Worth adding to a `/model` or `/about` route:
- Feature importance (XGBoost `feature_importances_` or SHAP values)
- Calibration curve (predicted probability vs. actual outcome rate — ties directly into the
  "well-calibrated" pitch above)
- Accuracy-over-time chart, fed by the accumulated `live_predictions.json` history from #2
- Optional: per-surface accuracy breakdown (hard/clay/grass)

### 4. Deploy — done
Frontend on [Vercel](https://tennis-oracle.vercel.app/), backend on
[Render](https://tennisoracle.onrender.com) (Docker, built from `backend/Dockerfile`, build
context = repo root since `data/loader.py` needs `../ATP_Matches` at startup). CORS is env-driven
via `ALLOWED_ORIGINS` (see `backend/main.py`). Render env vars: `ODDS_API_KEY`,
`ODDS_CACHE_TTL=900`, `ALLOWED_ORIGINS=https://tennis-oracle.vercel.app`.

### Order of operations
Reframe pitch (free) → ship the scheduled job so history starts accumulating immediately →
deploy → build visualizations next, now that there's real `live_predictions.json` history to
chart instead of a static backtest.
