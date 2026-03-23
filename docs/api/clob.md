# ClobClient

::: poly_data.clob

Live prices, order books, and historical price data from the Polymarket CLOB API.

```python
from poly_data import ClobClient
```

---

## Constructor

```python
ClobClient(base_url: str = "https://clob.polymarket.com")
```

---

## Methods

### `fetch_orderbook`

```python
def fetch_orderbook(self, token_id: str) -> dict
```

Fetch the full order book for a token.

**Returns:** `dict` with `bids` and `asks` — each a list of `{"price": str, "size": str}`.

```python
clob = ClobClient()
book = clob.fetch_orderbook("50131916083478714...")

print(f"Bids: {len(book['bids'])}, Asks: {len(book['asks'])}")
print(f"Best bid: {book['bids'][0]}")
```

---

### `fetch_midpoint`

```python
def fetch_midpoint(self, token_id: str) -> float | None
```

Fetch the midpoint price for a token (average of best bid and best ask).

**Returns:** `float` between 0 and 1, or `None` if unavailable.

```python
mid = clob.fetch_midpoint(token_id)
print(f"Implied probability: {mid:.1%}")  # e.g. "62.5%"
```

---

### `fetch_last_trade`

```python
def fetch_last_trade(self, token_id: str) -> dict | None
```

Fetch the most recent trade for a token.

**Returns:** `dict` with `price`, `size`, etc. — or `None`.

---

### `snapshot_market`

```python
def snapshot_market(self, market: dict) -> dict
```

Take a full price snapshot of a market — midpoint, best bid/ask, depth, and last trade for **each outcome**.

| Parameter | Type | Description |
|-----------|------|-------------|
| `market` | `dict` | A Gamma market dict (must contain `clobTokenIds` or `tokens`) |

**Returns:** `dict` keyed by outcome name.

```python
snapshot = clob.snapshot_market(market)
# {
#   "condition_id": "0x...",
#   "Lakers": {"token_id": "...", "midpoint": 0.625, "best_bid": 0.62, ...},
#   "Pistons": {"token_id": "...", "midpoint": 0.375, "best_bid": 0.37, ...},
# }
```

!!! note "Token field name"
    The Gamma API stores token IDs in `clobTokenIds` (a JSON string), not `tokens`. `snapshot_market` handles both fields automatically.

---

### `fetch_price_history`

```python
def fetch_price_history(
    self,
    token_id: str,
    *,
    fidelity: int = 1,
    interval: str = "max",
) -> list[dict]
```

Fetch historical price time series.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token_id` | `str` | — | Token to fetch |
| `fidelity` | `int` | `1` | Resolution (1 = highest) |
| `interval` | `str` | `"max"` | Time range |

**Returns:** `list[dict]` with `t` (UNIX timestamp) and `p` (price) fields.

!!! warning "Purged after resolution"
    CLOB price history is **deleted after a market resolves**. Use [`DataAPIClient`](data-api.md) for post-resolution data.

---

### `fetch_price_history_df`

```python
def fetch_price_history_df(self, token_id: str, **kwargs) -> pd.DataFrame
```

Like `fetch_price_history()` but returns a DataFrame with columns:

- `timestamp` — `datetime64[ns, UTC]`
- `price` — `float64`

```python
df = clob.fetch_price_history_df(token_id)
print(df.head())
```

```
                 timestamp   price
0 2026-03-21 14:22:00+00:00  0.580
1 2026-03-21 15:05:00+00:00  0.592
2 2026-03-21 16:30:00+00:00  0.610
```
