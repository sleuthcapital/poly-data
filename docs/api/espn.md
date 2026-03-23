# ESPNClient

::: poly_data.espn

Game schedules, start times, and team matching from the ESPN Scoreboard API. No API key required.

```python
from poly_data import ESPNClient
```

---

## Constructor

```python
ESPNClient(base_url: str = "https://site.api.espn.com/apis/site/v2/sports")
```

---

## Methods

### `fetch_scoreboard`

```python
def fetch_scoreboard(self, sport: str, date_str: str | None = None) -> list[dict]
```

Fetch ESPN scoreboard events for a sport on a date.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sport` | `str` | — | Sport key — `"nba"`, `"soccer"`, `"f1"`, etc. |
| `date_str` | `str \| None` | `None` | Date in `YYYYMMDD` format, or `None` for current matchday |

**Returns:** `list[dict]` — ESPN event objects. Results are cached in memory.

```python
espn = ESPNClient()

# Specific date
events = espn.fetch_scoreboard("nba", "20260323")
print(f"{len(events)} NBA games")

# Current matchday (important for soccer)
soccer = espn.fetch_scoreboard("soccer")  # date_str=None
print(f"{len(soccer)} soccer games")
```

!!! warning "Soccer date handling"
    ESPN soccer scoreboards use **matchday windows**, not UTC dates.
    Passing a specific date may return 0 events even when games are on.
    Use `date_str=None` to get the current round's games.

!!! note "Soccer queries 8 leagues"
    Passing `sport="soccer"` queries EPL, La Liga, Bundesliga, Serie A, Ligue 1, MLS, UCL, and UEL simultaneously.

!!! info "Esports return empty"
    Sports with no ESPN paths (`cs2`, `valorant`, `lol`, etc.) return `[]`. Use PandaScore for esports.

---

### `find_game_time`

```python
def find_game_time(
    self,
    title: str,
    anchor_date: str,
    sport: str,
    *,
    search_days: int = 3,
) -> str | None
```

Match a Polymarket "X vs. Y" title to an ESPN game and return the start time.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | — | Polymarket event title |
| `anchor_date` | `str` | — | Anchor date `YYYY-MM-DD` |
| `sport` | `str` | — | Sport key |
| `search_days` | `int` | `3` | Search ±N days around anchor |

**Returns:** ISO datetime string, or `None` if no match.

```python
time = espn.find_game_time(
    "Lakers vs. Pistons",
    "2026-03-23",
    "nba"
)
print(time)  # "2026-03-23T23:10:00Z"
```

---

### `extract_teams` (static)

```python
@staticmethod
def extract_teams(event: dict) -> set[str]
```

Extract all lowercased team names from an ESPN event dict. Returns abbreviations, short names, and full names.

```python
teams = ESPNClient.extract_teams(espn_event)
# {'phi', 'tb', 'phillies', 'tampa bay rays', 'rays', 'philadelphia phillies'}
```

---

### `normalize_team` (static)

```python
@staticmethod
def normalize_team(name: str) -> str
```

Normalize a team name for fuzzy matching — removes `FC`, `SC`, `the`, punctuation, extra whitespace.

```python
ESPNClient.normalize_team("FC Barcelona")  # → "barcelona"
ESPNClient.normalize_team("The Lakers")    # → "lakers"
```

---

### `extract_poly_teams` (static)

```python
@staticmethod
def extract_poly_teams(title: str) -> list[str]
```

Extract team names from a Polymarket "X vs. Y" title.

```python
ESPNClient.extract_poly_teams("Knicks vs. Hornets")     # → ["Knicks", "Hornets"]
ESPNClient.extract_poly_teams("Barcelona v Real Madrid") # → ["Barcelona", "Real Madrid"]
```

---

### `teams_match` (classmethod)

```python
@classmethod
def teams_match(cls, poly_teams: list[str], espn_teams: set[str]) -> bool
```

Check if Polymarket team names match ESPN team names with fuzzy substring matching. Returns `True` if both teams match.

---

### `fetch_scoreboard_df`

```python
def fetch_scoreboard_df(self, sport: str, date_str: str) -> pd.DataFrame
```

Like `fetch_scoreboard()` but returns a flattened DataFrame via `pd.json_normalize`.

---

## Constants

### `ESPN_SPORT_PATHS`

Maps sport keys to ESPN API paths. 22 sports with coverage info:

```python
from poly_data.espn import ESPN_SPORT_PATHS

# Traditional sports
ESPN_SPORT_PATHS["nba"]     # → ["basketball/nba"]
ESPN_SPORT_PATHS["soccer"]  # → ["soccer/eng.1", "soccer/esp.1", ...]  (8 leagues)
ESPN_SPORT_PATHS["f1"]      # → ["racing/f1"]

# Esports — empty (use PandaScore)
ESPN_SPORT_PATHS["cs2"]       # → []
ESPN_SPORT_PATHS["valorant"]  # → []
```

Full mapping:

| Sport Key | ESPN Paths | Coverage |
|-----------|------------|----------|
| `nba` | `basketball/nba` | Year-round |
| `nfl` | `football/nfl` | Seasonal (Sep-Feb) |
| `mlb` | `baseball/mlb` | Seasonal (Mar-Oct) |
| `nhl` | `hockey/nhl` | Seasonal (Oct-Jun) |
| `soccer` | 8 leagues | Year-round |
| `mma` | `mma/ufc` | Event-based |
| `ncaam` | `basketball/mens-college-basketball` | Seasonal |
| `ncaaf` | `football/college-football` | Seasonal |
| `wnba` | `basketball/wnba` | Seasonal |
| `tennis` | `tennis/atp` | Year-round |
| `golf` | `golf/pga` | Year-round |
| `f1` | `racing/f1` | Seasonal (Mar-Dec) |
| `cricket` | `cricket/icc` | Seasonal |
| `cs2`–`cod` | — | Use PandaScore |
| `rugby`, `boxing` | — | Planned |
