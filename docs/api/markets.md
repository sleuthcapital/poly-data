# MarketFilter

::: poly_data.markets

Market classification, sport detection, and winner extraction — pure logic, no API calls.

```python
from poly_data import MarketFilter
from poly_data.markets import detect_sport, extract_winner, parse_json_field
```

---

## MarketFilter

### `is_head_to_head` (static)

```python
@staticmethod
def is_head_to_head(market: dict) -> bool
```

Returns `True` for a head-to-head game market (`"Team A vs Team B"` with exactly 2 team-name outcomes).

**Excluded:**

- Props (Yes/No outcomes)
- Spreads (`"Spread:"` in question)
- Over/Under
- Partial-game (1H, 2Q, 1st period, etc.)

```python
# ✅ Passes
MarketFilter.is_head_to_head({
    "question": "Lakers vs. Pistons",
    "outcomes": '["Lakers", "Pistons"]',
})  # → True

# ❌ Filtered out
MarketFilter.is_head_to_head({
    "question": "Will LeBron score 30+?",
    "outcomes": '["Yes", "No"]',
})  # → False (prop)

MarketFilter.is_head_to_head({
    "question": "1H: Lakers vs Pistons",
    "outcomes": '["Lakers", "Pistons"]',
})  # → False (partial game)
```

---

### `is_soccer_event` (static)

```python
@staticmethod
def is_soccer_event(event: dict) -> bool
```

Returns `True` if event tags or title contain soccer indicators (Premier League, La Liga, MLS, etc.).

---

### `is_soccer_match_market` (static)

```python
@staticmethod
def is_soccer_match_market(market: dict) -> bool
```

Returns `True` for soccer beat/draw Yes/No markets.

```python
MarketFilter.is_soccer_match_market({
    "question": "Will Liverpool beat Manchester City?",
    "outcomes": '["Yes", "No"]',
})  # → True
```

---

### `is_esports_event` (static)

```python
@staticmethod
def is_esports_event(event: dict) -> bool
```

Returns `True` if event is an esports match (CS2, Valorant, LoL, Dota 2, Overwatch, CoD).

---

### `is_esports_h2h` (static)

```python
@staticmethod
def is_esports_h2h(market: dict) -> bool
```

Returns `True` for esports H2H team matchups. Same structure as traditional sports H2H.

---

### `should_include` (classmethod)

```python
@classmethod
def should_include(cls, market: dict, event: dict | None = None) -> bool
```

One-stop filter — returns `True` if a market should be included for trading/analysis:

- Head-to-head markets (any sport)
- Soccer beat/draw markets (when event is soccer)
- Esports H2H markets (when event is esports)

```python
MarketFilter.should_include(market, event)
```

---

## `detect_sport` { #detect_sport }

```python
def detect_sport(title: str, tags: list | None = None) -> str
```

Auto-detect sport from event tags or title. Returns uppercase sport name or `"UNKNOWN"`.

| Priority | Source | Example |
|----------|--------|---------|
| 1st | Tag labels | `[{"label": "nba"}]` → `"NBA"` |
| 2nd | Title keywords | `"Lakers vs Celtics — NBA"` → `"NBA"` |
| Fallback | — | `"UNKNOWN"` |

**Supported sports:** NBA, NFL, MLB, NHL, WNBA, NCAAM, NCAAF, MMA, TENNIS, GOLF, F1, CRICKET, RUGBY, BOXING, SOCCER, CS2, VALORANT, LOL, DOTA2, OVERWATCH, COD, ESPORTS

```python
detect_sport("", tags=[{"label": "premier-league"}])  # → "SOCCER"
detect_sport("", tags=[{"label": "csgo"}])             # → "CS2"
detect_sport("CS2: NAVI vs FaZe")                      # → "CS2"
```

---

## `extract_winner` { #extract_winner }

```python
def extract_winner(market: dict) -> str | None
```

Extract the winning outcome from a resolved market by checking `outcomePrices` — the winner has a payout of `1.0`.

```python
extract_winner({
    "outcomes": '["Lakers", "Pistons"]',
    "outcomePrices": '[1, 0]',
})  # → "Lakers"

extract_winner({
    "outcomes": '["Lakers", "Pistons"]',
    "outcomePrices": '[0.62, 0.38]',
})  # → None (not resolved)
```

---

## `parse_json_field`

```python
def parse_json_field(raw: Any) -> Any
```

Parse a Gamma API field that may be a JSON string or already Python data.

```python
parse_json_field('["Yes", "No"]')  # → ["Yes", "No"]
parse_json_field(["Yes", "No"])     # → ["Yes", "No"] (passthrough)
```

---

## DrawMarketGroup { #DrawMarketGroup }

```python
class DrawMarketGroup(event: dict)
```

Links the three separate Yes/No markets Polymarket creates for soccer matches into a single logical match.

Soccer events contain:

- `"Will Team A win on YYYY-MM-DD?"` → Yes/No
- `"Will Team B win on YYYY-MM-DD?"` → Yes/No
- `"Will Team A vs. Team B end in a draw?"` → Yes/No

Each has a different `conditionId` and `clobTokenIds`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_complete` | `bool` | `True` if all 3 sub-markets found |
| `teams` | `tuple[str, str]` | `(team_a, team_b)` names |
| `team_a` | `str` | First team name |
| `team_b` | `str` | Second team name |

### `yes_token_ids`

```python
def yes_token_ids() -> dict[str, str]
```

Returns `{"team_a": "...", "team_b": "...", "draw": "..."}` — the CLOB token ID for the "Yes" outcome of each sub-market.

### `implied_probabilities`

```python
def implied_probabilities(midpoints: dict[str, float]) -> dict[str, float]
```

Given raw midpoint prices (e.g. `{"team_a": 0.45, "team_b": 0.30, "draw": 0.28}`), returns normalized probabilities that sum to ~1.0, plus an `"overround"` entry showing the raw total.

### `condition_ids`

```python
def condition_ids() -> dict[str, str]
```

Returns `{"team_a": "0x...", "team_b": "0x...", "draw": "0x..."}`.

```python
from poly_data import DrawMarketGroup

grp = DrawMarketGroup(event)
if grp.is_complete:
    print(grp.teams)           # ('Liverpool', 'Man City')
    print(grp.yes_token_ids()) # {'team_a': '…', 'team_b': '…', 'draw': '…'}
```

---

## `group_draw_markets` { #group_draw_markets }

```python
def group_draw_markets(events: list[dict]) -> list[DrawMarketGroup]
```

Scan a list of Gamma events and return `DrawMarketGroup` instances for all soccer events that have a complete set of 3 sub-markets.

```python
from poly_data import GammaClient, group_draw_markets

events = GammaClient().fetch_events(active_only=True, sport_slugs=["soccer"])
groups = group_draw_markets(events)
print(f"{len(groups)} complete draw-market groups")
for g in groups[:3]:
    print(f"  {g}")
```
