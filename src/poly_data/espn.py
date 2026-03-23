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
    def fetch_scoreboard(self, sport: str, date_str: str | None = None) -> list[dict[str, Any]]:
        """Fetch ESPN scoreboard events for a sport on a specific date.

        Parameters
        ----------
        sport : str
            Sport key (``"nba"``, ``"soccer"``, etc.).
        date_str : str | None
            Date string ``YYYYMMDD``.  If ``None``, returns the current
            matchday (ESPN's default), which is especially useful for soccer
            where the ``dates`` parameter doesn't always match UTC calendar
            dates.

        Returns
        -------
        list[dict]
            ESPN event dicts from the scoreboard endpoint.
        """
        cache_key = f"{sport}:{date_str or 'default'}"
        if cache_key in _espn_cache:
            return _espn_cache[cache_key]

        paths = ESPN_SPORT_PATHS.get(sport, [])
        if not paths:
            return []

        events: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for path in paths:
            url = f"{self.base_url}/{path}/scoreboard"
            params: dict[str, Any] = {}
            if date_str is not None:
                params["dates"] = date_str
            try:
                data = get_json(url, params=params or None)
                for ev in data.get("events", []) if isinstance(data, dict) else []:
                    eid = ev.get("id", "")
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        events.append(ev)
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

        # For soccer, also try the default matchday (no date param) since
        # ESPN soccer uses matchday windows that don't align with UTC calendar dates.
        if sport == "soccer":
            default_events = self.fetch_scoreboard(sport, None)
            for event in default_events:
                espn_teams = self.extract_teams(event)
                if self.teams_match(poly_teams, espn_teams):
                    game_time = event.get("date")
                    if game_time:
                        return game_time

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

    def find_game_event(
        self,
        title: str,
        anchor_date: str,
        sport: str,
        *,
        search_days: int = 3,
    ) -> dict[str, Any] | None:
        """Like :meth:`find_game_time` but returns the full ESPN event dict.

        This is useful when you need more than just the start time — e.g.
        period count, competition status, or team scores.

        Returns
        -------
        dict | None
            The full ESPN event dict, or None if no match found.
        """
        poly_teams = self.extract_poly_teams(title)
        if not poly_teams:
            return None

        anchor = datetime.strptime(anchor_date, "%Y-%m-%d")

        if sport == "soccer":
            default_events = self.fetch_scoreboard(sport, None)
            for event in default_events:
                if self.teams_match(poly_teams, self.extract_teams(event)):
                    return event

        for delta in range(-search_days, search_days + 1):
            check_date = anchor + timedelta(days=delta)
            date_str = check_date.strftime("%Y%m%d")
            events = self.fetch_scoreboard(sport, date_str)
            for event in events:
                if self.teams_match(poly_teams, self.extract_teams(event)):
                    return event

        return None

    @staticmethod
    def estimate_game_end(event: dict, sport: str = "nba") -> str | None:
        """Estimate the game end time from an ESPN event dict.

        Uses the event start time plus a sport-specific duration estimate,
        adjusted for overtime periods when available.

        Parameters
        ----------
        event : dict
            ESPN event dict (from :meth:`find_game_event`).
        sport : str
            Sport key for duration estimation.

        Returns
        -------
        str | None
            Estimated end time as ISO datetime, or None.
        """
        start = event.get("date")
        if not start:
            return None

        # Base durations (minutes) per sport
        base_minutes: dict[str, int] = {
            "nba": 150, "nfl": 210, "mlb": 180, "nhl": 150,
            "soccer": 115, "mma": 60, "ncaam": 140, "ncaaf": 210,
            "wnba": 130, "tennis": 120, "golf": 300, "f1": 120,
        }
        minutes = base_minutes.get(sport, 150)

        # Check for overtime periods
        for comp in event.get("competitions", []):
            period = comp.get("status", {}).get("period", 0)
            if sport == "nba" and period > 4:
                minutes += (period - 4) * 10  # ~10 min per OT
            elif sport == "nhl" and period > 3:
                minutes += (period - 3) * 10

        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(minutes=minutes)
            return end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # DataFrame helper
    # ------------------------------------------------------------------
    def fetch_scoreboard_df(self, sport: str, date_str: str | None = None) -> pd.DataFrame:
        """Like :meth:`fetch_scoreboard` but return a DataFrame."""
        events = self.fetch_scoreboard(sport, date_str)
        if not events:
            return pd.DataFrame()
        return pd.json_normalize(events)
