"""Gamma API client — event metadata and resolution data."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from poly_data._http import GAMMA_API, get_json

logger = logging.getLogger(__name__)

# Default sport slugs used for queries.
# Covers all 85 slugs with confirmed resolved game data on Polymarket.
DEFAULT_SPORT_SLUGS = [
    # --- US traditional ---
    "nba", "nfl", "mlb", "nhl",
    # --- College ---
    "cbb", "cwbb", "cfb",
    # --- Soccer ---
    "epl", "laliga", "bundesliga", "ligue-1", "mls", "ucl", "uel", "sea",
    "bra", "bra2", "jap", "ja2", "kor", "csl", "mex", "ere", "por", "tur",
    "nor", "den", "spl", "ssc", "aus", "ruprem", "ucol",
    "sud", "itc", "lib", "cdr", "cde", "dfb",
    "caf", "concacaf", "conmebol", "uef-qualifiers",
    "afc-wc", "fifa-friendlies",
    # --- Hockey ---
    "cehl", "dehl", "ahl", "khl", "shl",
    # --- Basketball (international) ---
    "bkcba", "bkcl", "bkfr1", "bkkbl", "bkligend", "bknbl", "bkseriea", "bkarg",
    "rueuchamp",
    # --- Rugby ---
    "rusixnat", "rusrp", "rutopft", "ruurc",
    # --- Lacrosse ---
    "pll", "wll",
    # --- Combat / Baseball ---
    "wbc",
    # --- Individual ---
    "atp", "wta", "golf",
    # --- Table Tennis ---
    "wtt-mens-singles",
    # --- Esports ---
    "counter-strike", "call-of-duty", "dota-2", "league-of-legends",
    "mobile-legends-bang-bang", "overwatch", "rainbow-six-siege",
    "rocket-league", "starcraft-2", "valorant",
    "mwoh", "wwoh",
    # --- Cricket ---
    "cricipl", "cricpsl", "cricbbl", "criccsat20w", "cricps", "cricss",
    "cricthunderbolt", "cricwncl", "criclcl", "cricpakt20cup",
    "crict20lpl", "crichkt20w", "crint",
]

# Mapping from frontend URL slugs to actual Gamma API tag_slug values.
# Polymarket's website routes use short slugs that differ from the event
# tag_slug stored in the Gamma API.  This mapping bridges the gap.
TAG_SLUG_MAP: dict[str, str] = {
    # Soccer
    "laliga": "la-liga",
    "bra": "brazil-serie-a",
    "bra2": "serie-b",
    "jap": "japan-j-league",
    "ja2": "japan-j2-league",
    "kor": "k-league",
    "csl": "chinese-super-league",
    "por": "primeira-liga",
    "nor": "norway-eliteserien",
    "den": "denmark-superliga",
    "spl": "scottish-premiership",
    "ssc": "efl-championship",
    "aus": "australian-a-league",
    "cdr": "copa-del-rey",
    "cde": "copa-del-rey",
    "dfb": "dfb-pokal",
    "ruprem": "rus",
    "ucol": "ukraine-premier-liha",
    "afc-wc": "world-cup-qualifiers",
    "fifa-friendlies": "fifa",
    # Basketball (international)
    "bkcba": "cba",
    "bkcl": "basketball-champions-league",
    "bkfr1": "pro-a",
    "bkkbl": "kbl",
    "bkligend": "liga-endesa",
    "bknbl": "nbl",
    "bkseriea": "basketball-series-a",
    "bkarg": "lnb",
    "rueuchamp": "euroleague",
    # Cricket
    "cricthunderbolt": "thunderbolt-t10-league",
    "cricwncl": "womens-national-cricket-league",
    "criclcl": "legends-league-cricket",
    "cricpakt20cup": "national-t20-cup",
    "cricipl": "ipl",
    "cricpsl": "pakistan-super-league",
    "cricbbl": "big-bash-league",
    "criccsat20w": "csa-t20",
    "cricps": "sheffield-shield",
    "cricss": "cricket-new-zealand",
    "crict20lpl": "lanka-premier-league",
    "crichkt20w": "t20",
    "crint": "international-cricket",
    # Esports
    "mwoh": "honor-of-kings",
    "wwoh": "honor-of-kings",
    # Table Tennis
    "wtt-mens-singles": "wttms",
    # Rugby
    "rusixnat": "rugby-six-nations",
    "rusrp": "rugby-premiership",
    "rutopft": "rugby-top-14",
    "ruurc": "united-rugby-championship",
}


def resolve_tag_slug(slug: str) -> str:
    """Convert a frontend URL slug to the real Gamma API ``tag_slug``."""
    return TAG_SLUG_MAP.get(slug, slug)


class GammaClient:
    """Client for the Polymarket Gamma API (event metadata & resolution).

    Parameters
    ----------
    base_url : str
        Override the Gamma API base URL (useful for testing).
    sport_slugs : list[str]
        Sport tag slugs to query. Defaults to the major US/international sports.
    """

    def __init__(
        self,
        base_url: str = GAMMA_API,
        sport_slugs: list[str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sport_slugs = sport_slugs or DEFAULT_SPORT_SLUGS

    # ------------------------------------------------------------------
    # Active events
    # ------------------------------------------------------------------
    def fetch_events(
        self,
        *,
        active_only: bool = True,
        sport_slugs: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch sports events from the Gamma API.

        Parameters
        ----------
        active_only : bool
            If True, only return events that are not yet closed.
        sport_slugs : list[str], optional
            Override the default sport slugs for this call.
        limit : int
            Maximum events per page per sport slug.

        Returns
        -------
        list[dict]
            Deduplicated list of event dicts.
        """
        slugs = sport_slugs or self.sport_slugs
        seen_ids: set[str] = set()
        events: list[dict[str, Any]] = []

        for slug in slugs:
            params: dict[str, Any] = {
                "tag_slug": resolve_tag_slug(slug),
                "limit": limit,
            }
            if active_only:
                params["closed"] = "false"

            try:
                data = get_json(f"{self.base_url}/events", params=params)
            except Exception:
                logger.warning("Failed to fetch events for slug=%s", slug, exc_info=True)
                continue

            if not isinstance(data, list):
                data = [data]

            for event in data:
                eid = str(event.get("id", ""))
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    events.append(event)

        return events

    # ------------------------------------------------------------------
    # Resolved events
    # ------------------------------------------------------------------
    def fetch_resolved_events(
        self,
        start_date: str,
        end_date: str,
        *,
        sport_slugs: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch resolved (closed) sports events in a date range.

        Parameters
        ----------
        start_date : str
            Inclusive start date (YYYY-MM-DD).
        end_date : str
            Inclusive end date (YYYY-MM-DD).
        sport_slugs : list[str], optional
            Override the default sport slugs for this call.
        limit : int
            Maximum events per page per sport slug.

        Returns
        -------
        list[dict]
            Deduplicated list of resolved event dicts.
        """
        slugs = sport_slugs or self.sport_slugs
        seen_ids: set[str] = set()
        events: list[dict[str, Any]] = []

        for slug in slugs:
            params: dict[str, Any] = {
                "tag_slug": resolve_tag_slug(slug),
                "closed": "true",
                "start_date_min": start_date,
                "end_date_max": end_date,
                "limit": limit,
            }
            try:
                data = get_json(f"{self.base_url}/events", params=params)
            except Exception:
                logger.warning("Failed to fetch resolved events for slug=%s", slug, exc_info=True)
                continue

            if not isinstance(data, list):
                data = [data]

            for event in data:
                eid = str(event.get("id", ""))
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    events.append(event)

        return events

    # ------------------------------------------------------------------
    # DataFrame helpers
    # ------------------------------------------------------------------
    def fetch_events_df(self, **kwargs) -> pd.DataFrame:
        """Like :meth:`fetch_events` but return a DataFrame."""
        return pd.json_normalize(self.fetch_events(**kwargs))

    def fetch_resolved_events_df(self, start_date: str, end_date: str, **kwargs) -> pd.DataFrame:
        """Like :meth:`fetch_resolved_events` but return a DataFrame."""
        return pd.json_normalize(self.fetch_resolved_events(start_date, end_date, **kwargs))
