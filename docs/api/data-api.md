# DataAPIClient

::: poly_data.data_api

Post-resolution trade history from the Polymarket Data API. Unlike CLOB price history, **trade data survives market resolution**.

```python
from poly_data import DataAPIClient
```

---

## Constructor

```python
DataAPIClient(base_url: str = "https://data-api.polymarket.com")
```

---

## Methods

### `fetch_trades`

```python
def fetch_trades(
    self,
    condition_id: str,
    *,
    max_offset: int = 3000,
    page_size: int = 100,
) -> list[dict]
```

Fetch all trades for a market condition, with automatic pagination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition_id` | `str` | — | Market condition ID |
| `max_offset` | `int` | `3000` | Stop pagination after this offset |
| `page_size` | `int` | `100` | Trades per page |

**Returns:** `list[dict]` — All trades sorted by timestamp ascending.

```python
api = DataAPIClient()
trades = api.fetch_trades("0xf440e623...", max_offset=500)
print(f"{len(trades)} trades")
print(trades[0].keys())
```

```
300 trades
dict_keys(['proxyWallet', 'side', 'asset', 'conditionId', 'size', 'price', 'timestamp', ...])
```

!!! info "API hard limit"
    The Data API enforces a maximum offset of ~3000. For markets with more trades, you'll get the most recent 3000.

---

### `fetch_trades_df`

```python
def fetch_trades_df(self, condition_id: str, **kwargs) -> pd.DataFrame
```

Like `fetch_trades()` but returns a DataFrame. Timestamps are automatically converted to `datetime64[ns, UTC]`.

```python
df = api.fetch_trades_df("0xf440e623...", max_offset=500)
print(df[["timestamp", "price", "size", "side"]].head())
```

```
                     timestamp  price   size side
0 2026-03-20 09:15:22+00:00    0.55  25.00  BUY
1 2026-03-20 09:18:45+00:00    0.56  50.00  BUY
2 2026-03-20 10:02:11+00:00    0.54  30.00  SELL
```

---

## CLOB vs Data API

| Feature | CLOB API | Data API |
|---------|----------|----------|
| Endpoint | `clob.polymarket.com` | `data-api.polymarket.com` |
| Data | Price history (OHLC-like) | Individual trades |
| After resolution | **Purged** | **Preserved** |
| Pagination | No | Yes (offset-based) |
| Use case | Live price charts | Backtesting, volume analysis |
