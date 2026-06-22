from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from data.loader import PlayerDB

router = APIRouter(prefix="/api")

_db: PlayerDB = None


def init(db: PlayerDB):
    global _db
    _db = db


@router.get("/players")
def list_players(
    search: str = Query("", description="Name substring filter"),
    hand: Optional[str] = Query(None, description="R or L"),
    country: Optional[str] = Query(None, description="IOC country code"),
    limit: int = Query(200, le=500),
):
    return _db.search_players(query=search, hand=hand, country=country, limit=limit)


@router.get("/players/{name:path}")
def get_player(name: str):
    player = _db.get_player(name)
    if player is None:
        raise HTTPException(404, f"Player not found: {name}")
    return player
