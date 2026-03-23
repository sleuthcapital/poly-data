"""Smoke tests for poly_data clients."""

from poly_data import GammaClient, ClobClient, DataAPIClient, ESPNClient, MarketFilter
from poly_data.markets import parse_json_field, extract_winner, detect_sport
from poly_data.io import save_json, load_json


def test_imports():
    """All public symbols are importable."""
    assert GammaClient is not None
    assert ClobClient is not None
    assert DataAPIClient is not None
    assert ESPNClient is not None
    assert MarketFilter is not None


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
