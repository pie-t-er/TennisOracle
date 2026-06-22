"""TennisOracle FastAPI backend. Run with: uvicorn main:app --reload"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from data.loader import PlayerDB, load_all_matches
from routers import predict as predict_router
from routers import players as players_router
from routers import odds as odds_router

MODEL_PATH = Path(__file__).parent / "ml" / "model.joblib"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading ATP match data...")
    df = load_all_matches()
    db = PlayerDB(df)
    print(f"  {len(db.profiles):,} player profiles built")

    model = None
    if MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
        print("  Model loaded ✓")
    else:
        print("  WARNING: model.joblib not found — run ml/train.py first")

    predict_router.init(db, model)
    players_router.init(db)
    odds_router.init(db, model)

    yield


app = FastAPI(title="TennisOracle API", lifespan=lifespan)

_default_origins = "http://localhost:3000,http://localhost:3001"
allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict_router.router)
app.include_router(players_router.router)
app.include_router(odds_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
