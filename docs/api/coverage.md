# Coverage Registry

::: poly_data.coverage

The coverage module tracks which Polymarket sport slugs have backtesting data,
including date ranges, market types, and event counts.

## Quick Start

```python
from poly_data import load_registry, coverage_df, active_slugs, coverage_summary

# All active slugs (87 currently)
slugs = active_slugs()

# Lookup specific slug details
reg = load_registry()
nba = reg["nba"]
print(nba.earliest_date)   # 2023-12-26
print(nba.latest_date)     # 2026-06-22
print(nba.market_type)     # h2h
print(nba.event_count)     # 30

# Pandas DataFrame for analysis
df = coverage_df()
soccer = df[df["sport"] == "soccer"]

# Human-readable summary
print(coverage_summary())
```

## Data Model

### `SlugInfo`

A dataclass representing metadata for a single Polymarket sport slug.

| Field | Type | Description |
|-------|------|-------------|
| `slug` | `str` | Frontend URL slug (e.g. `"laliga"`) |
| `api_tag` | `str` | Resolved Gamma API `tag_slug` (e.g. `"la-liga"`) |
| `sport` | `str` | High-level sport category (`soccer`, `basketball`, …) |
| `market_type` | `str \| None` | `"h2h"` (2-outcome), `"draw"` (3-way), or `None` |
| `status` | `str` | `active` · `no_history` · `no_events` · `active_only` · `unknown` |
| `espn_sport` | `str \| None` | ESPN sport key for game-time matching |
| `earliest_date` | `str \| None` | ISO date of earliest resolved event |
| `latest_date` | `str \| None` | ISO date of most recent resolved event |
| `event_count` | `int` | Total resolved events found |
| `sample_title` | `str \| None` | Example event title |
| `updated_at` | `str \| None` | ISO timestamp of last refresh |

## Functions

### `load_registry(path=None) → dict[str, SlugInfo]`

Load the coverage registry from disk. Uses the bundled `coverage_data.json` by default.

```python
reg = load_registry()
reg["epl"].earliest_date  # '2023-12-12'
```

### `save_registry(registry, path=None) → Path`

Persist a registry to disk as JSON. Used by `scripts/update_coverage.py`.

### `coverage_df() → DataFrame`

Return the full registry as a pandas DataFrame, sorted by sport then slug.

```python
df = coverage_df()
df.columns
# ['slug', 'api_tag', 'sport', 'market_type', 'status',
#  'espn_sport', 'earliest_date', 'latest_date', 'event_count',
#  'sample_title', 'updated_at']
```

### `active_slugs() → list[str]`

Return a sorted list of slugs with confirmed backtesting data.

### `slugs_by_sport(sport) → list[SlugInfo]`

Return all slug entries for a given sport category.

```python
from poly_data import slugs_by_sport
rugby = slugs_by_sport("rugby")
# [SlugInfo(slug='rusixnat', ...), SlugInfo(slug='rusrp', ...), ...]
```

### `coverage_summary() → str`

Return a human-readable multi-line summary string.

## Updating the Registry

```bash
# Refresh all slugs from the Gamma API
python scripts/update_coverage.py

# Only scan specific slugs
python scripts/update_coverage.py --only nba,epl

# Only scan one sport
python scripts/update_coverage.py --sport soccer

# Dry run (print, don't save)
python scripts/update_coverage.py --dry-run
```

The update script writes to `src/poly_data/coverage_data.json`, which ships with the package.
