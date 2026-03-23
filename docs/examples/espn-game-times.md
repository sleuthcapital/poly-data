# ESPN Game Times

The ESPN client maps Polymarket events to real game schedules, giving you actual start times for matches.

## Fetch Today's Scoreboard

```python
from datetime import datetime, timezone
from poly_data import ESPNClient

espn = ESPNClient()
today = datetime.now(timezone.utc).strftime("%Y%m%d")

# NBA games today
events = espn.fetch_scoreboard("nba", today)
print(f"NBA today: {len(events)} games")

for ev in events[:3]:
    print(f"  {ev['name']}  —  {ev.get('date', 'TBD')}")
```

## Soccer: Current Matchday

ESPN soccer uses **matchday-based windows** rather than exact calendar dates.
Pass `None` as the date to get the current matchday across all leagues:

```python
espn = ESPNClient()

# Current matchday (no date param — gets whatever ESPN considers "today's" games)
soccer_events = espn.fetch_scoreboard("soccer")  # date_str=None
print(f"Soccer current matchday: {len(soccer_events)} games")

for ev in soccer_events[:5]:
    print(f"  {ev['name']}  —  {ev.get('date', 'TBD')}")
```

```
Soccer current matchday: 15 games
  Sunderland at Newcastle United  —  2026-03-22T12:00Z
  West Ham United at Aston Villa  —  2026-03-22T14:15Z
  Rayo Vallecano at Barcelona     —  2026-03-22T20:00Z
  Eintracht Frankfurt at Mainz    —  2026-03-22T14:30Z
  ...
```

!!! warning "Date parameter quirks for soccer"
    Passing a specific date like `"20260323"` may return **0 events** for soccer
    even when games are scheduled — because ESPN soccer scoreboards are organized
    by matchday, not UTC calendar date.  Always also query with `date_str=None`
    for the current round's games.

## All Supported Sports

ESPN coverage spans 12+ sports and 20+ leagues:

```python
espn = ESPNClient()
today = datetime.now(timezone.utc).strftime("%Y%m%d")

for sport in ["nba", "nfl", "mlb", "nhl", "soccer", "mma",
              "ncaam", "ncaaf", "wnba", "tennis", "golf", "f1"]:
    # Use explicit date for most sports, but default for soccer
    if sport == "soccer":
        events = espn.fetch_scoreboard(sport)  # current matchday
    else:
        events = espn.fetch_scoreboard(sport, today)
    print(f"  {sport:8s} → {len(events):3d} events")
```

!!! note "Off-season sports return 0"
    NFL, college basketball, WNBA etc. will return 0 events when out of season.
    This is expected.

## Soccer Leagues

Soccer fetches from 8 leagues simultaneously:

```python
from poly_data.espn import ESPN_SPORT_PATHS

print("Soccer leagues queried:")
for path in ESPN_SPORT_PATHS["soccer"]:
    print(f"  • {path}")
```

```
Soccer leagues queried:
  • soccer/eng.1       (EPL)
  • soccer/esp.1       (La Liga)
  • soccer/ger.1       (Bundesliga)
  • soccer/ita.1       (Serie A)
  • soccer/fra.1       (Ligue 1)
  • soccer/usa.1       (MLS)
  • soccer/uefa.champions (UCL)
  • soccer/uefa.europa    (UEL)
```

## Extract Team Names

```python
espn = ESPNClient()
today = datetime.now(timezone.utc).strftime("%Y%m%d")
events = espn.fetch_scoreboard("mlb", today)

for ev in events[:3]:
    teams = espn.extract_teams(ev)
    print(f"  {teams}")
```

```
  {'phi', 'tb', 'phillies', 'tampa bay rays', 'rays', 'philadelphia phillies'}
  {'minnesota twins', 'min', 'twins', 'bos', 'red sox', 'boston red sox'}
  {'atlanta braves', 'atl', 'pirates', 'braves', 'pit', 'pittsburgh pirates'}
```

## Match Polymarket Titles to ESPN

The `find_game_time` method matches a Polymarket "X vs. Y" title to an ESPN scoreboard event.
For soccer, it also checks the current matchday automatically:

```python
espn = ESPNClient()

# Traditional sport — searches ±3 days around the anchor date
game_time = espn.find_game_time(
    title="Lakers vs. Pistons",
    anchor_date="2026-03-23",
    sport="nba",
    search_days=3,
)
print(f"Game time: {game_time}")

# Soccer — also checks the current matchday (no date param)
game_time = espn.find_game_time(
    title="Newcastle United vs. Sunderland",
    anchor_date="2026-03-22",
    sport="soccer",
    search_days=3,
)
print(f"Soccer game time: {game_time}")
```

### How Matching Works

1. **Extract teams** from the Polymarket title using `extract_poly_teams("Lakers vs. Pistons")` → `["Lakers", "Pistons"]`
2. **Normalize** team names — strip FC/SC/the, lowercase, remove punctuation
3. For **soccer**, first check the current matchday (ESPN default, no date param)
4. **Search** ESPN scoreboards ±N days around the anchor date
5. **Fuzzy match** — if both Polymarket team names are substrings of (or contain) ESPN team names, it's a match

```python
# Team normalization
print(ESPNClient.normalize_team("FC Barcelona"))  # → "barcelona"
print(ESPNClient.normalize_team("The Lakers"))     # → "lakers"

# Team extraction from Polymarket titles
print(ESPNClient.extract_poly_teams("Knicks vs. Hornets"))
# → ["Knicks", "Hornets"]

print(ESPNClient.extract_poly_teams("FC Barcelona v Real Madrid"))
# → ["FC Barcelona", "Real Madrid"]
```

## Scoreboard as DataFrame

```python
df = espn.fetch_scoreboard_df("mlb", today)
print(f"{len(df)} rows × {len(df.columns)} columns")
print(df[["name", "date", "status.type.name"]].head())
```

## Caching

ESPN results are cached in memory per `(sport, date)` key. Repeated calls for the same sport+date return instantly:

```python
# First call — hits ESPN API
events1 = espn.fetch_scoreboard("nba", "20260323")

# Second call — returns from cache (no HTTP request)
events2 = espn.fetch_scoreboard("nba", "20260323")

assert events1 is events2  # Same object
```
