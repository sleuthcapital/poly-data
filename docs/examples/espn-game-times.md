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

```
NBA today: 10 games
  Los Angeles Lakers at Detroit Pistons  —  2026-03-23T23:10:00Z
  Orlando Magic at Indiana Pacers  —  2026-03-23T23:00:00Z
  Miami Heat at Boston Celtics  —  2026-03-24T00:30:00Z
```

## All Supported Sports

ESPN coverage spans 12+ sports and 20+ leagues:

```python
espn = ESPNClient()
today = datetime.now(timezone.utc).strftime("%Y%m%d")

for sport in ["nba", "nfl", "mlb", "nhl", "soccer", "mma",
              "ncaam", "ncaaf", "wnba", "tennis", "golf", "f1"]:
    events = espn.fetch_scoreboard(sport, today)
    print(f"  {sport:8s} → {len(events):3d} events")
```

```
  nba      →  10 events
  nfl      →   0 events
  mlb      →  12 events
  nhl      →   1 events
  soccer   →   0 events
  mma      →   0 events
  ncaam    →   0 events
  ncaaf    →   0 events
  wnba     →   0 events
  tennis   →   1 events
  golf     →   1 events
  f1       →   0 events
```

!!! note "Off-season sports return 0"
    NFL, college basketball, WNBA etc. will return 0 events when out of season. This is expected.

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

The `find_game_time` method matches a Polymarket "X vs. Y" title to an ESPN scoreboard event:

```python
espn = ESPNClient()

# Searches ±3 days around the anchor date
game_time = espn.find_game_time(
    title="Lakers vs. Pistons",
    anchor_date="2026-03-23",
    sport="nba",
    search_days=3,
)
print(f"Game time: {game_time}")
```

```
Game time: 2026-03-23T23:10:00Z
```

### How Matching Works

1. **Extract teams** from the Polymarket title using `extract_poly_teams("Lakers vs. Pistons")` → `["Lakers", "Pistons"]`
2. **Normalize** team names — strip FC/SC/the, lowercase, remove punctuation
3. **Search** ESPN scoreboards ±N days around the anchor date
4. **Fuzzy match** — if both Polymarket team names are substrings of (or contain) ESPN team names, it's a match

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
