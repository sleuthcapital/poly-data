# poly-data

**Polymarket sports data client** — clean Python wrappers for the Gamma, CLOB, Data, and ESPN APIs, returning pandas DataFrames or Parquet files.

<div class="grid cards" markdown>

- :material-database: **Gamma API** — Event metadata, sport tags, market definitions
- :material-chart-line: **CLOB API** — Live order books, midpoints, price history
- :material-swap-horizontal: **Data API** — Post-resolution trade history (survives market close)
- :material-scoreboard: **ESPN API** — Real game start times, team matching across 22 sports

</div>

---

## Quick Example

```python
from poly_data import GammaClient, ClobClient, MarketFilter
from poly_data.markets import detect_sport

# Fetch all active NBA events
gamma = GammaClient()
events = gamma.fetch_events(active_only=True, sport_slugs=["nba"])

# Filter to head-to-head markets only
for event in events:
    for market in event.get("markets", []):
        if MarketFilter.is_head_to_head(market):
            sport = detect_sport(event.get("title", ""), tags=event.get("tags"))
            print(f"[{sport}] {market['question']}")
```

```
[NBA] Los Angeles Lakers vs Detroit Pistons
[NBA] Orlando Magic vs Indiana Pacers
[NBA] Miami Heat vs Boston Celtics
...
```

## Architecture

```
poly_data/
├── _http.py      # Shared HTTP with retry + rate-limit handling
├── gamma.py      # GammaClient — event metadata
├── clob.py       # ClobClient — live prices & order books
├── data_api.py   # DataAPIClient — trade history
├── espn.py       # ESPNClient — game schedules & team matching
├── markets.py    # MarketFilter, detect_sport, extract_winner
└── io.py         # JSON/JSONL/Parquet save & load helpers
```

## Key Features

- **No trading logic** — pure data access, clean separation of concerns
- **DataFrame-first** — every client has `_df` methods returning pandas DataFrames
- **Retry + rate-limit** — automatic 429 backoff with optional VPN rotation
- **22 sports** — NBA, NFL, MLB, NHL, soccer (8 leagues), MMA, tennis, golf, F1, cricket, plus 6 esports via PandaScore
- **Market intelligence** — filter H2H matchups, detect props/spreads/partials, extract winners

## Installation

```bash
pip install poly-data
```

Or from source:

```bash
git clone https://github.com/sleuthcapital/poly-data.git
cd poly-data
pip install -e ".[dev]"
```
