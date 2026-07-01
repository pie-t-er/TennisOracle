"""GET /api/model/info — feature importance and model metadata."""
import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/model")

_FI_PATH = Path(__file__).parent.parent / "ml" / "feature_importance.json"


@router.get("/info")
def model_info():
    """
    Feature importance values saved by ml/train.py at retrain time.
    Returns an empty list if the file hasn't been generated yet.
    """
    if not _FI_PATH.exists():
        return {"feature_importance": []}
    with open(_FI_PATH) as f:
        return {"feature_importance": json.load(f)}
