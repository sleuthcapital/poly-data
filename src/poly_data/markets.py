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

        Accepts head-to-head markets (NBA/NFL/MLB/NHL style), soccer match
        markets (Yes/No beat/draw questions), and esports H2H markets.
        """
        if cls.is_head_to_head(market):
            return True
        if event is not None and cls.is_soccer_event(event) and cls.is_soccer_match_market(market):
            return True
        if event is not None and cls.is_esports_event(event) and cls.is_head_to_head(market):
            return True
        return False

    @staticmethod
    def is_esports_event(event: dict[str, Any]) -> bool:
        """Return True if this event is an esports match."""
        tags = [
            t.get("label", "").lower() if isinstance(t, dict) else str(t).lower()
            for t in event.get("tags", [])
        ]
        title = event.get("title", "").lower()
        esport_indicators = [
            "esports", "cs2", "csgo", "counter-strike", "valorant",
            "league-of-legends", "lol", "dota", "dota-2", "dota2",
            "overwatch", "call-of-duty", "cod",
        ]
        combined = " ".join(tags)
        return any(ind in combined or ind in title for ind in esport_indicators)

    @staticmethod
    def is_esports_h2h(market: dict[str, Any]) -> bool:
        """Return True if this is an esports head-to-head team matchup.

        Esports H2H markets have exactly 2 non-Yes/No outcomes and typically
        contain 'vs' in the question — same structure as traditional sports H2H.
        """
        # Direct reuse: esports H2H is identical in structure to regular H2H
        return MarketFilter.is_head_to_head(market)


class DrawMarketGroup:
    """Links the three separate Yes/No markets that Polymarket creates for
    soccer (and other draw-eligible sports) into a single logical match.

    Polymarket represents a soccer match as three independent binary markets
    under the same event::

        "Will Team A win on YYYY-MM-DD?"   → Yes/No
        "Will Team B win on YYYY-MM-DD?"   → Yes/No
        "Will Team A vs. Team B end in a draw?"  → Yes/No

    These markets have *separate* ``conditionId`` values and are not
    formally linked by the API.  ``DrawMarketGroup`` groups them by
    scanning the event's ``markets`` list and exposes unified helpers
    for price comparison and implied-probability reconciliation.

    Parameters
    ----------
    event : dict
        A Gamma API event dict with nested ``markets``.
    """

    def __init__(self, event: dict[str, Any]) -> None:
        self.event = event
        self.team_a_market: dict[str, Any] | None = None
        self.team_b_market: dict[str, Any] | None = None
        self.draw_market: dict[str, Any] | None = None
        self.team_a: str = ""
        self.team_b: str = ""
        self._parse(event)

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse(self, event: dict[str, Any]) -> None:
        """Identify team-A-win, team-B-win, and draw markets within an event."""
        markets = event.get("markets", [])
        win_markets: list[dict[str, Any]] = []
        draw_market: dict[str, Any] | None = None

        for mkt in markets:
            q = mkt.get("question", "").lower()
            outcomes = parse_json_field(mkt.get("outcomes", []))

            # Must be binary Yes/No
            if not isinstance(outcomes, list) or len(outcomes) != 2:
                continue
            oset = {o.strip().lower() for o in outcomes}
            if oset != {"yes", "no"}:
                continue

            if "draw" in q:
                draw_market = mkt
            elif "win" in q or "beat" in q:
                win_markets.append(mkt)

        self.draw_market = draw_market

        if len(win_markets) == 2:
            self.team_a_market = win_markets[0]
            self.team_b_market = win_markets[1]
            self.team_a = self._extract_team_name(win_markets[0])
            self.team_b = self._extract_team_name(win_markets[1])

    @staticmethod
    def _extract_team_name(market: dict[str, Any]) -> str:
        """Extract team name from "Will <team> win on …?" question."""
        q = market.get("question", "")
        # Pattern: "Will <team> win on YYYY-MM-DD?"
        # or      "Will <team> beat <other>?"
        import re
        # Try "Will X win on ..."
        m = re.match(r"Will\s+(.+?)\s+win\b", q, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # Try "Will X beat Y?"
        m = re.match(r"Will\s+(.+?)\s+beat\b", q, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return q

    # ── Public API ────────────────────────────────────────────────────

    @property
    def is_complete(self) -> bool:
        """True if all three markets (team A win, team B win, draw) are found."""
        return all([self.team_a_market, self.team_b_market, self.draw_market])

    @property
    def teams(self) -> tuple[str, str]:
        """Return ``(team_a, team_b)`` names."""
        return (self.team_a, self.team_b)

    def yes_token_ids(self) -> dict[str, str]:
        """Return a mapping ``{role: token_id}`` for the Yes token of each market.

        Keys are ``"team_a"``, ``"team_b"``, ``"draw"``.
        """
        result: dict[str, str] = {}
        for role, mkt in [("team_a", self.team_a_market),
                          ("team_b", self.team_b_market),
                          ("draw", self.draw_market)]:
            if mkt is None:
                continue
            tokens = parse_json_field(mkt.get("clobTokenIds") or mkt.get("tokens", []))
            outcomes = parse_json_field(mkt.get("outcomes", []))
            if isinstance(tokens, list) and tokens and isinstance(outcomes, list):
                # Find the "Yes" token index
                for i, o in enumerate(outcomes):
                    if o.strip().lower() == "yes" and i < len(tokens):
                        tid = tokens[i] if isinstance(tokens[i], str) else str(tokens[i])
                        result[role] = tid
                        break
        return result

    def implied_probabilities(self, midpoints: dict[str, float]) -> dict[str, float]:
        """Given midpoint prices for each role, compute implied probabilities.

        Parameters
        ----------
        midpoints : dict
            E.g. ``{"team_a": 0.45, "team_b": 0.30, "draw": 0.28}``

        Returns
        -------
        dict
            Normalized probabilities that sum to ~1.0, plus ``"overround"``
            showing the raw total (indicates market efficiency).
        """
        raw_total = sum(midpoints.values())
        normed = {k: v / raw_total if raw_total > 0 else 0.0 for k, v in midpoints.items()}
        normed["overround"] = raw_total
        return normed

    def condition_ids(self) -> dict[str, str]:
        """Return ``{role: condition_id}`` for each sub-market."""
        result: dict[str, str] = {}
        for role, mkt in [("team_a", self.team_a_market),
                          ("team_b", self.team_b_market),
                          ("draw", self.draw_market)]:
            if mkt:
                cid = mkt.get("conditionId") or mkt.get("condition_id", "")
                if cid:
                    result[role] = cid
        return result

    def __repr__(self) -> str:
        status = "complete" if self.is_complete else "partial"
        return f"DrawMarketGroup({self.team_a} vs {self.team_b}, {status})"


def group_draw_markets(events: list[dict[str, Any]]) -> list[DrawMarketGroup]:
    """Scan events and return groups for all soccer-style draw matches.

    Only events that produce a *complete* group (all 3 markets found) are
    included.
    """
    groups: list[DrawMarketGroup] = []
    for ev in events:
        if not MarketFilter.is_soccer_event(ev):
            continue
        grp = DrawMarketGroup(ev)
        if grp.is_complete:
            groups.append(grp)
    return groups


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


def detect_sport(title: str, tags: list[Any] | None = None, slug: str | None = None) -> str:
    """Detect the sport from event tags, slug, or title keywords.

    Returns an uppercase sport name (``"NBA"``, ``"SOCCER"``, ``"CS2"``, etc.)
    or ``"UNKNOWN"`` if undetectable.

    Parameters
    ----------
    title : str
        Event title.
    tags : list, optional
        Gamma API tags.
    slug : str, optional
        Polymarket tag slug (e.g. "epl", "cbb").
    """
    # --- Slug-based detection (most reliable) ---
    if slug:
        slug_lower = slug.lower()
        slug_sport_map: dict[str, str] = {
            # US sports
            "nba": "NBA", "nfl": "NFL", "mlb": "MLB", "nhl": "NHL",
            "cbb": "NCAAM", "cwbb": "NCAAW", "cfb": "NCAAF",
            # Soccer
            "epl": "SOCCER", "laliga": "SOCCER", "bundesliga": "SOCCER",
            "ligue-1": "SOCCER", "mls": "SOCCER", "ucl": "SOCCER",
            "uel": "SOCCER", "sea": "SOCCER", "bra": "SOCCER", "bra2": "SOCCER",
            "chi1": "SOCCER", "col1": "SOCCER", "mex": "SOCCER", "per1": "SOCCER",
            "jap": "SOCCER", "kor": "SOCCER", "csl": "SOCCER", "ere": "SOCCER",
            "por": "SOCCER", "tur": "SOCCER", "nor": "SOCCER", "den": "SOCCER",
            "spl": "SOCCER", "rou1": "SOCCER", "cze1": "SOCCER", "egy1": "SOCCER",
            "mar1": "SOCCER", "sud": "SOCCER", "ssc": "SOCCER", "cdr": "SOCCER",
            "cde": "SOCCER", "dfb": "SOCCER", "itc": "SOCCER", "acn": "SOCCER",
            "afc-wc": "SOCCER", "caf": "SOCCER", "concacaf": "SOCCER",
            "conmebol": "SOCCER", "crint": "SOCCER", "cehl": "SOCCER",
            "dehl": "SOCCER", "fifa-friendlies": "SOCCER", "ja2": "SOCCER",
            "lib": "SOCCER", "ucol": "SOCCER", "uef-qualifiers": "SOCCER",
            "ruprem": "SOCCER", "rueuchamp": "SOCCER", "rusixnat": "SOCCER",
            "rusrp": "SOCCER", "rutopft": "SOCCER", "ruurc": "SOCCER",
            "aus": "SOCCER",
            # Hockey
            "ahl": "HOCKEY", "khl": "HOCKEY", "shl": "HOCKEY",
            # International basketball
            "bkarg": "BASKETBALL", "bkcba": "BASKETBALL", "bkcl": "BASKETBALL",
            "bkfr1": "BASKETBALL", "bkkbl": "BASKETBALL", "bkligend": "BASKETBALL",
            "bknbl": "BASKETBALL", "bkseriea": "BASKETBALL",
            # Combat
            "mwoh": "MMA", "wwoh": "MMA", "wbc": "BOXING",
            # Lacrosse
            "pll": "LACROSSE", "wll": "LACROSSE",
            # Tennis
            "atp": "TENNIS", "wta": "TENNIS", "wtt-mens-singles": "TENNIS",
            # Cricket
            "cricbbl": "CRICKET", "criccsat20w": "CRICKET", "crichkt20w": "CRICKET",
            "cricipl": "CRICKET", "criclcl": "CRICKET", "cricpakt20cup": "CRICKET",
            "cricps": "CRICKET", "cricpsl": "CRICKET", "cricss": "CRICKET",
            "crict20lpl": "CRICKET", "cricthunderbolt": "CRICKET", "cricwncl": "CRICKET",
            # Esports
            "counter-strike": "CS2", "call-of-duty": "COD", "dota-2": "DOTA2",
            "league-of-legends": "LOL", "mobile-legends-bang-bang": "MOBILE_LEGENDS",
            "overwatch": "OVERWATCH", "rainbow-six-siege": "RAINBOW_SIX",
            "rocket-league": "ROCKET_LEAGUE", "starcraft-2": "STARCRAFT",
            "valorant": "VALORANT",
            # Other
            "golf": "GOLF",
        }
        if slug_lower in slug_sport_map:
            return slug_sport_map[slug_lower]

    # --- Tag-based detection ---
    if tags:
        tag_labels = [
            t.get("label", "").lower() if isinstance(t, dict) else str(t).lower()
            for t in tags
        ]
        tag_str = " ".join(tag_labels)

        # Traditional sports (check longer names first to avoid substring matches)
        for sport in ["wnba", "ncaaf", "ncaam", "ncaaw", "nba", "nfl", "mlb", "nhl",
                       "mma", "ufc", "tennis", "golf", "boxing", "cricket",
                       "rugby", "f1", "lacrosse"]:
            if sport in tag_str:
                return sport.upper()

        # College sports
        if "ncaa" in tag_str or "college-basketball" in tag_str:
            if "football" in tag_str or "college-football" in tag_str:
                return "NCAAF"
            return "NCAAM"

        # Soccer
        soccer_indicators = [
            "soccer", "premier-league", "champions-league", "la-liga",
            "bundesliga", "serie-a", "ligue-1", "mls", "europa-league", "epl",
            "libertadores", "concacaf", "conmebol", "copa-del-rey",
        ]
        if any(ind in tag_str for ind in soccer_indicators):
            return "SOCCER"

        # Esports
        esport_map = {
            "cs2": "CS2", "csgo": "CS2", "counter-strike": "CS2",
            "valorant": "VALORANT",
            "league-of-legends": "LOL", "lol": "LOL",
            "dota": "DOTA2", "dota-2": "DOTA2", "dota2": "DOTA2",
            "overwatch": "OVERWATCH",
            "call-of-duty": "COD", "cod": "COD",
            "mobile-legends": "MOBILE_LEGENDS",
            "rainbow-six": "RAINBOW_SIX",
            "rocket-league": "ROCKET_LEAGUE",
            "starcraft": "STARCRAFT",
        }
        for key, sport in esport_map.items():
            if key in tag_str:
                return sport

        # Hockey leagues
        if any(h in tag_str for h in ["ahl", "khl", "shl", "hockey"]):
            return "HOCKEY"

        # Catch-all esports tag
        if "esports" in tag_str:
            return "ESPORTS"

    # --- Fall back to title-based detection ---
    title_lower = title.lower()
    for sport in ["wnba", "nba", "nfl", "mlb", "nhl", "mma", "ufc", "f1"]:
        if sport in title_lower:
            return sport.upper()

    # Title prefixes for esports
    esport_title_prefixes = {
        "cs:": "CS2", "counter-strike": "CS2", "cs2": "CS2",
        "valorant": "VALORANT",
        "lol:": "LOL", "league of legends": "LOL",
        "dota 2": "DOTA2", "dota2": "DOTA2",
        "overwatch": "OVERWATCH",
        "call of duty": "COD",
        "mobile legends": "MOBILE_LEGENDS",
        "rainbow six": "RAINBOW_SIX",
        "rocket league": "ROCKET_LEAGUE",
        "starcraft": "STARCRAFT",
    }
    for hint, sport in esport_title_prefixes.items():
        if hint in title_lower:
            return sport

    # Soccer title hints
    soccer_title_hints = [
        "premier league", "champions league", "la liga", "bundesliga",
        "serie a", "ligue 1", "eredivisie", "libertadores", "copa del rey",
    ]
    if any(hint in title_lower for hint in soccer_title_hints):
        return "SOCCER"

    # League prefixes in titles (e.g. "AHL: Calgary..." or "KHL: Spartak...")
    league_title_map = {
        "ahl:": "HOCKEY", "khl:": "HOCKEY", "shl:": "HOCKEY",
        "del:": "HOCKEY", "elh:": "HOCKEY",
        "pll:": "LACROSSE",
    }
    for prefix, sport in league_title_map.items():
        if title_lower.startswith(prefix):
            return sport

    return "UNKNOWN"
