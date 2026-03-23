"""ESPN client — game schedules, start times, and team matching."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from poly_data._http import ESPN_BASE, get_json

logger = logging.getLogger(__name__)

# ESPN sport paths — one per league.
ESPN_SPORT_PATHS: dict[str, list[str]] = {
    # --- Traditional US sports (P0, live) ---
    "nba": ["basketball/nba"],
    "nfl": ["football/nfl"],
    "mlb": ["baseball/mlb"],
    "nhl": ["hockey/nhl"],
    # --- Soccer (P0, live) ---
    "soccer": [
        "soccer/eng.1",     # EPL
        "soccer/esp.1",     # La Liga
        "soccer/ger.1",     # Bundesliga
        "soccer/ita.1",     # Serie A
        "soccer/fra.1",     # Ligue 1
        "soccer/usa.1",     # MLS
        "soccer/uefa.champions",  # UCL
        "soccer/uefa.europa",     # UEL
    ],
    # --- Combat sports (P1) ---
    "mma": ["mma/ufc"],
    # --- College sports (P1) ---
    "ncaam": ["basketball/mens-college-basketball"],
    "ncaaf": ["football/college-football"],
    # --- Other traditional (P2) ---
    "wnba": ["basketball/wnba"],
    "tennis": ["tennis/atp"],
    "golf": ["golf/pga"],
    "f1": ["racing/f1"],
    "cricket": ["cricket/icc"],  # Seasonal — may return 0 events outside tournaments
    # --- Esports — no ESPN coverage, use PandaScore ---
    "cs2": [],
    "valorant": [],
    "lol": [],
    "dota2": [],
    "overwatch": [],
    "cod": [],
    # --- No ESPN endpoint found ---
    "rugby": [],
    "boxing": [],
}

# In-memory cache to avoid repeated ESPN calls for the same date/sport.
_espn_cache: dict[str, list[dict]] = {}


class ESPNClient:
    """Client for the ESPN Scoreboard API — real game start times.

    Parameters
    ----------
    base_url : str
        Override the ESPN API base URL.
    """

    def __init__(self, base_url: str = ESPN_BASE) -> None:
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Scoreboard
    # ------------------------------------------------------------------
    def fetch_scoreboard(self, sport: str, date_str: str) -> list[dict[str, Any]]:
        """Fetch ESPN scoreboard events for a sport on a specific date.

        Parameters
        ----------
        sport : str
            Sport key (``"nba"``, ``"soccer"``, etc.).
        date_str : str
            Date string ``YYYYMMDD``.

        Returns
        -------
        list[dict]
            ESPN event dicts from the scoreboard endpoint.
        """
        cache_key = f"{sport}:{date_str}"
        if cache_key in _espn_cache:
            return _espn_cache[cache_key]

        paths = ESPN_SPORT_PATHS.get(sport, [])
        if not paths:
            return []

        events: list[dict[str, Any]] = []
        for path in paths:
            url = f"{self.base_url}/{path}/scoreboard"
            try:
                data = get_json(url, params={"dates": date_str})
                events.extend(data.get("events", []) if isinstance(data, dict) else [])
            except Exception:
                logger.debug("ESPN fetch failed for %s on %s", path, date_str, exc_info=True)

        _espn_cache[cache_key] = events
        return events

    # ------------------------------------------------------------------
    # Team matching helpers
    # ------------------------------------------------------------------
    @staticmethod
    def extract_teams(event: dict) -> set[str]:
        """Extract lowercased team names from an ESPN event dict."""
        teams: set[str] = set()
        for comp in event.get("competitions", [{}]):
            for team_entry in comp.get("competitors", []):
                team = team_entry.get("team", {})
                for key in ("displayName", "shortDisplayName", "name", "abbreviation"):
                    val = team.get(key, "")
                    if val:
                        teams.add(val.lower())
        return teams

    @staticmethod
    def normalize_team(name: str) -> str:
        """Normalize a team name for fuzzy matching.

        Removes FC/SC/the, punctuation, and extra whitespace.
        """
        name = name.lower().strip()
        name = re.sub(r"\b(fc|sc|the)\b", "", name)
        name = re.sub(r"[^a-z0-9\s]", "", name)
        return " ".join(name.split())

    @staticmethod
    def extract_poly_teams(title: str) -> list[str]:
        """Extract team names from a Polymarket 'X vs. Y' title."""
        for sep in [" vs. ", " vs ", " v. ", " v "]:
            if sep in title.lower():
                idx = title.lower().index(sep)
                team_a = title[:idx].strip()
                team_b = title[idx + len(sep) :].strip()
                # Strip trailing question marks, colons etc.
                team_b = re.sub(r"[?:!]+$", "", team_b).strip()
                return [team_a, team_b]
        return []

    @classmethod
    def teams_match(cls, poly_teams: list[str], espn_teams: set[str]) -> bool:
        """Check if Polymarket team names match ESPN team names (fuzzy)."""
        if len(poly_teams) < 2:
            return False
        matched = 0
        for pt in poly_teams:
            pt_norm = cls.normalize_team(pt)
            for et in espn_teams:
                et_norm = cls.normalize_team(et)
                if pt_norm in et_norm or et_norm in pt_norm:
                    matched += 1
                    break
        return matched >= 2

    # ------------------------------------------------------------------
    # High-level: find game time
    # ------------------------------------------------------------------
    def find_game_time(
        self,
        title: str,
        anchor_date: str,
        sport: str,
        *,
        search_days: int = 3,
    ) -> str | None:
        """Find the real game start time by matching a Polymarket title to ESPN.

        Parameters
        ----------
        title : str
            Polymarket event title (e.g. ``"Knicks vs. Hornets"``).
        anchor_date : str
            Anchor date ``YYYY-MM-DD`` (typically the first trade date).
        sport : str
            Sport key (``"nba"``, ``"soccer"``, etc.).
        search_days : int
            Search ±N days around the anchor date.

        Returns
        -------
        str | None
            ISO datetime of the game start, or None if no match found.
        """
        poly_teams = self.extract_poly_teams(title)
        if not poly_teams:
            return None

        anchor = datetime.strptime(anchor_date, "%Y-%m-%d")

        for delta in range(-search_days, search_days + 1):
            check_date = anchor + timedelta(days=delta)
            date_str = check_date.strftime("%Y%m%d")
            events = self.fetch_scoreboard(sport, date_str)

            for event in events:
                espn_teams = self.extract_teams(event)
                if self.teams_match(poly_teams, espn_teams):
                    game_time = event.get("date")
                    if game_time:
                        return game_time

        return None

    # ------------------------------------------------------------------
    # DataFrame helper
    # ------------------------------------------------------------------
    def fetch_scoreboard_df(self, sport: str, date_str: str) -> pd.DataFrame:
        """Like :meth:`fetch_scoreboard` but return a DataFrame."""
        events = self.fetch_scoreboard(sport, date_str)
        if not events:
            return pd.DataFrame()
        return pd.json_normalize(events)
