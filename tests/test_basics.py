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
