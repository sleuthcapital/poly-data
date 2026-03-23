# Sports Coverage

poly-data covers **22 sports** across 4 data sources. Here's the complete coverage matrix.

## Coverage Matrix

| Sport | Gamma API | ESPN | PandaScore | the-odds-api |
|-------|:---------:|:----:|:----------:|:------------:|
| **NBA** | ✅ | ✅ | — | ✅ |
| **NFL** | ✅ | ✅ | — | ✅ |
| **MLB** | ✅ | ✅ | — | ✅ |
| **NHL** | ✅ | ✅ | — | ✅ |
| **Soccer** (8 leagues) | ✅ | ✅ | — | ✅ |
| **MMA/UFC** | ✅ | ✅ | — | ✅ |
| **Tennis** | ✅ | ✅ | — | ✅ |
| **Golf** | ✅ | ✅ | — | — |
| **F1** | ✅ | ✅ | — | — |
| **Cricket** | ✅ | ✅ | — | ✅ |
| **NCAAM** | ✅ | ✅ | — | ✅ |
| **NCAAF** | ✅ | ✅ | — | ✅ |
| **WNBA** | ✅ | ✅ | — | ✅ |
| **Boxing** | ✅ | — | — | ✅ |
| **Rugby** | ✅ | — | — | ✅ |
| **CS2** | ✅ | — | ✅ | — |
| **Valorant** | ✅ | — | ✅ | — |
| **League of Legends** | ✅ | — | ✅ | — |
| **Dota 2** | ✅ | — | ✅ | — |
| **Overwatch** | ✅ | — | ✅ | — |
| **Call of Duty** | ✅ | — | ✅ | — |

## Data Sources

### Polymarket Gamma API (no auth)

The primary source for event metadata, market definitions, and resolution data. Every sport on Polymarket is discoverable through Gamma.

```python
from poly_data import GammaClient

gamma = GammaClient()
events = gamma.fetch_events(active_only=True)
# Returns events across all sports with tags, markets, and outcomes
```

### Polymarket CLOB API (no auth)

Live order books, midpoints, and price history for active markets. Data is **purged after resolution**.

```python
from poly_data import ClobClient

clob = ClobClient()
mid = clob.fetch_midpoint(token_id)  # Implied probability
book = clob.fetch_orderbook(token_id)  # Full depth
```

### Polymarket Data API (no auth)

Trade history that **survives market resolution** — crucial for backtesting.

```python
from poly_data import DataAPIClient

api = DataAPIClient()
trades = api.fetch_trades(condition_id)  # Up to 3000 trades
```

### ESPN Scoreboard API (no auth)

Real game start times and team rosters. Covers 12+ traditional sports with 20+ leagues.

```python
from poly_data import ESPNClient

espn = ESPNClient()
events = espn.fetch_scoreboard("nba", "20260323")
```

### PandaScore API (requires API key)

Esports match schedules, results, and timing data. Covers CS2, Valorant, LoL, Dota 2, Overwatch, CoD.

!!! note "Not yet a poly-data client"
    PandaScore integration is planned. Currently, our live tests validate the API directly:

```python
import requests

resp = requests.get(
    "https://api.pandascore.co/csgo/matches/upcoming",
    headers={"Authorization": f"Bearer {PANDASCORE_KEY}"},
    params={"per_page": 5},
)
matches = resp.json()
for m in matches:
    print(f"  {m['name']} — {m.get('begin_at', 'TBD')}")
```

### the-odds-api (requires API key, 500 free req/mo)

Pre-game odds and commence times from multiple bookmakers. Covers 40+ sports.

!!! note "Not yet a poly-data client"
    the-odds-api integration is planned. Currently validated via live tests:

```python
import requests

resp = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_nba/odds",
    params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h"},
)
events = resp.json()
for ev in events[:3]:
    print(f"  {ev['home_team']} vs {ev['away_team']} — {ev['commence_time']}")
```

## Game Time Resolution Tiers

When matching Polymarket events to real game times, the data sources form a priority chain:

| Tier | Source | Latency | Coverage |
|------|--------|---------|----------|
| **1** | ESPN Scoreboard | ~Real-time | Traditional sports |
| **2** | PandaScore | ~Minutes | Esports |
| **3** | the-odds-api | ~Hours | All sports via `commence_time` |
| **4** | Gamma API description | Static | Parse text for date hints |
| **5** | First trade timestamp | After the fact | Universal fallback |

## Soccer League Coverage

ESPN queries 8 soccer leagues simultaneously:

| League | ESPN Path | Region |
|--------|-----------|--------|
| Premier League | `soccer/eng.1` | England |
| La Liga | `soccer/esp.1` | Spain |
| Bundesliga | `soccer/ger.1` | Germany |
| Serie A | `soccer/ita.1` | Italy |
| Ligue 1 | `soccer/fra.1` | France |
| MLS | `soccer/usa.1` | USA |
| Champions League | `soccer/uefa.champions` | Europe |
| Europa League | `soccer/uefa.europa` | Europe |

## PandaScore Game Coverage

Validated videogames from the PandaScore API:

```
mlbb, starcraft-brood-war, starcraft-2, lol-wild-rift, kog,
valorant, fifa, r6-siege, cod-mw, rl, pubg, ow, dota-2,
cs-go, league-of-legends
```
