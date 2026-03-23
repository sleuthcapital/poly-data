# API Reference

Complete documentation for all poly-data modules and classes.

## Clients

| Class | Module | Purpose |
|-------|--------|---------|
| [`GammaClient`](gamma.md) | `poly_data.gamma` | Event metadata from Polymarket Gamma API |
| [`ClobClient`](clob.md) | `poly_data.clob` | Live prices, order books, price history |
| [`DataAPIClient`](data-api.md) | `poly_data.data_api` | Post-resolution trade history |
| [`ESPNClient`](espn.md) | `poly_data.espn` | Game schedules and team matching |

## Utilities

| Name | Module | Purpose |
|------|--------|---------|
| [`MarketFilter`](markets.md) | `poly_data.markets` | Classify markets — H2H, soccer, esports |
| [`detect_sport`](markets.md#detect_sport) | `poly_data.markets` | Auto-detect sport from tags/title |
| [`extract_winner`](markets.md#extract_winner) | `poly_data.markets` | Get winning outcome from resolved market |
| [I/O Utilities](io.md) | `poly_data.io` | JSON/JSONL/Parquet save & load |
| [HTTP Internals](http.md) | `poly_data._http` | Shared retry logic and rate-limit handling |

## Quick Import

```python
from poly_data import (
    GammaClient,
    ClobClient,
    DataAPIClient,
    ESPNClient,
    MarketFilter,
)
```
