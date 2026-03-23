"""Smoke tests for poly_data clients."""

from poly_data import GammaClient, ClobClient, DataAPIClient, ESPNClient, MarketFilter
from poly_data import DrawMarketGroup, group_draw_markets
from poly_data import SlugInfo, load_registry, coverage_df, active_slugs, slugs_by_sport, coverage_summary
from poly_data.markets import parse_json_field, extract_winner, detect_sport
from poly_data.io import save_json, load_json


def test_imports():
    """All public symbols are importable."""
    assert GammaClient is not None
    assert ClobClient is not None
    assert DataAPIClient is not None
    assert ESPNClient is not None
    assert MarketFilter is not None
    assert SlugInfo is not None
    assert load_registry is not None


def test_parse_json_field_string():
    assert parse_json_field('["a", "b"]') == ["a", "b"]


def test_parse_json_field_list():
    assert parse_json_field(["a", "b"]) == ["a", "b"]


def test_parse_json_field_invalid():
    assert parse_json_field("not json") == "not json"


def test_is_head_to_head_true():
    market = {
        "question": "Knicks vs. Hornets",
        "outcomes": '["Knicks", "Hornets"]',
    }
    assert MarketFilter.is_head_to_head(market) is True


def test_is_head_to_head_prop():
    market = {
        "question": "Will Knicks beat Hornets?",
        "outcomes": '["Yes", "No"]',
    }
    assert MarketFilter.is_head_to_head(market) is False


def test_is_head_to_head_spread():
    market = {
        "question": "Knicks vs. Hornets: Spread -5.5",
        "outcomes": '["Knicks", "Hornets"]',
    }
    assert MarketFilter.is_head_to_head(market) is False


def test_is_head_to_head_partial_game():
    market = {
        "question": "Knicks vs. Hornets: 1H Moneyline",
        "outcomes": '["Knicks", "Hornets"]',
    }
    assert MarketFilter.is_head_to_head(market) is False


def test_is_soccer_match_market():
    market = {
        "question": "Will Arsenal beat Liverpool?",
        "outcomes": '["Yes", "No"]',
    }
    assert MarketFilter.is_soccer_match_market(market) is True


def test_extract_winner():
    market = {
        "outcomes": '["Knicks", "Hornets"]',
        "outcomePrices": '["1", "0"]',
    }
    assert extract_winner(market) == "Knicks"


def test_extract_winner_no_winner():
    market = {
        "outcomes": '["Knicks", "Hornets"]',
        "outcomePrices": '["0.5", "0.5"]',
    }
    assert extract_winner(market) is None


def test_detect_sport_from_tags():
    assert detect_sport("Some game", tags=[{"label": "nba"}]) == "NBA"


def test_detect_sport_soccer():
    assert detect_sport("Some game", tags=[{"label": "premier-league"}]) == "SOCCER"


def test_detect_sport_unknown():
    assert detect_sport("Random event", tags=[]) == "UNKNOWN"


def test_espn_extract_poly_teams():
    teams = ESPNClient.extract_poly_teams("Knicks vs. Hornets")
    assert teams == ["Knicks", "Hornets"]


def test_espn_extract_poly_teams_v():
    teams = ESPNClient.extract_poly_teams("Arsenal v Liverpool")
    assert teams == ["Arsenal", "Liverpool"]


def test_espn_normalize_team():
    assert ESPNClient.normalize_team("FC Barcelona") == "barcelona"
    assert ESPNClient.normalize_team("The Lakers") == "lakers"


def test_json_roundtrip(tmp_path):
    data = {"foo": 1, "bar": [2, 3]}
    path = save_json(data, tmp_path / "test.json")
    loaded = load_json(path)
    assert loaded == data


# --- New: Extended sport detection tests ---

def test_detect_sport_esports_cs2():
    assert detect_sport("CS2 Major", tags=[{"label": "cs2"}]) == "CS2"
    assert detect_sport("CS Major", tags=[{"label": "counter-strike"}]) == "CS2"


def test_detect_sport_esports_valorant():
    assert detect_sport("VCT Match", tags=[{"label": "valorant"}]) == "VALORANT"


def test_detect_sport_esports_lol():
    assert detect_sport("Worlds", tags=[{"label": "league-of-legends"}]) == "LOL"
    assert detect_sport("LCK", tags=[{"label": "lol"}]) == "LOL"


def test_detect_sport_esports_dota():
    assert detect_sport("TI", tags=[{"label": "dota-2"}]) == "DOTA2"


def test_detect_sport_esports_overwatch():
    assert detect_sport("OWL Match", tags=[{"label": "overwatch"}]) == "OVERWATCH"


def test_detect_sport_esports_cod():
    assert detect_sport("CDL Match", tags=[{"label": "call-of-duty"}]) == "COD"


def test_detect_sport_esports_generic():
    assert detect_sport("Some esports event", tags=[{"label": "esports"}]) == "ESPORTS"


def test_detect_sport_f1():
    assert detect_sport("Monaco GP", tags=[{"label": "f1"}]) == "F1"


def test_detect_sport_cricket():
    assert detect_sport("IPL Match", tags=[{"label": "cricket"}]) == "CRICKET"


def test_detect_sport_rugby():
    assert detect_sport("Six Nations", tags=[{"label": "rugby"}]) == "RUGBY"


def test_detect_sport_boxing():
    assert detect_sport("Title Fight", tags=[{"label": "boxing"}]) == "BOXING"


def test_detect_sport_college():
    assert detect_sport("March Madness", tags=[{"label": "ncaa"}, {"label": "college-basketball"}]) == "NCAAM"
    assert detect_sport("Bowl Game", tags=[{"label": "ncaa"}, {"label": "college-football"}]) == "NCAAF"


def test_detect_sport_wnba():
    assert detect_sport("WNBA Finals", tags=[{"label": "wnba"}]) == "WNBA"


def test_detect_sport_tennis():
    assert detect_sport("US Open", tags=[{"label": "tennis"}]) == "TENNIS"


def test_detect_sport_title_fallback_esports():
    assert detect_sport("Counter-Strike 2 Major Finals") == "CS2"
    assert detect_sport("Valorant Champions Tour") == "VALORANT"


# --- New: Esports event detection tests ---

def test_is_esports_event():
    event = {"tags": [{"label": "valorant"}, {"label": "esports"}], "title": "VCT"}
    assert MarketFilter.is_esports_event(event) is True


def test_is_not_esports_event():
    event = {"tags": [{"label": "nba"}], "title": "Lakers vs Celtics"}
    assert MarketFilter.is_esports_event(event) is False


def test_esports_h2h():
    market = {
        "question": "LOUD vs. Paper Rex",
        "outcomes": '["LOUD", "Paper Rex"]',
    }
    assert MarketFilter.is_esports_h2h(market) is True


def test_esports_h2h_prop():
    market = {
        "question": "Will NaVi win the CS2 Major?",
        "outcomes": '["Yes", "No"]',
    }
    assert MarketFilter.is_esports_h2h(market) is False


# --- ESPN sport paths tests ---

from poly_data.espn import ESPN_SPORT_PATHS


def test_espn_paths_all_sports_present():
    """All major sports have entries in ESPN_SPORT_PATHS."""
    for sport in ["nba", "nfl", "mlb", "nhl", "soccer", "mma", "wnba",
                   "ncaam", "ncaaf", "tennis", "golf", "f1", "cricket",
                   "cs2", "valorant", "lol", "dota2", "overwatch", "cod",
                   "rugby", "boxing"]:
        assert sport in ESPN_SPORT_PATHS, f"Missing ESPN path for {sport}"


def test_espn_paths_esports_empty():
    """Esports have no ESPN paths (use PandaScore instead)."""
    for sport in ["cs2", "valorant", "lol", "dota2", "overwatch", "cod"]:
        assert ESPN_SPORT_PATHS[sport] == [], f"{sport} should have empty ESPN paths"


def test_espn_paths_traditional_populated():
    """Traditional sports have at least one ESPN path."""
    for sport in ["nba", "nfl", "mlb", "nhl", "soccer", "mma"]:
        assert len(ESPN_SPORT_PATHS[sport]) > 0, f"{sport} should have ESPN paths"


# --- DrawMarketGroup tests ---

def _make_soccer_event(team_a="Liverpool", team_b="Manchester City"):
    """Build a fake soccer event with 3 separate Yes/No markets."""
    return {
        "title": f"{team_a} vs {team_b}",
        "tags": [{"label": "premier-league"}, {"label": "soccer"}],
        "markets": [
            {
                "question": f"Will {team_a} win on 2026-03-22?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["token_a_yes", "token_a_no"]',
                "conditionId": "0xaaa",
            },
            {
                "question": f"Will {team_b} win on 2026-03-22?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["token_b_yes", "token_b_no"]',
                "conditionId": "0xbbb",
            },
            {
                "question": f"Will {team_a} vs. {team_b} end in a draw?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["token_draw_yes", "token_draw_no"]',
                "conditionId": "0xccc",
            },
        ],
    }


def test_draw_group_complete():
    grp = DrawMarketGroup(_make_soccer_event())
    assert grp.is_complete
    assert grp.team_a == "Liverpool"
    assert grp.team_b == "Manchester City"


def test_draw_group_teams():
    grp = DrawMarketGroup(_make_soccer_event("Arsenal", "Chelsea"))
    assert grp.teams == ("Arsenal", "Chelsea")


def test_draw_group_yes_token_ids():
    grp = DrawMarketGroup(_make_soccer_event())
    tokens = grp.yes_token_ids()
    assert tokens["team_a"] == "token_a_yes"
    assert tokens["team_b"] == "token_b_yes"
    assert tokens["draw"] == "token_draw_yes"


def test_draw_group_condition_ids():
    grp = DrawMarketGroup(_make_soccer_event())
    cids = grp.condition_ids()
    assert cids["team_a"] == "0xaaa"
    assert cids["team_b"] == "0xbbb"
    assert cids["draw"] == "0xccc"


def test_draw_group_implied_probabilities():
    grp = DrawMarketGroup(_make_soccer_event())
    midpoints = {"team_a": 0.45, "team_b": 0.30, "draw": 0.28}
    probs = grp.implied_probabilities(midpoints)
    # Should sum to ~1.0
    assert abs(probs["team_a"] + probs["team_b"] + probs["draw"] - 1.0) < 1e-9
    # Overround should be raw total
    assert abs(probs["overround"] - 1.03) < 1e-9
    # team_a should have highest probability
    assert probs["team_a"] > probs["team_b"]
    assert probs["team_a"] > probs["draw"]


def test_draw_group_implied_probabilities_zero():
    grp = DrawMarketGroup(_make_soccer_event())
    midpoints = {"team_a": 0.0, "team_b": 0.0, "draw": 0.0}
    probs = grp.implied_probabilities(midpoints)
    assert probs["team_a"] == 0.0
    assert probs["overround"] == 0.0


def test_draw_group_incomplete_no_draw():
    event = _make_soccer_event()
    event["markets"] = event["markets"][:2]  # remove draw
    grp = DrawMarketGroup(event)
    assert not grp.is_complete


def test_draw_group_incomplete_single_win():
    event = _make_soccer_event()
    event["markets"] = [event["markets"][0], event["markets"][2]]  # only 1 win + draw
    grp = DrawMarketGroup(event)
    assert not grp.is_complete


def test_draw_group_repr():
    grp = DrawMarketGroup(_make_soccer_event())
    assert "Liverpool" in repr(grp)
    assert "complete" in repr(grp)


def test_draw_group_beat_format():
    """Test parsing 'Will X beat Y?' format."""
    event = {
        "title": "Arsenal vs Chelsea",
        "tags": [{"label": "premier-league"}],
        "markets": [
            {
                "question": "Will Arsenal beat Chelsea?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["t1", "t2"]',
                "conditionId": "0x1",
            },
            {
                "question": "Will Chelsea beat Arsenal?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["t3", "t4"]',
                "conditionId": "0x2",
            },
            {
                "question": "Will Arsenal vs Chelsea end in a draw?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["t5", "t6"]',
                "conditionId": "0x3",
            },
        ],
    }
    grp = DrawMarketGroup(event)
    assert grp.is_complete
    assert grp.team_a == "Arsenal"
    assert grp.team_b == "Chelsea"


def test_group_draw_markets():
    events = [
        _make_soccer_event("Liverpool", "Man City"),
        _make_soccer_event("Arsenal", "Chelsea"),
        # Non-soccer event — should be skipped
        {
            "title": "Lakers vs Celtics",
            "tags": [{"label": "nba"}],
            "markets": [{"question": "Lakers vs. Celtics", "outcomes": '["Lakers", "Celtics"]'}],
        },
    ]
    groups = group_draw_markets(events)
    assert len(groups) == 2
    assert groups[0].team_a == "Liverpool"
    assert groups[1].team_a == "Arsenal"


def test_group_draw_markets_incomplete_skipped():
    """Incomplete groups (missing draw market) should be excluded."""
    event = _make_soccer_event()
    event["markets"] = event["markets"][:2]  # no draw
    groups = group_draw_markets([event])
    assert len(groups) == 0


def test_draw_group_non_binary_outcomes_skipped():
    """Markets with non-binary outcomes should be ignored during parsing."""
    event = {
        "title": "Liverpool vs Man City",
        "tags": [{"label": "soccer"}],
        "markets": [
            {
                "question": "Will Liverpool win on 2026-03-22?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["t1", "t2"]',
                "conditionId": "0x1",
            },
            {
                "question": "Will Man City win on 2026-03-22?",
                "outcomes": '["Liverpool", "Man City", "Draw"]',  # NOT binary
                "clobTokenIds": '["t3", "t4", "t5"]',
                "conditionId": "0x2",
            },
            {
                "question": "Will the match end in a draw?",
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["t6", "t7"]',
                "conditionId": "0x3",
            },
        ],
    }
    grp = DrawMarketGroup(event)
    # Only 1 win market parsed (the non-binary one was skipped), so incomplete
    assert not grp.is_complete


# --- ESPN estimate_game_end tests ---

def test_estimate_game_end_nba():
    event = {"date": "2026-03-23T01:00Z", "competitions": [{"status": {"period": 4}}]}
    end = ESPNClient.estimate_game_end(event, "nba")
    assert end == "2026-03-23T03:30:00Z"  # 2.5 hours


def test_estimate_game_end_nba_overtime():
    event = {"date": "2026-03-23T01:00Z", "competitions": [{"status": {"period": 5}}]}
    end = ESPNClient.estimate_game_end(event, "nba")
    assert end == "2026-03-23T03:40:00Z"  # 2.5h + 10 min OT


def test_estimate_game_end_nfl():
    event = {"date": "2026-09-10T17:00Z", "competitions": [{"status": {"period": 4}}]}
    end = ESPNClient.estimate_game_end(event, "nfl")
    assert end == "2026-09-10T20:30:00Z"  # 3.5 hours


def test_estimate_game_end_soccer():
    event = {"date": "2026-03-22T15:00Z", "competitions": [{"status": {"period": 2}}]}
    end = ESPNClient.estimate_game_end(event, "soccer")
    assert end == "2026-03-22T16:55:00Z"  # 1h 55m


def test_estimate_game_end_no_date():
    event = {"competitions": []}
    end = ESPNClient.estimate_game_end(event, "nba")
    assert end is None


def test_estimate_game_end_unknown_sport():
    event = {"date": "2026-03-23T01:00Z", "competitions": []}
    end = ESPNClient.estimate_game_end(event, "curling")
    assert end == "2026-03-23T03:30:00Z"  # default 150 min


# --- Coverage registry tests ---

from poly_data.coverage import SlugInfo, save_registry, load_registry


def test_slug_info_defaults():
    info = SlugInfo(slug="test", api_tag="test", sport="unknown")
    assert info.status == "unknown"
    assert info.market_type is None
    assert info.event_count == 0
    assert info.earliest_date is None


def test_registry_roundtrip(tmp_path):
    reg = {
        "nba": SlugInfo(
            slug="nba", api_tag="nba", sport="basketball",
            market_type="h2h", status="active",
            earliest_date="2023-12-26", latest_date="2026-03-22",
            event_count=30, sample_title="Lakers vs. Celtics",
        ),
        "laliga": SlugInfo(
            slug="laliga", api_tag="la-liga", sport="soccer",
            market_type="draw", status="active",
            earliest_date="2024-05-31", latest_date="2026-03-22",
            event_count=30, sample_title="Real Madrid vs. Barcelona",
        ),
    }
    path = tmp_path / "coverage.json"
    save_registry(reg, path)
    loaded = load_registry(path)
    assert len(loaded) == 2
    assert loaded["nba"].api_tag == "nba"
    assert loaded["nba"].market_type == "h2h"
    assert loaded["nba"].earliest_date == "2023-12-26"
    assert loaded["laliga"].api_tag == "la-liga"
    assert loaded["laliga"].sport == "soccer"


def test_load_registry_missing_file(tmp_path):
    reg = load_registry(tmp_path / "nonexistent.json")
    assert reg == {}


def test_active_slugs_from_file():
    """The shipped coverage_data.json should have active slugs."""
    slugs = active_slugs()
    assert len(slugs) > 50  # we know 87 are active
    assert "nba" in slugs
    assert "epl" in slugs


def test_coverage_df_columns():
    df = coverage_df()
    assert not df.empty
    for col in ["slug", "api_tag", "sport", "market_type", "status",
                 "earliest_date", "latest_date", "event_count"]:
        assert col in df.columns, f"Missing column: {col}"


def test_coverage_df_has_dates():
    """Active slugs should have earliest/latest dates."""
    df = coverage_df()
    active = df[df["status"] == "active"]
    assert active["earliest_date"].notna().sum() > 50


def test_slugs_by_sport():
    soccer = slugs_by_sport("soccer")
    assert len(soccer) > 20
    assert all(s.sport == "soccer" for s in soccer)


def test_coverage_summary_string():
    s = coverage_summary()
    assert "Coverage Registry" in s
    assert "soccer" in s
    assert "Backtest date range" in s
