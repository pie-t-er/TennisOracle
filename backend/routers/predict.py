from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data.loader import PlayerDB
from ml.features import build_feature_vector

router = APIRouter(prefix="/api")

# Injected at startup by main.py
_db: PlayerDB = None
_model = None


def init(db: PlayerDB, model):
    global _db, _model
    _db = db
    _model = model


class PredictRequest(BaseModel):
    player1: str
    player2: str
    surface: str = "Hard"


@router.post("/predict")
def predict(req: PredictRequest):
    if _model is None:
        raise HTTPException(503, "Model not loaded")

    p1 = _db.get_player(req.player1)
    p2 = _db.get_player(req.player2)
    if p1 is None:
        raise HTTPException(404, f"Player not found: {req.player1}")
    if p2 is None:
        raise HTTPException(404, f"Player not found: {req.player2}")

    h2h_p1 = _db.h2h_win_pct(req.player1, req.player2)
    fv = build_feature_vector(p1, p2, req.surface, h2h_p1).reshape(1, -1)

    probs = _model.predict_proba(fv)[0]
    p1_prob = float(probs[1])
    p2_prob = float(probs[0])

    margin = abs(p1_prob - p2_prob)
    if margin >= 0.20:
        confidence = "high"
    elif margin >= 0.08:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "player1": p1["name"],
        "player2": p2["name"],
        "surface": req.surface,
        "p1_prob": round(p1_prob, 4),
        "p2_prob": round(p2_prob, 4),
        "predicted_winner": p1["name"] if p1_prob >= p2_prob else p2["name"],
        "confidence": confidence,
        "h2h": _db.get_h2h_record(req.player1, req.player2),
    }
