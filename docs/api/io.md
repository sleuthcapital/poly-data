# I/O Utilities

::: poly_data.io

Convenience helpers for saving and loading data as JSON, JSONL, or Parquet.

```python
from poly_data.io import (
    save_json, load_json,
    append_jsonl, load_jsonl,
    save_parquet, load_parquet,
    load_games_from_dir,
    load_trades_from_dir,
)
```

---

## JSON

### `save_json`

```python
def save_json(data: Any, path: str | Path) -> Path
```

Write data as pretty-printed JSON. Creates parent directories automatically.

```python
from poly_data.io import save_json

save_json(events, "data/events/nba_2026-03-23.json")
```

---

### `load_json`

```python
def load_json(path: str | Path) -> Any
```

Read and parse a JSON file.

```python
events = load_json("data/events/nba_2026-03-23.json")
```

---

## JSONL (line-delimited JSON)

### `append_jsonl`

```python
def append_jsonl(record: dict, path: str | Path) -> Path
```

Append a single JSON record to a JSONL file. Creates the file and parent dirs if needed.

```python
from poly_data.io import append_jsonl

for trade in trades:
    append_jsonl(trade, "data/trades/nba.jsonl")
```

---

### `load_jsonl`

```python
def load_jsonl(path: str | Path) -> list[dict]
```

Read all records from a JSONL file.

```python
records = load_jsonl("data/trades/nba.jsonl")
```

---

## Parquet

### `save_parquet`

```python
def save_parquet(df: pd.DataFrame, path: str | Path) -> Path
```

Write a DataFrame to Parquet. Creates parent directories automatically.

```python
from poly_data.io import save_parquet

df = gamma.fetch_events_df(active_only=True)
save_parquet(df, "data/events.parquet")
```

---

### `load_parquet`

```python
def load_parquet(path: str | Path) -> pd.DataFrame
```

Read a Parquet file into a DataFrame.

```python
df = load_parquet("data/events.parquet")
```

---

## Batch Loaders

### `load_games_from_dir`

```python
def load_games_from_dir(directory: str | Path) -> list[dict]
```

Load all `*.json` game files from a directory. Files are sorted by name.

```python
games = load_games_from_dir("data/games/")
```

---

### `load_trades_from_dir`

```python
def load_trades_from_dir(directory: str | Path) -> dict[str, list[dict]]
```

Load all `*_trades.json` files from a directory. Returns a dict keyed by condition ID (extracted from filename).

```python
trades_by_market = load_trades_from_dir("data/trades/")
# {"0xabc123": [...], "0xdef456": [...]}
```
