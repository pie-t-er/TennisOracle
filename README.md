# TennisOracle

ATP tennis match predictor. Logistic regression / XGBoost model trained on 2010–2023 ATP data, calibrated to produce well-grounded win probabilities. Player profiles (rank, recent form, head-to-head) are rebuilt at startup from match data that now extends through the current season, so live predictions use each player's actual current state rather than a frozen 2023 snapshot. Predictions are tracked against live bookmaker odds to check how the model's probabilities hold up against a real market.

**Live demo:** [tennis-oracle.vercel.app](https://tennis-oracle.vercel.app/) — backend hosted on [Render](https://tennisoracle.onrender.com).

---

## Project structure

```
TennisOracle/
├── ATP_Matches/          Raw ATP CSV data: 2010–2023 (Jeff Sackmann), 2024–2026 (TML-Database)
├── backend/              FastAPI server + ML model
│   ├── data/
│   │   ├── loader.py         Builds player profiles from CSVs at startup
│   │   ├── store.py          Append-only predictions store (live_predictions.json)
│   │   └── live_predictions.json   Accumulated live predictions + results
│   ├── ml/
│   │   ├── train.py          Model training script
│   │   ├── features.py       Feature engineering (shared by train + inference)
│   │   └── model.joblib      Trained model (re-generate with ml/train.py)
│   ├── routers/
│   │   ├── players.py        GET /api/players
│   │   ├── predict.py        POST /api/predict
│   │   └── odds.py           GET /api/odds/*
│   ├── scripts/
│   │   ├── collect.py        Fetch upcoming matches → run model → save predictions
│   │   ├── update_results.py Fetch completed scores → settle predictions
│   │   └── backtest.py       Retroactive accuracy report on historical fixtures
│   ├── fixtures/
│   │   └── sample_matches.json   13 confirmed 2024 matches for backtesting
│   ├── odds_client.py        The Odds API wrapper (caching, surface inference)
│   ├── main.py               FastAPI app entry point
│   ├── requirements.txt
│   ├── .env                  API keys (gitignored — see .env.example)
├── frontend/             Next.js 15 web app
│   ├── app/              Routes (/, /players, /players/[slug])
│   ├── components/       UI components
│   └── lib/api.ts        Typed API client
└── notebooks/            Model exploration (model_v1.ipynb, model_v2.ipynb)
```

---

## Prerequisites

| Tool | Tested version |
|---|---|
| Python (Anaconda) | 3.11 |
| Node.js | 20 |
| npm | 10+ |

---

## First-time setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Copy the env template and add your Odds API key
cp .env.example .env
# Edit .env and set ODDS_API_KEY=<your key from the-odds-api.com>
```

### Frontend

```bash
cd frontend
npm install
```

---

## Running the app

Both servers must be running at the same time. Open two terminal tabs.

### Terminal 1 — Backend (port 8000)

```bash
cd backend
uvicorn main:app --reload
```

The server loads all ATP match data and builds player profiles at startup (~5 seconds). You'll see:

```
Loading ATP match data...
  921 player profiles built
  Model loaded ✓
```

### Terminal 2 — Frontend (port 3000)

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**

---

## ML model

The model is pre-trained and committed as `backend/ml/model.joblib`, trained on 2010–2023 data.
It has **not** been retrained on the 2024–2026 data in `ATP_Matches/` — that data only feeds live
player profiles (rank, recent form, h2h) at inference time, which is the intended use of those
features. Re-train if you want the model itself to learn from the newer matches too, or if you add
more data and want to experiment.

To refresh match data beyond what's committed, download newer `{year}.csv` files from
[stats.tennismylife.org/data/](https://stats.tennismylife.org/data/) (free, MIT-licensed, no API
key, same schema as the original Jeff Sackmann dataset) and save them as
`ATP_Matches/atp_matches_{year}.csv` — `backend/data/loader.py` picks up anything matching that
glob automatically on next startup.

```bash
cd backend
python ml/train.py
```

Training takes ~30 seconds. It evaluates both Logistic Regression and XGBoost with 10-fold cross-validation and picks the better one, then calibrates probabilities using isotonic regression. The 2023 season is held out as a test set.

```
LogisticRegression  CV acc: 0.6821 ± 0.0041
XGBoost             CV acc: 0.6934 ± 0.0038
  → XGBoost selected as best model
2023 holdout — accuracy: 0.6891 | log-loss: 0.6012
```

---

## Live predictions workflow

The Odds API free tier gives **500 credits/month**. Cost is **1 credit per active ATP tournament,
per call** — `update_results.py`'s scores call always costs (no caching), `collect.py`'s odds call
only costs when its 15-min cache has expired. Running the full workflow 3x/day costs ~18
credits/day worst case (3 concurrent tournaments) — comfortably under budget most of the season,
tight only in the heaviest overlapping weeks.

This now runs automatically 3x/day (every 8 hours) via
[`.github/workflows/live-predictions.yml`](.github/workflows/live-predictions.yml), which settles
recent matches, collects new upcoming ones, backfills predictions for matches outside Odds API
coverage (see below), and commits the updated `data/live_predictions.json` back to the repo. It
needs an `ODDS_API_KEY` repo secret — add one under repo **Settings → Secrets and variables →
Actions → New repository secret** using the same value as `backend/.env`. You can also trigger it
manually from the Actions tab ("Run workflow").

The steps below are for running it manually/locally.

### Predictions beyond Odds API coverage

The Odds API only covers Grand Slams, Masters 1000s, and the bigger 500s — roughly 20 of the
60+ ATP events per year. Lower-tier ATP 250s never appear there, so `collect.py` alone never
predicts them. `scripts/backfill_predictions.py` closes that gap independently: it scans
[stats.tennismylife.org](https://stats.tennismylife.org)'s results (same source used to extend
`ATP_Matches/`, covers every tournament level) for matches not already in the store, predicts
each one, and records it **already settled** — the actual winner is known the moment a match
shows up there, so there's no pending phase for these. They're stored with no odds
(`bookmakers: {}`), which the frontend already renders as "No edge" / "no odds" gracefully. Needs
no API key and costs no Odds API credits.

```bash
cd backend
python scripts/backfill_predictions.py        # last 14 days, default
python scripts/backfill_predictions.py --days 30
```

### Step 1 — Collect predictions (run before matches)

```bash
cd backend
python scripts/collect.py
```

Fetches upcoming ATP matches, runs the model against each, and saves new predictions to `data/live_predictions.json`. Already-stored predictions are never overwritten.

```bash
# Force a fresh fetch, bypassing the 15-minute cache (costs 1 extra credit)
python scripts/collect.py --force
```

### Step 2 — Settle results (run after matches complete)

```bash
cd backend
python scripts/update_results.py
```

Pulls completed scores from the Odds API, matches them to stored predictions, and records whether the model was correct.

```bash
# Look back further if you missed a day
python scripts/update_results.py --days 5
```

### Check running accuracy anytime (no API call)

```bash
cd backend
python -c "from data.store import summary; import json; print(json.dumps(summary(), indent=2))"
```

Output:
```json
{
  "total": 14,
  "settled": 11,
  "pending": 3,
  "correct": 9,
  "accuracy": 0.8182
}
```

---

## Retroactive backtest

Tests the model against 13 confirmed 2024 ATP matches (fully out-of-sample) with approximate historical Pinnacle odds. No API credits used.

```bash
cd backend
python scripts/backtest.py
```

```bash
# Adjust the edge threshold for the flat-bet simulation (default: 5%)
python scripts/backtest.py --edge 0.08

# Plain text output (no ANSI colours)
python scripts/backtest.py --no-color
```

Last run results (2024, out-of-sample):
- **Accuracy: 84.6%** (11/13) — 90.9% excluding retirements
- **Flat-bet ROI: +41%** on matches where model edge > 5%

This is a tiny, hand-picked 13-match sample, not a track record. The bigger finding from running
this against live odds: bookmaker pricing is already efficient, so durable value gaps are rare —
the model's calibrated probabilities mostly track the market rather than beating it. That's a
useful result in itself, since it means the model is producing realistic probabilities rather than
overconfident ones.

---

## API endpoints

The backend exposes these routes (all prefixed with `/api`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/players` | Player list. Params: `search`, `limit` |
| `GET` | `/api/players/{name}` | Single player profile + recent form |
| `POST` | `/api/predict` | Match prediction. Body: `{player1, player2, surface}` |
| `GET` | `/api/odds/upcoming` | Live odds + model predictions for upcoming matches. Param: `force=true` to bypass cache |
| `GET` | `/api/odds/predictions` | All stored predictions. Param: `settled_only=true` |
| `GET` | `/api/odds/summary` | Running accuracy stats |

Interactive docs: **http://localhost:8000/docs** (local) or
**https://tennisoracle.onrender.com/docs** (deployed)

---

## Environment variables

All variables go in `backend/.env`. See `backend/.env.example` for the template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ODDS_API_KEY` | Yes | — | API key from [the-odds-api.com](https://the-odds-api.com) (free: 500 credits/month) |
| `ODDS_CACHE_TTL` | No | `900` | Seconds to cache odds responses. Raise to conserve credits. |

---

## Deployment

Frontend → **Vercel**, backend → **Render** (Docker).

**Backend (Render):**
1. New Web Service → connect this GitHub repo.
2. Root Directory: repo root. Dockerfile path: `backend/Dockerfile` (the build context is the
   repo root since `data/loader.py` reads `../ATP_Matches` at startup).
3. Env vars: `ODDS_API_KEY`, `ODDS_CACHE_TTL=900`, `ALLOWED_ORIGINS=https://<your-vercel-domain>`.
4. Enable Auto-Deploy with a build filter on `backend/**` — this also picks up the daily commits
   from `live-predictions.yml`, so the deployed instance's prediction history stays current without
   needing a persistent volume.
5. Health check: `GET /api/health` → `{"status": "ok"}`.

**Frontend (Vercel):**
1. New Project → import this GitHub repo.
2. Root Directory: `frontend`.
3. Env var: `NEXT_PUBLIC_API_URL=https://<your-render-backend-url>`.

No frontend code changes are needed — `frontend/lib/api.ts` and `next.config.ts` already read the
backend URL from `NEXT_PUBLIC_API_URL`. Vercel's per-root ignored-build-step means pushes that only
touch `backend/**` won't trigger pointless frontend rebuilds.

---

## Adding more backtest fixtures

Edit `backend/fixtures/sample_matches.json`. Each entry follows this shape:

```json
{
  "id": "unique_id",
  "tournament": "Wimbledon",
  "date": "2024-07-14",
  "surface": "Grass",
  "round": "F",
  "player1": "Carlos Alcaraz",
  "player2": "Novak Djokovic",
  "winner": "player1",
  "score": "6-2, 6-2, 7-6(4)",
  "notes": "",
  "odds": {
    "pinnacle_est": { "player1": 1.72, "player2": 2.10 }
  }
}
```

Player names must match the ATP dataset format (full name, e.g. `"Carlos Alcaraz"`).
