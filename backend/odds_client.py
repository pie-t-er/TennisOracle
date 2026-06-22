"""
Thin wrapper around the-odds-api.com v4 API.

The Odds API uses per-tournament sport keys (e.g. tennis_atp_french_open,
tennis_atp_wimbledon). This module auto-discovers active ATP keys via the
free /v4/sports endpoint, then fetches odds for each active tournament.

Credit cost:
  /v4/sports        — FREE (never counts against the 500/month quota)
  /v4/sports/*/odds — 1 credit per tournament, per call

With the file cache (default TTL 15 min), running collect.py once a day
costs ~1–3 credits/day depending on how many tournaments are running.
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

API_BASE   = "https://api.the-odds-api.com/v4"
CACHE_FILE = Path(__file__).parent / "data" / ".odds_cache.json"

# Surface lookup — checked against both sport key and event title (lowercase).
# Entries are ordered longest-first to avoid "paris" matching "paris masters".
_SURFACE: Dict[str, str] = {
    # ── Clay ─────────────────────────────────────────────────────────────────
    "roland_garros":   "Clay",  "roland garros":   "Clay",
    "french_open":     "Clay",  "french open":     "Clay",
    "monte_carlo":     "Clay",  "monte carlo":     "Clay",
    "buenos_aires":    "Clay",  "buenos aires":    "Clay",
    "rio_de_janeiro":  "Clay",  "rio de janeiro":  "Clay",
    "paris_masters":   "Clay",  # ← don't confuse with Paris indoor hard
    "barcelona":       "Clay",
    "madrid":          "Clay",
    "hamburg":         "Clay",
    "geneva":          "Clay",
    "rome":            "Clay",
    "lyon":            "Clay",
    "munich":          "Clay",
    "estoril":         "Clay",
    "bucharest":       "Clay",
    "marrakesh":       "Clay",
    "cordoba":         "Clay",
    "houston":         "Clay",
    "istanbul":        "Clay",
    # ── Grass ────────────────────────────────────────────────────────────────
    "wimbledon":          "Grass",
    "queens_club":        "Grass",  "queen's club":     "Grass",
    "queens club":        "Grass",
    "s-hertogenbosch":    "Grass",
    "eastbourne":         "Grass",
    "nottingham":         "Grass",
    "halle":              "Grass",
    "newport":            "Grass",
    # ── Hard (explicit) ──────────────────────────────────────────────────────
    "australian_open":    "Hard",  "australian open":   "Hard",
    "us_open":            "Hard",  "us open":           "Hard",
    "indian_wells":       "Hard",  "indian wells":      "Hard",
    "miami":              "Hard",
    "cincinnati":         "Hard",
    "canada":             "Hard",
    "toronto":            "Hard",
    "montreal":           "Hard",
    "shanghai":           "Hard",
    "vienna":             "Hard",
    "basel":              "Hard",
    "tokyo":              "Hard",
    "atp_finals":         "Hard",  "atp finals":        "Hard",
    "nitto_atp":          "Hard",  "nitto atp":         "Hard",
}


def infer_surface(sport_key: str = "", title: str = "") -> str:
    """
    Return 'Clay', 'Grass', or 'Hard'.
    Checks the sport key first (most reliable), then the title text.
    """
    for text in (sport_key.lower(), title.lower()):
        for keyword, surface in _SURFACE.items():
            if keyword in text:
                return surface
    return "Hard"


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> Optional[dict]:
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(events: list) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"ts": time.time(), "events": events}, f)


# ── Sports discovery (free endpoint) ─────────────────────────────────────────

def active_atp_sport_keys(api_key: str) -> List[dict]:
    """
    Return all currently active ATP tennis sport definitions.
    Calls /v4/sports — this endpoint is FREE and never costs credits.
    """
    resp = httpx.get(
        f"{API_BASE}/sports",
        params={"apiKey": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    return [
        s for s in resp.json()
        if s.get("active") and s.get("key", "").startswith("tennis_atp")
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_upcoming(
    api_key: str,
    ttl: int = 900,
    force: bool = False,
) -> List[dict]:
    """
    Return upcoming ATP events with H2H odds, enriched with sport_key and
    sport_title so surface inference works correctly.

    Served from cache if < *ttl* seconds old (default 15 min).
    Pass force=True to bypass the cache — costs 1 credit per active tournament.
    """
    if not force:
        cached = _load_cache()
        if cached and (time.time() - cached["ts"]) < ttl:
            return cached["events"]

    sports = active_atp_sport_keys(api_key)
    if not sports:
        print("  [Odds API] No active ATP tournaments found right now.")
        return []

    all_events: List[dict] = []
    for sport in sports:
        sport_key   = sport["key"]
        sport_title = sport["title"]
        url = f"{API_BASE}/sports/{sport_key}/odds"
        params = {
            "apiKey":     api_key,
            "regions":    "us,eu",
            "markets":    "h2h",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()

        used      = resp.headers.get("x-requests-used", "?")
        remaining = resp.headers.get("x-requests-remaining", "?")
        events    = resp.json()
        print(f"  [Odds API] {sport_title}: {len(events)} events  "
              f"|  credits used: {used}  remaining: {remaining}")

        # Enrich each event so routers/scripts can infer surface without
        # needing to call the sports endpoint again.
        for ev in events:
            ev["_sport_key"]   = sport_key
            ev["_sport_title"] = sport_title

        all_events.extend(events)

    _save_cache(all_events)
    return all_events


def fetch_scores(api_key: str, days_from: int = 3) -> List[dict]:
    """
    Return completed + in-progress scores for the last *days_from* days
    across all currently active ATP tournaments. Costs 1 credit per tournament.
    """
    sports = active_atp_sport_keys(api_key)
    if not sports:
        return []

    all_scores: List[dict] = []
    for sport in sports:
        sport_key = sport["key"]
        url    = f"{API_BASE}/sports/{sport_key}/scores"
        params = {
            "apiKey":     api_key,
            "daysFrom":   days_from,
            "dateFormat": "iso",
        }
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()

        used      = resp.headers.get("x-requests-used", "?")
        remaining = resp.headers.get("x-requests-remaining", "?")
        scores    = resp.json()
        print(f"  [Odds API] {sport['title']} scores: {len(scores)}  "
              f"|  credits used: {used}  remaining: {remaining}")

        all_scores.extend(scores)

    return all_scores


def best_odds(event: dict) -> Dict[str, float]:
    """Best H2H decimal odds across all bookmakers: {player_name: odds}."""
    best: Dict[str, float] = {}
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "h2h":
                continue
            for outcome in mkt.get("outcomes", []):
                name  = outcome["name"]
                price = float(outcome["price"])
                if price > best.get(name, 0.0):
                    best[name] = price
    return best


def all_book_odds(event: dict) -> Dict[str, Dict[str, float]]:
    """Per-bookmaker H2H odds: {book_key: {player_name: decimal_odds}}."""
    result: Dict[str, Dict[str, float]] = {}
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "h2h":
                continue
            result[bm["key"]] = {
                o["name"]: float(o["price"])
                for o in mkt.get("outcomes", [])
            }
    return result
