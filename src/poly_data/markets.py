"""Market filtering and parsing utilities — pure logic, no API calls."""

from __future__ import annotations

import json
from typing import Any


def parse_json_field(raw: Any) -> Any:
    """Parse a Gamma API field that may be a JSON string or already a list/dict."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


class MarketFilter:
    """Static methods for classifying Polymarket markets.

    These filters determine which markets are relevant for sports trading
    strategies (head-to-head matchups, soccer beat/draw markets, etc.).
    """

    @staticmethod
    def is_head_to_head(market: dict[str, Any]) -> bool:
        """Return True if this is a head-to-head game market (not a prop/side bet).

        Head-to-head markets have exactly 2 outcomes and a question containing
        'vs' (e.g. "Knicks vs. Hornets").  Excluded:
        - Props (Yes/No outcomes)
        - Spreads ("Spread:" in question)
        - Over/Under (outcomes contain Over/Under)
        - Partial-game markets (halves, quarters, periods)
        """
        question = market.get("question", "")
        q_lower = question.lower()
        outcomes = parse_json_field(market.get("outcomes", []))

        if not isinstance(outcomes, list) or len(outcomes) != 2:
            return False

        # Must contain "vs" or "v" as a matchup indicator
        if " vs" not in q_lower and " v " not in q_lower:
            return False

        # Exclude Yes/No outcomes (props)
        outcome_set = {o.strip().lower() for o in outcomes}
        if outcome_set & {"yes", "no"}:
            return False

        # Exclude Over/Under
        if outcome_set & {"over", "under"}:
            return False

        # Exclude spread markets
        if "spread" in q_lower:
            return False

        # Exclude partial-game markets
        partial_game_markers = [
            "1h ", "2h ", "1q ", "2q ", "3q ", "4q ",
            "1h:", "2h:", "1q:", "2q:", "3q:", "4q:",
            "1st half", "2nd half",
            "1st quarter", "2nd quarter", "3rd quarter", "4th quarter",
            "1st period", "2nd period", "3rd period",
            "1p ", "2p ", "3p ",
            "1p:", "2p:", "3p:",
        ]
        if any(marker in q_lower for marker in partial_game_markers):
            return False

        return True

    @staticmethod
    def is_soccer_event(event: dict[str, Any]) -> bool:
        """Return True if this event is a soccer match."""
        tags = [
            t.get("label", "").lower() if isinstance(t, dict) else str(t).lower()
            for t in event.get("tags", [])
        ]
        title = event.get("title", "").lower()
        soccer_indicators = [
            "soccer", "premier-league", "premier league", "champions-league",
            "champions league", "la-liga", "la liga", "bundesliga", "serie-a",
            "serie a", "ligue-1", "ligue 1", "mls", "europa-league",
            "europa league", "leagues-cup", "epl",
        ]
        combined = " ".join(tags)
        return any(ind in combined or ind in title for ind in soccer_indicators)

    @staticmethod
    def is_soccer_match_market(market: dict[str, Any]) -> bool:
        """Return True if this is a soccer match market (beat/draw Yes/No)."""
        question = market.get("question", "")
        q_lower = question.lower()
        outcomes = parse_json_field(market.get("outcomes", []))

        if not isinstance(outcomes, list) or len(outcomes) != 2:
            return False

        outcome_set = {o.strip().lower() for o in outcomes}
        if outcome_set != {"yes", "no"}:
            return False

        return "beat" in q_lower or "draw" in q_lower

    @classmethod
    def should_include(
        cls,
        market: dict[str, Any],
        event: dict[str, Any] | None = None,
    ) -> bool:
        """Return True if this market should be included for trading/analysis.

        Accepts head-to-head markets (NBA/NFL/MLB/NHL style) and
        soccer match markets (Yes/No beat/draw questions).
        """
        if cls.is_head_to_head(market):
            return True
        if event is not None and cls.is_soccer_event(event) and cls.is_soccer_match_market(market):
            return True
        return False


def extract_winner(market: dict[str, Any]) -> str | None:
    """Extract the winning outcome from a resolved market.

    Checks ``outcome_prices`` (or ``outcomePrices``) — the winner has
    a payout of 1.0 (or "1").
    """
    outcomes = parse_json_field(market.get("outcomes", []))
    outcome_prices = parse_json_field(
        market.get("outcomePrices") or market.get("outcome_prices", "[]")
    )

    if not isinstance(outcomes, list) or not isinstance(outcome_prices, list):
        return None
    if len(outcomes) != len(outcome_prices):
        return None

    for outcome, price in zip(outcomes, outcome_prices):
        try:
            if float(price) == 1.0:
                return outcome
        except (ValueError, TypeError):
            continue

    return None


def detect_sport(title: str, tags: list[Any] | None = None) -> str:
    """Detect the sport from event tags or title keywords.

    Returns an uppercase sport name (``"NBA"``, ``"SOCCER"``, etc.)
    or ``"UNKNOWN"`` / ``"OTHER"`` if undetectable.
    """
    # Prefer tags if available
    if tags:
        tag_labels = [
            t.get("label", "").lower() if isinstance(t, dict) else str(t).lower()
            for t in tags
        ]
        tag_str = " ".join(tag_labels)
        for sport in ["nba", "nfl", "mlb", "nhl", "mma", "tennis"]:
            if sport in tag_str:
                return sport.upper()
        soccer_indicators = [
            "soccer", "premier-league", "champions-league", "la-liga",
            "bundesliga", "serie-a", "ligue-1", "mls", "europa-league", "epl",
        ]
        if any(ind in tag_str for ind in soccer_indicators):
            return "SOCCER"

    # Fall back to title-based detection
    title_lower = title.lower()
    # (Could add hardcoded team lists here for better detection)
    for sport in ["nba", "nfl", "mlb", "nhl", "mma"]:
        if sport in title_lower:
            return sport.upper()

    soccer_title_hints = ["premier league", "champions league", "la liga", "bundesliga", "serie a"]
    if any(hint in title_lower for hint in soccer_title_hints):
        return "SOCCER"

    return "UNKNOWN"
