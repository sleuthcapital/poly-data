# GammaClient

::: poly_data.gamma

Event metadata from the Polymarket Gamma API — sport tags, market definitions, resolution data.

```python
from poly_data import GammaClient
```

---

## Constructor

```python
GammaClient(
    base_url: str = "https://gamma-api.polymarket.com",
    sport_slugs: list[str] | None = None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | Gamma API URL | Override for testing |
| `sport_slugs` | `list[str]` | `["nba", "nfl", "mlb", "nhl", "soccer", "mma", "tennis"]` | Default sport tags |

---

## Methods

### `fetch_events`

```python
def fetch_events(
    self,
    *,
    active_only: bool = True,
    sport_slugs: list[str] | None = None,
    limit: int = 100,
) -> list[dict]
```

Fetch sports events from Polymarket. Queries each sport slug separately and **deduplicates** results by event ID.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `active_only` | `bool` | `True` | Only return events that haven't closed |
| `sport_slugs` | `list[str]` | Instance default | Override sport tags for this call |
| `limit` | `int` | `100` | Max events per page per slug |

**Returns:** `list[dict]` — Deduplicated event dicts.

```python
gamma = GammaClient()

# All default sports
events = gamma.fetch_events()

# Specific sports
events = gamma.fetch_events(sport_slugs=["nba", "soccer"])

# Include closed events
events = gamma.fetch_events(active_only=False)
```

---

### `fetch_resolved_events`

```python
def fetch_resolved_events(
    self,
    start_date: str,
    end_date: str,
    *,
    sport_slugs: list[str] | None = None,
    limit: int = 100,
) -> list[dict]
```

Fetch resolved (closed) events within a date range.

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | `str` | Inclusive start date `YYYY-MM-DD` |
| `end_date` | `str` | Inclusive end date `YYYY-MM-DD` |
| `sport_slugs` | `list[str]` | Override sport tags |
| `limit` | `int` | Max events per page per slug |

```python
resolved = gamma.fetch_resolved_events(
    "2026-03-01", "2026-03-23",
    sport_slugs=["nba", "mlb"]
)
```

---

### `fetch_events_df`

```python
def fetch_events_df(self, **kwargs) -> pd.DataFrame
```

Like `fetch_events()` but returns a `pandas.DataFrame` via `pd.json_normalize`.

```python
df = gamma.fetch_events_df(active_only=True, sport_slugs=["nba"])
print(df[["id", "title"]].head())
```

---

### `fetch_resolved_events_df`

```python
def fetch_resolved_events_df(
    self, start_date: str, end_date: str, **kwargs
) -> pd.DataFrame
```

Like `fetch_resolved_events()` but returns a DataFrame.

---

## Constants

### `DEFAULT_SPORT_SLUGS`

```python
DEFAULT_SPORT_SLUGS = ["nba", "nfl", "mlb", "nhl", "soccer", "mma", "tennis"]
```

The sport tag slugs used when no custom list is provided.
