"""Gamma API client — event metadata and resolution data."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from poly_data._http import GAMMA_API, get_json

logger = logging.getLogger(__name__)

# Default sport slugs used for queries.
# Covers all 42 slugs with confirmed resolved game data on Polymarket.
DEFAULT_SPORT_SLUGS = [
    # --- US traditional ---
    "nba", "nfl", "mlb", "nhl",
    # --- College ---
    "cbb", "cwbb", "cfb",
    # --- Soccer ---
    "epl", "laliga", "bundesliga", "ligue-1", "mls", "ucl", "uel", "sea",
    "mex", "ere", "tur", "sud", "itc", "lib",
    "caf", "concacaf", "conmebol", "uef-qualifiers",
    # --- Hockey ---
    "cehl", "dehl", "ahl", "khl", "shl",
    # --- Combat ---
    "mwoh", "wwoh", "wbc",
    # --- Lacrosse ---
    "pll", "wll",
    # --- Individual ---
    "atp", "wta", "golf",
    # --- Esports ---
    "counter-strike", "call-of-duty", "dota-2", "league-of-legends",
    "mobile-legends-bang-bang", "overwatch", "rainbow-six-siege",
    "rocket-league", "starcraft-2", "valorant",
    # --- Tennis (table) ---
    "wtt-mens-singles",
    # --- Cricket ---
    "cricipl", "cricpsl", "cricss",
]


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
                "tag_slug": slug,
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
                "tag_slug": slug,
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
