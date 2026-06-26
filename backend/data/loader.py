"""ATP match data loader. Builds in-memory player profiles at startup."""
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ATP_DIR = Path(__file__).parent.parent.parent / "ATP_Matches"
MIN_MATCHES = 5


def _canonicalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mixing data sources (Sackmann + TML) means the same player can appear
    under different capitalizations (e.g. "Alex De Minaur" vs "Alex de
    Minaur"), which would otherwise split one player into two profiles.
    Collapse each case-insensitive name group onto whichever exact spelling
    appears most often across the combined dataset.
    """
    counts = pd.concat([df["winner_name"], df["loser_name"]]).value_counts()
    canonical: Dict[str, str] = {}
    for name, count in counts.items():
        key = name.lower()
        if key not in canonical or count > counts[canonical[key]]:
            canonical[key] = name

    name_map = {name: canonical[name.lower()] for name in counts.index}
    df = df.copy()
    df["winner_name"] = df["winner_name"].map(name_map)
    df["loser_name"] = df["loser_name"].map(name_map)
    return df


def load_all_matches() -> pd.DataFrame:
    files = sorted(ATP_DIR.glob("atp_matches_*.csv"))
    dfs = [pd.read_csv(f, low_memory=False) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["tourney_date", "winner_name", "loser_name"])
    df = _canonicalize_names(df)
    return df.sort_values("tourney_date").reset_index(drop=True)


def _safe(val, default):
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


class PlayerDB:
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.profiles: Dict[str, Dict] = {}
        self._h2h: Dict[Tuple[str, str], Dict[str, int]] = {}
        self._build()

    def _build(self):
        df = self._df

        # --- Career win/loss counts ---
        career_wins = df.groupby("winner_name").size()
        career_losses = df.groupby("loser_name").size()

        # --- Most recent physical/ranking info per player ---
        df_s = df.sort_values("tourney_date")
        latest_w = (
            df_s.dropna(subset=["winner_rank"])
            .drop_duplicates("winner_name", keep="last")
            .set_index("winner_name")[
                ["winner_hand", "winner_ht", "winner_ioc", "winner_age",
                 "winner_rank", "winner_rank_points"]
            ]
            .rename(columns=lambda c: c.replace("winner_", ""))
        )
        latest_l = (
            df_s.dropna(subset=["loser_rank"])
            .drop_duplicates("loser_name", keep="last")
            .set_index("loser_name")[
                ["loser_hand", "loser_ht", "loser_ioc", "loser_age",
                 "loser_rank", "loser_rank_points"]
            ]
            .rename(columns=lambda c: c.replace("loser_", ""))
        )
        latest = latest_w.combine_first(latest_l)

        # --- Minutes, aces, serve games ---
        w_min = df.groupby("winner_name")["minutes"].sum()
        l_min = df.groupby("loser_name")["minutes"].sum()
        w_aces = df.groupby("winner_name")["w_ace"].sum()
        l_aces = df.groupby("loser_name")["l_ace"].sum()
        w_svgms = df.groupby("winner_name")["w_SvGms"].sum()
        l_svgms = df.groupby("loser_name")["l_SvGms"].sum()

        # --- Surface stats ---
        w_surf = df.groupby(["winner_name", "surface"]).size().reset_index(name="wins")
        l_surf = df.groupby(["loser_name", "surface"]).size().reset_index(name="losses")
        w_surf = w_surf.rename(columns={"winner_name": "name"})
        l_surf = l_surf.rename(columns={"loser_name": "name"})
        surf_df = (
            w_surf.merge(l_surf, on=["name", "surface"], how="outer")
            .fillna(0)
        )
        surf_df["total"] = surf_df["wins"] + surf_df["losses"]
        surf_df["win_pct"] = (
            (surf_df["wins"] / surf_df["total"])
            .where(surf_df["total"] > 0, 0.5)
            .round(3)
        )
        surf_lookup: Dict[str, Dict] = {}
        for _, row in surf_df.iterrows():
            surf_lookup.setdefault(row["name"], {})[row["surface"]] = {
                "wins": int(row["wins"]),
                "losses": int(row["losses"]),
                "win_pct": float(row["win_pct"]),
            }

        # --- Recent form (last 20 matches) ---
        events_w = (
            df[["tourney_date", "winner_name"]]
            .assign(won=True)
            .rename(columns={"winner_name": "name"})
        )
        events_l = (
            df[["tourney_date", "loser_name"]]
            .assign(won=False)
            .rename(columns={"loser_name": "name"})
        )
        events = pd.concat([events_w, events_l]).sort_values("tourney_date")
        recent_form = (
            events.groupby("name")["won"]
            .apply(lambda x: float(x.tail(20).mean()) if len(x) > 0 else 0.5)
            .to_dict()
        )

        # --- Recent match history (last 10, most recent first) ---
        ev_full = pd.concat([
            df[["tourney_date", "winner_name", "loser_name", "surface", "score"]]
            .rename(columns={"winner_name": "name", "loser_name": "opponent"})
            .assign(result="W"),
            df[["tourney_date", "loser_name", "winner_name", "surface", "score"]]
            .rename(columns={"loser_name": "name", "winner_name": "opponent"})
            .assign(result="L"),
        ]).sort_values("tourney_date")

        recent_matches_lookup: Dict[str, List] = {}
        for name, grp in ev_full.groupby("name"):
            recent_matches_lookup[name] = [
                {
                    "date": str(r["tourney_date"])[:10],
                    "opponent": r["opponent"],
                    "surface": _safe(r.get("surface"), "Hard"),
                    "result": r["result"],
                    "score": _safe(r.get("score"), ""),
                }
                for _, r in grp.tail(10).iloc[::-1].iterrows()
            ]

        # --- H2H ---
        for _, row in df.iterrows():
            w, l = row["winner_name"], row["loser_name"]
            key = tuple(sorted([w, l]))
            if key not in self._h2h:
                self._h2h[key] = {key[0]: 0, key[1]: 0}
            self._h2h[key][w] = self._h2h[key].get(w, 0) + 1

        # --- Assemble profiles ---
        all_names = set(career_wins.index) | set(career_losses.index)
        for name in all_names:
            wins = int(career_wins.get(name, 0))
            losses = int(career_losses.get(name, 0))
            matches = wins + losses
            if matches < MIN_MATCHES:
                continue

            lat = latest.loc[name] if name in latest.index else {}

            rank_raw = lat.get("rank") if isinstance(lat, pd.Series) else None
            rp_raw = lat.get("rank_points") if isinstance(lat, pd.Series) else None

            total_min = float(_safe(w_min.get(name), 0)) + float(_safe(l_min.get(name), 0))
            total_aces = float(_safe(w_aces.get(name), 0)) + float(_safe(l_aces.get(name), 0))
            total_svgms = float(_safe(w_svgms.get(name), 0)) + float(_safe(l_svgms.get(name), 0))

            player_surf = surf_lookup.get(name, {})
            for surf in ["Hard", "Clay", "Grass"]:
                player_surf.setdefault(surf, {"wins": 0, "losses": 0, "win_pct": 0.5})

            self.profiles[name] = {
                "name": name,
                "hand": _safe(lat.get("hand") if isinstance(lat, pd.Series) else None, "U"),
                "height": float(_safe(lat.get("ht") if isinstance(lat, pd.Series) else None, 185.0)),
                "country": _safe(lat.get("ioc") if isinstance(lat, pd.Series) else None, ""),
                "age": round(float(_safe(lat.get("age") if isinstance(lat, pd.Series) else None, 25.0)), 1),
                "rank": None if (rank_raw is None or pd.isna(rank_raw)) else int(rank_raw),
                "rank_points": None if (rp_raw is None or pd.isna(rp_raw)) else int(rp_raw),
                "career_wins": wins,
                "career_losses": losses,
                "career_matches": matches,
                "career_win_pct": round(wins / matches, 3),
                "minutes_per_match": round(total_min / matches, 1),
                "ace_rate": round(total_aces / total_svgms, 4) if total_svgms > 0 else 0.0,
                "surface_stats": player_surf,
                "recent_win_pct": round(recent_form.get(name, 0.5), 3),
                "recent_matches": recent_matches_lookup.get(name, []),
            }

    def get_player(self, name: str) -> Optional[Dict]:
        if name in self.profiles:
            return self.profiles[name]
        name_lower = name.lower()
        for k, v in self.profiles.items():
            if k.lower() == name_lower:
                return v
        return None

    def search_players(
        self,
        query: str = "",
        hand: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        results = list(self.profiles.values())
        if query:
            q = query.lower()
            results = [p for p in results if q in p["name"].lower()]
        if hand:
            results = [p for p in results if p["hand"] == hand.upper()]
        if country:
            results = [p for p in results if p["country"].lower() == country.lower()]
        results.sort(key=lambda p: (p["rank"] or 9999, p["name"]))
        return results[:limit]

    def h2h_win_pct(self, p1: str, p2: str) -> float:
        key = tuple(sorted([p1, p2]))
        h2h = self._h2h.get(key)
        if not h2h:
            return 0.5
        total = sum(h2h.values())
        return h2h.get(p1, 0) / total if total > 0 else 0.5

    def get_h2h_record(self, p1: str, p2: str) -> Dict:
        key = tuple(sorted([p1, p2]))
        h2h = self._h2h.get(key, {})
        return {
            "p1_wins": h2h.get(p1, 0),
            "p2_wins": h2h.get(p2, 0),
            "total": sum(h2h.values()),
        }
