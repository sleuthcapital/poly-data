"""Live integration tests — hit real APIs.

Every test in this file is marked ``@pytest.mark.live``.
Run them explicitly::

    pytest tests/test_live.py -v              # run all live tests
    pytest -m live -v                          # same via marker
    pytest -m 'not live'                       # skip them in CI

API keys are loaded from ``../.env`` via python-dotenv.
Tests that need a key are skipped when it is missing.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env from the repo root (one level up from tests/)
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_dotenv_path)

PANDASCORE_KEY = os.getenv("PANDASCORE_API_KEY", "")
ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
needs_pandascore = pytest.mark.skipif(not PANDASCORE_KEY, reason="PANDASCORE_API_KEY not set")
needs_odds_api = pytest.mark.skipif(not ODDS_API_KEY, reason="THE_ODDS_API_KEY not set")

pytestmark = pytest.mark.live  # applies to every test in this module


# ===================================================================
#  Polymarket Gamma API
# ===================================================================

class TestGammaLive:
    """Tests against the real Gamma API."""

    def test_fetch_active_events(self):
        from poly_data import GammaClient

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True, sport_slugs=["nba", "nfl"])
        assert isinstance(events, list)
        # There should be at least *some* NBA/NFL events (props, futures, or H2H)
        # — but allow 0 in deep off-season; mainly check no crash.
        for ev in events[:5]:
            assert "id" in ev
            assert "title" in ev or "question" in ev or "slug" in ev

    def test_fetch_events_df(self):
        from poly_data import GammaClient

        gamma = GammaClient()
        df = gamma.fetch_events_df(active_only=True, sport_slugs=["soccer"])
        assert hasattr(df, "columns")  # is a DataFrame
        # If there are rows, check basic columns
        if len(df) > 0:
            assert "id" in df.columns

    def test_fetch_resolved_events(self):
        from poly_data import GammaClient

        gamma = GammaClient()
        # Look back 30 days — should find *something* resolved
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        resolved = gamma.fetch_resolved_events(start, end, sport_slugs=["nba", "mlb", "soccer"])
        assert isinstance(resolved, list)
        # Off-season may yield 0, that's OK — we test the plumbing

    def test_fetch_events_esports(self):
        from poly_data import GammaClient

        gamma = GammaClient()
        events = gamma.fetch_events(
            active_only=True,
            sport_slugs=["valorant", "cs2", "lol", "dota-2", "esports"],
        )
        assert isinstance(events, list)
        # Log counts for visibility
        print(f"[Gamma] esports events: {len(events)}")

    def test_event_has_markets(self):
        """At least some events should contain nested market data."""
        from poly_data import GammaClient

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True, sport_slugs=["nba", "nfl", "soccer"])
        events_with_markets = [
            e for e in events if e.get("markets") and len(e["markets"]) > 0
        ]
        # It's possible all are empty, but log it
        print(f"[Gamma] {len(events)} events, {len(events_with_markets)} with markets")

    def test_detect_sport_on_live_events(self):
        """detect_sport should return something useful on real data."""
        from poly_data import GammaClient
        from poly_data.markets import detect_sport

        gamma = GammaClient()
        events = gamma.fetch_events(
            active_only=True,
            sport_slugs=["nba", "soccer", "valorant", "f1"],
        )
        detected = {}
        for ev in events:
            sport = detect_sport(ev.get("title", ""), tags=ev.get("tags"))
            detected.setdefault(sport, 0)
            detected[sport] += 1
        print(f"[Gamma] sport detection: {detected}")
        # At least one should not be UNKNOWN
        assert "UNKNOWN" not in detected or len(detected) > 1 or len(events) == 0


# ===================================================================
#  Polymarket CLOB API
# ===================================================================

class TestClobLive:
    """Tests against the real CLOB API.

    These need an active market token_id. We discover one dynamically
    from the Gamma API.
    """

    @pytest.fixture(scope="class")
    def active_token_id(self):
        """Find a token_id from a currently-active head-to-head market."""
        from poly_data import GammaClient
        from poly_data.markets import MarketFilter, parse_json_field

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True)
        for ev in events:
            for mkt in ev.get("markets", []):
                if MarketFilter.is_head_to_head(mkt):
                    # Gamma API stores token IDs in 'clobTokenIds' (JSON string), not 'tokens'
                    raw = mkt.get("clobTokenIds") or mkt.get("tokens", [])
                    tokens = parse_json_field(raw)
                    if tokens:
                        tid = tokens[0].get("token_id") if isinstance(tokens[0], dict) else str(tokens[0])
                        if tid:
                            return tid
        pytest.skip("No active H2H market with tokens found")

    def test_fetch_midpoint(self, active_token_id):
        from poly_data import ClobClient

        clob = ClobClient()
        mid = clob.fetch_midpoint(active_token_id)
        # midpoint should be a float between 0 and 1 (or slightly outside)
        assert mid is None or (isinstance(mid, float) and 0 <= mid <= 1.05)
        print(f"[CLOB] midpoint for {active_token_id[:12]}… = {mid}")

    def test_fetch_orderbook(self, active_token_id):
        from poly_data import ClobClient

        clob = ClobClient()
        book = clob.fetch_orderbook(active_token_id)
        assert isinstance(book, dict)
        # book should have bids and/or asks
        assert "bids" in book or "asks" in book
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        print(f"[CLOB] orderbook {active_token_id[:12]}…: {len(bids)} bids, {len(asks)} asks")

    def test_fetch_price_history(self, active_token_id):
        from poly_data import ClobClient

        clob = ClobClient()
        history = clob.fetch_price_history(active_token_id)
        assert isinstance(history, list)
        if history:
            point = history[0]
            assert "t" in point or "timestamp" in point
            assert "p" in point or "price" in point
        print(f"[CLOB] price history for {active_token_id[:12]}…: {len(history)} points")

    def test_fetch_price_history_df(self, active_token_id):
        from poly_data import ClobClient

        clob = ClobClient()
        df = clob.fetch_price_history_df(active_token_id)
        assert hasattr(df, "columns")
        if len(df) > 0:
            assert "timestamp" in df.columns
            assert "price" in df.columns
            assert df["price"].dtype == float or df["price"].dtype == "float64"
        print(f"[CLOB] price_history_df: {len(df)} rows")

    def test_fetch_last_trade(self, active_token_id):
        from poly_data import ClobClient

        clob = ClobClient()
        trade = clob.fetch_last_trade(active_token_id)
        # may be None if no trades yet
        if trade is not None:
            assert isinstance(trade, dict)
            assert "price" in trade
        print(f"[CLOB] last trade: {trade}")

    def test_snapshot_market(self):
        """snapshot_market assembles midpoint + book + last trade for all tokens."""
        from poly_data import GammaClient, ClobClient
        from poly_data.markets import MarketFilter

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True)
        market = None
        for ev in events:
            for mkt in ev.get("markets", []):
                if MarketFilter.is_head_to_head(mkt):
                    market = mkt
                    break
            if market:
                break
        if not market:
            pytest.skip("No active H2H market found for snapshot")

        clob = ClobClient()
        snap = clob.snapshot_market(market)
        assert isinstance(snap, dict)
        assert "condition_id" in snap
        print(f"[CLOB] snapshot: {snap}")


# ===================================================================
#  Polymarket Data API
# ===================================================================

class TestDataAPILive:
    """Tests against the real Data API (trade history)."""

    @pytest.fixture(scope="class")
    def active_condition_id(self):
        """Find a condition_id from a currently-active market."""
        from poly_data import GammaClient
        from poly_data.markets import MarketFilter

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True)
        for ev in events:
            for mkt in ev.get("markets", []):
                cid = mkt.get("conditionId") or mkt.get("condition_id")
                if cid and MarketFilter.is_head_to_head(mkt):
                    return cid
        pytest.skip("No active market with conditionId found")

    def test_fetch_trades(self, active_condition_id):
        from poly_data import DataAPIClient

        api = DataAPIClient()
        trades = api.fetch_trades(active_condition_id, max_offset=200)
        assert isinstance(trades, list)
        if trades:
            assert "price" in trades[0] or "p" in trades[0]
        print(f"[DataAPI] trades for {active_condition_id[:12]}…: {len(trades)}")

    def test_fetch_trades_df(self, active_condition_id):
        from poly_data import DataAPIClient

        api = DataAPIClient()
        df = api.fetch_trades_df(active_condition_id, max_offset=200)
        assert hasattr(df, "columns")
        print(f"[DataAPI] trades_df: {len(df)} rows, cols={list(df.columns)[:6]}")


# ===================================================================
#  ESPN API
# ===================================================================

class TestESPNLive:
    """Tests against the real ESPN Scoreboard API (no auth needed)."""

    def test_fetch_scoreboard_nba(self):
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        events = espn.fetch_scoreboard("nba", today)
        assert isinstance(events, list)
        print(f"[ESPN] NBA today: {len(events)} events")

    def test_fetch_scoreboard_soccer(self):
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        events = espn.fetch_scoreboard("soccer", today)
        assert isinstance(events, list)
        # Soccer has many leagues — total could be high
        print(f"[ESPN] Soccer today: {len(events)} events")

    @pytest.mark.parametrize(
        "sport",
        ["nba", "nfl", "mlb", "nhl", "soccer", "mma", "ncaam", "ncaaf",
         "wnba", "tennis", "golf", "f1"],
    )
    def test_fetch_scoreboard_all_sports(self, sport):
        """Every sport with ESPN paths should not crash, even if 0 events."""
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        events = espn.fetch_scoreboard(sport, today)
        assert isinstance(events, list)
        print(f"[ESPN] {sport}: {len(events)} events")

    def test_fetch_scoreboard_df(self):
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        df = espn.fetch_scoreboard_df("mlb", today)
        assert hasattr(df, "columns")
        print(f"[ESPN] MLB df: {len(df)} rows")

    def test_find_game_time_historical(self):
        """Try to match a real past NBA game against ESPN archives."""
        from poly_data import ESPNClient

        espn = ESPNClient()
        # Use a recent date range — pick a date likely to have had games
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        # We don't know team names, so just verify the method runs without error
        result = espn.find_game_time(
            "FakeTeam vs. FakeOpponent",
            yesterday,
            "nba",
            search_days=1,
        )
        # Should be None since teams are fake
        assert result is None

    def test_extract_teams_from_live_events(self):
        """extract_teams should return team names from real ESPN data."""
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        events = espn.fetch_scoreboard("mlb", today)
        for ev in events[:3]:
            teams = espn.extract_teams(ev)
            assert isinstance(teams, set)
            # Active games should have team names
            if ev.get("competitions"):
                assert len(teams) > 0, f"No teams extracted from: {ev.get('name', 'unknown')}"
            print(f"  [ESPN] teams: {teams}")

    def test_espn_no_paths_returns_empty(self):
        """Sports with no ESPN paths should return empty list, not crash."""
        from poly_data import ESPNClient

        espn = ESPNClient()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        for sport in ["cs2", "valorant", "lol", "dota2", "boxing", "rugby"]:
            events = espn.fetch_scoreboard(sport, today)
            assert events == [], f"{sport} should return empty list"


# ===================================================================
#  PandaScore API (esports)
# ===================================================================

class TestPandaScoreLive:
    """Tests against the real PandaScore API.

    Requires PANDASCORE_API_KEY in .env.
    PandaScore isn't in poly-data yet as a client module, so these tests
    hit the API directly via requests to validate the endpoints work.
    This will inform the PandaScoreClient implementation.
    """

    @needs_pandascore
    @pytest.mark.parametrize("game", ["csgo", "valorant", "lol", "dota2", "ow", "codmw"])
    def test_upcoming_matches(self, game):
        """Fetch upcoming matches for each esport — validates endpoint + auth."""
        import requests

        resp = requests.get(
            f"https://api.pandascore.co/{game}/matches/upcoming",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 5},
            timeout=15,
        )
        assert resp.status_code == 200, f"{game} upcoming: HTTP {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PandaScore] {game} upcoming: {len(data)} matches")
        if data:
            match = data[0]
            assert "begin_at" in match or "scheduled_at" in match
            assert "opponents" in match or "name" in match

    @needs_pandascore
    def test_running_matches(self):
        """Check running (live) matches across all esports."""
        import requests

        resp = requests.get(
            "https://api.pandascore.co/matches/running",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 10},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PandaScore] running matches: {len(data)}")

    @needs_pandascore
    def test_past_matches_cs2(self):
        """Fetch recent past CS2 matches — should always have results."""
        import requests

        resp = requests.get(
            "https://api.pandascore.co/csgo/matches/past",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 5},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected recent CS2 past matches"
        match = data[0]
        assert "winner" in match or "results" in match or "status" in match
        print(f"[PandaScore] CS2 past: {data[0].get('name', '?')}, status={data[0].get('status')}")

    @needs_pandascore
    def test_match_has_timing_info(self):
        """Upcoming matches should include scheduling info we need for game timing."""
        import requests

        resp = requests.get(
            "https://api.pandascore.co/valorant/matches/upcoming",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 3},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        for match in data:
            # At least one of these should be present for scheduling
            has_time = match.get("begin_at") or match.get("scheduled_at") or match.get("original_scheduled_at")
            print(f"  [PandaScore] {match.get('name', '?')}: begin_at={match.get('begin_at')}")
            if has_time:
                return  # pass — found at least one with timing
        # If all matches lack timing, it's a soft failure
        if data:
            pytest.skip("No upcoming valorant matches have begin_at set")

    @needs_pandascore
    def test_match_has_opponent_teams(self):
        """Matches should include opponent team names for matching."""
        import requests

        resp = requests.get(
            "https://api.pandascore.co/csgo/matches/upcoming",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 5, "filter[status]": "not_started"},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        for match in data:
            opponents = match.get("opponents", [])
            if len(opponents) >= 2:
                team_a = opponents[0].get("opponent", {}).get("name", "")
                team_b = opponents[1].get("opponent", {}).get("name", "")
                print(f"  [PandaScore] {team_a} vs {team_b}")
                assert team_a and team_b
                return
        if data:
            print(f"  [PandaScore] matches found but no 2-opponent match: {[m.get('name') for m in data]}")

    @needs_pandascore
    def test_videogames_list(self):
        """List all videogames PandaScore covers — useful for building ROUTING."""
        import requests

        resp = requests.get(
            "https://api.pandascore.co/videogames",
            headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
            params={"per_page": 50},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        slugs = [g.get("slug") for g in data]
        print(f"[PandaScore] videogames: {slugs}")
        # Should include our key games
        for expected in ["cs-go", "valorant", "league-of-legends", "dota-2", "ow"]:
            assert expected in slugs, f"Missing {expected} in PandaScore videogames"


# ===================================================================
#  the-odds-api
# ===================================================================

class TestOddsAPILive:
    """Tests against the-odds-api (500 free req/mo).

    Requires THE_ODDS_API_KEY in .env.
    Like PandaScore, this isn't a poly-data module yet — these tests
    validate the API and inform the OddsAPIClient implementation.
    """

    @needs_odds_api
    def test_list_sports(self):
        """List all available sports — validates auth and coverage."""
        import requests

        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports",
            params={"apiKey": ODDS_API_KEY},
            timeout=15,
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        keys = [s["key"] for s in data if not s.get("has_outrights")]
        print(f"[OddsAPI] {len(data)} sports, non-outright keys sample: {keys[:10]}")
        # Check critical sports are listed (some may only appear as outrights
        # in off-season, e.g. americanfootball_nfl → americanfootball_nfl_super_bowl_winner).
        sport_keys = {s["key"] for s in data}
        for prefix in ["basketball_nba", "americanfootball_nfl", "baseball_mlb", "icehockey_nhl"]:
            has_match = any(k.startswith(prefix) for k in sport_keys)
            assert has_match, f"No sport key starting with '{prefix}' found in {sorted(sport_keys)}"
        # Remaining requests header
        remaining = resp.headers.get("x-requests-remaining", "?")
        print(f"[OddsAPI] requests remaining: {remaining}")

    @needs_odds_api
    def test_fetch_nba_odds(self):
        """Fetch current NBA odds — validates event structure + commence_time."""
        import requests

        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h",
            },
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[OddsAPI] NBA odds: {len(data)} events")
        if data:
            event = data[0]
            assert "commence_time" in event
            assert "home_team" in event
            assert "away_team" in event
            print(f"  First: {event['away_team']} @ {event['home_team']} at {event['commence_time']}")

    @needs_odds_api
    @pytest.mark.parametrize(
        "sport_key",
        [
            "soccer_epl",
            "mma_mixed_martial_arts",
            "cricket_ipl",
            "rugbyleague_nrl",
        ],
    )
    def test_fetch_events_various_sports(self, sport_key):
        """Validate the-odds-api covers sports ESPN doesn't."""
        import requests

        resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events",
            params={"apiKey": ODDS_API_KEY},
            timeout=15,
        )
        # Some sports may not be in-season → 200 with empty list is OK
        assert resp.status_code in (200, 404), f"HTTP {resp.status_code} for {sport_key}"
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            print(f"[OddsAPI] {sport_key}: {len(data)} events")
            if data:
                assert "commence_time" in data[0]

    @needs_odds_api
    def test_commence_time_is_iso(self):
        """commence_time should be ISO 8601 — useful for game timing fallback."""
        import requests
        from datetime import datetime as dt

        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/events",
            params={"apiKey": ODDS_API_KEY},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        for event in data[:3]:
            ct = event.get("commence_time", "")
            # Should be parseable ISO 8601
            parsed = dt.fromisoformat(ct.replace("Z", "+00:00"))
            assert parsed is not None
            print(f"  [OddsAPI] {event.get('home_team')} — commence: {ct}")


# ===================================================================
#  Cross-API: MarketFilter on live Gamma data
# ===================================================================

class TestMarketFilterLive:
    """Run MarketFilter logic on real Gamma data."""

    def test_filter_head_to_head_markets(self):
        from poly_data import GammaClient
        from poly_data.markets import MarketFilter

        gamma = GammaClient()
        events = gamma.fetch_events(active_only=True)
        h2h_count = 0
        total_markets = 0
        for ev in events:
            for mkt in ev.get("markets", []):
                total_markets += 1
                if MarketFilter.is_head_to_head(mkt):
                    h2h_count += 1
        print(f"[Filter] {h2h_count}/{total_markets} markets are H2H across {len(events)} events")

    def test_detect_sports_distribution(self):
        """Run detect_sport on all live events and show distribution."""
        from poly_data import GammaClient
        from poly_data.markets import detect_sport

        gamma = GammaClient()
        events = gamma.fetch_events(
            active_only=True,
            sport_slugs=[
                "nba", "nfl", "mlb", "nhl", "soccer", "mma",
                "valorant", "cs2", "lol", "f1", "cricket",
                "tennis", "golf", "boxing", "rugby",
            ],
        )
        distribution: dict[str, int] = {}
        for ev in events:
            sport = detect_sport(ev.get("title", ""), tags=ev.get("tags"))
            distribution.setdefault(sport, 0)
            distribution[sport] += 1
        sorted_dist = dict(sorted(distribution.items(), key=lambda x: -x[1]))
        print(f"[Filter] sport distribution ({len(events)} events): {sorted_dist}")

    def test_esports_h2h_on_live_data(self):
        """Check if any current esports events have H2H markets."""
        from poly_data import GammaClient
        from poly_data.markets import MarketFilter

        gamma = GammaClient()
        events = gamma.fetch_events(
            active_only=True,
            sport_slugs=["valorant", "cs2", "lol", "overwatch", "esports"],
        )
        esport_h2h = []
        for ev in events:
            if MarketFilter.is_esports_event(ev):
                for mkt in ev.get("markets", []):
                    if MarketFilter.is_head_to_head(mkt):
                        esport_h2h.append(
                            f"{ev.get('title', '?')} → {mkt.get('question', '?')}"
                        )
        print(f"[Filter] esports H2H markets: {len(esport_h2h)}")
        for m in esport_h2h[:5]:
            print(f"  {m}")
