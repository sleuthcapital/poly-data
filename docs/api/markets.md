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
