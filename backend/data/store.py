"""
Append-only predictions store backed by live_predictions.json.

Each entry is keyed by the Odds API match ID and contains:
  - match metadata (players, surface, tournament, commence_time)
  - odds at the time the prediction was collected
  - our model's prediction (probabilities, predicted winner, confidence)
  - result (filled in by update_results.py once the match completes)

Thread-safe via a module-level lock so the FastAPI server and CLI scripts
can share the file safely.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

STORE_PATH = Path(__file__).parent / "live_predictions.json"
_lock      = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not STORE_PATH.exists():
        return {"predictions": {}}
    with open(STORE_PATH) as f:
        return json.load(f)


def _write(data: dict) -> None:
    data["last_updated"] = _now()
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Public interface ──────────────────────────────────────────────────────────

def load_all() -> Dict[str, dict]:
    """Return all stored predictions as {match_id: entry}."""
    with _lock:
        return _load().get("predictions", {})


def upsert(match_id: str, entry: dict) -> bool:
    """
    Save a new prediction.
    Returns True if newly inserted, False if match_id already existed.
    Existing predictions are never modified here — results come via update_result().
    """
    with _lock:
        data = _load()
        if match_id in data["predictions"]:
            return False
        data["predictions"][match_id] = entry
        _write(data)
        return True


def update_result(match_id: str, winner_name: str, correct: bool) -> bool:
    """
    Record the actual result for a settled match.
    Returns True if the prediction was found, False if unknown match_id.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    with _lock:
        data = _load()
        if match_id not in data["predictions"]:
            return False
        pred = data["predictions"][match_id]
        if pred.get("result"):
            return True  # already settled, don't overwrite
        data["predictions"][match_id]["result"] = {
            "winner":     winner_name,
            "correct":    correct,
            "settled_at": _now(),
        }
        _write(data)
        return True


def summary() -> dict:
    """Quick stats for logging/display."""
    preds   = load_all().values()
    total   = len(preds)
    settled = [p for p in preds if p.get("result")]
    correct = sum(1 for p in settled if p["result"]["correct"])
    return {
        "total":    total,
        "settled":  len(settled),
        "pending":  total - len(settled),
        "correct":  correct,
        "accuracy": round(correct / len(settled), 4) if settled else None,
    }
