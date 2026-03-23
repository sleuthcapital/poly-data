# HTTP Internals

::: poly_data._http

Low-level shared HTTP client with retry logic, rate-limit handling, and optional VPN rotation.

!!! info "You usually don't need this module directly"
    All API clients use `get_json` internally. Import this only if you need custom HTTP calls or VPN integration.

```python
from poly_data._http import get_json, set_vpn, GAMMA_API, CLOB_API, DATA_API, ESPN_BASE
```

---

## `get_json`

```python
def get_json(
    url: str,
    params: dict | None = None,
    retries: int = 3,
    timeout: float = 15,
) -> dict | list
```

GET a URL and parse the JSON response, with automatic retry and rate-limit handling.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | Full URL to fetch |
| `params` | `dict` | `None` | Query parameters |
| `retries` | `int` | `3` | Number of retry attempts |
| `timeout` | `float` | `15` | Request timeout in seconds |

**Behavior:**

1. If a VPN rotator is registered, calls `maybe_rotate()` before each request
2. On HTTP 429 (rate limited), calls `vpn.on_rate_limit()` and backs off exponentially
3. On any request failure, retries with exponential backoff (`2^attempt` seconds)

```python
from poly_data._http import get_json, GAMMA_API

data = get_json(f"{GAMMA_API}/events", params={"tag_slug": "nba", "limit": 10})
```

---

## `set_vpn`

```python
def set_vpn(vpn: VPNRotator) -> None
```

Register a VPN rotator for all HTTP calls. The rotator must implement the `VPNRotator` protocol.

---

## `VPNRotator` Protocol

```python
class VPNRotator(Protocol):
    def maybe_rotate(self) -> None: ...
    def on_rate_limit(self) -> None: ...
```

Implement this protocol in your trading engine to auto-rotate VPN connections on rate limits.

---

## Base URL Constants

| Constant | URL | Auth |
|----------|-----|------|
| `GAMMA_API` | `https://gamma-api.polymarket.com` | None |
| `CLOB_API` | `https://clob.polymarket.com` | None |
| `DATA_API` | `https://data-api.polymarket.com` | None |
| `ESPN_BASE` | `https://site.api.espn.com/apis/site/v2/sports` | None |
