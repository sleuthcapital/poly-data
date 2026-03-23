# Getting Started

## Installation

=== "pip"

    ```bash
    pip install poly-data
    ```

=== "From source"

    ```bash
    git clone https://github.com/sleuthcapital/poly-data.git
    cd poly-data
    pip install -e ".[dev]"
    ```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | ≥ 2.28 | HTTP client |
| `pandas` | ≥ 2.0 | DataFrame output |
| `pyarrow` | ≥ 14.0 | Parquet I/O |

## Your First Query

Fetch active NBA events from Polymarket's Gamma API:

```python
from poly_data import GammaClient

gamma = GammaClient()
events = gamma.fetch_events(active_only=True, sport_slugs=["nba"])

print(f"Found {len(events)} NBA events")
for ev in events[:3]:
    print(f"  • {ev['title']}")
```

```
Found 76 NBA events
  • NBA: Los Angeles Lakers vs Detroit Pistons
  • NBA: Orlando Magic vs Indiana Pacers
  • NBA: Miami Heat vs Boston Celtics
```

## Get a DataFrame

Every client has `_df` variants that return pandas DataFrames:

```python
df = gamma.fetch_events_df(active_only=True, sport_slugs=["nba"])

print(df[["id", "title", "slug"]].head())
```

```
                    id                                     title              slug
0  12345678-abcd-...  NBA: Los Angeles Lakers vs Detroit Pist...  nba-lakers-vs...
1  23456789-bcde-...  NBA: Orlando Magic vs Indiana Pacers        nba-magic-vs-...
2  34567890-cdef-...  NBA: Miami Heat vs Boston Celtics            nba-heat-vs-c...
```

## Filter Head-to-Head Markets

Polymarket has many market types — props, spreads, over/unders, partials. Use `MarketFilter` to keep only the head-to-head matchups:

```python
from poly_data import GammaClient, MarketFilter

gamma = GammaClient()
events = gamma.fetch_events(active_only=True, sport_slugs=["nba"])

h2h_markets = []
for event in events:
    for market in event.get("markets", []):
        if MarketFilter.is_head_to_head(market):
            h2h_markets.append(market)

print(f"{len(h2h_markets)} H2H markets out of all NBA markets")
```

## Detect Sports Automatically

```python
from poly_data.markets import detect_sport

# From tags (preferred)
detect_sport("", tags=[{"label": "nba"}])      # → "NBA"
detect_sport("", tags=[{"label": "valorant"}])  # → "VALORANT"

# Fall back to title keywords
detect_sport("Lakers vs Celtics — NBA")         # → "NBA"
detect_sport("CS2: NAVI vs FaZe")               # → "CS2"
```

## Next Steps

- **[Examples](examples/index.md)** — Full code samples with plots
- **[API Reference](api/index.md)** — Complete method documentation
- **[Sports Coverage](sports-coverage.md)** — All 22 supported sports and data sources
