# poly-data

Polymarket data client — wraps the Gamma, CLOB, Data, and ESPN APIs into a clean Python interface returning pandas DataFrames or Parquet files. **No trading logic.**

Part of the [Sleuth Capital](https://github.com/sleuthcapital) project.

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

## Quick Start

```python
from poly_data import GammaClient, ClobClient, DataAPIClient, ESPNClient, MarketFilter

# Fetch active sports events
gamma = GammaClient()
events = gamma.fetch_events(active_only=True)

# Filter to head-to-head matchups
for event in events:
    for market in event.get("markets", []):
        if MarketFilter.should_include(market, event):
            print(market["question"])

# Get live price data
clob = ClobClient()
midpoint = clob.fetch_midpoint(token_id="0x1234...")
book = clob.fetch_orderbook(token_id="0x1234...")

# Fetch historical prices as DataFrame
df = clob.fetch_price_history_df(token_id="0x1234...")
df.to_parquet("cache/prices.parquet")

# Fetch trade history (survives market resolution)
data_api = DataAPIClient()
trades_df = data_api.fetch_trades_df(condition_id="0xABCD...")

# Find real game start time via ESPN
espn = ESPNClient()
game_time = espn.find_game_time(
    title="Knicks vs. Hornets",
    anchor_date="2026-03-20",
    sport="nba",
)
```

## API Clients

| Client | API | Purpose |
|---|---|---|
| `GammaClient` | Gamma API | Event metadata, active/resolved events |
| `ClobClient` | CLOB API | Order books, midpoints, price history |
| `DataAPIClient` | Data API | Post-resolution trade history |
| `ESPNClient` | ESPN API | Real game schedules and start times |

## Utilities

| Module | Purpose |
|---|---|
| `MarketFilter` | Classify markets (head-to-head, soccer, props, etc.) |
| `poly_data.markets` | Winner extraction, sport detection, JSON field parsing |
| `poly_data.io` | Save/load JSON, JSONL, Parquet files |

## Design Principles

1. **No trading logic** — this is a pure data library.
2. **Returns DataFrames** — every `fetch_*` method has a `fetch_*_df` variant.
3. **No opinion on storage** — use the I/O helpers or bring your own.
4. **Minimal dependencies** — `requests`, `pandas`, `pyarrow`.
5. **VPN-aware** — optional VPN rotator via `poly_data.set_vpn()` for rate-limit handling.

## License

MIT
