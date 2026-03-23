"""Low-level HTTP helpers with retry, rate-limit handling, and optional VPN rotation."""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


# ---------------------------------------------------------------------------
# VPN rotator protocol (optional dependency — kept outside poly-data)
# ---------------------------------------------------------------------------
class VPNRotator(Protocol):
    """Minimal interface for a VPN rotator (e.g. from trading-engine)."""

    def maybe_rotate(self) -> None: ...
    def on_rate_limit(self) -> None: ...


# Module-level VPN rotator — set externally if needed.
_vpn: VPNRotator | None = None


def set_vpn(vpn: VPNRotator) -> None:
    """Register a VPN rotator for use by all HTTP helpers."""
    global _vpn
    _vpn = vpn


# ---------------------------------------------------------------------------
# Core HTTP helper
# ---------------------------------------------------------------------------
def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    retries: int = 3,
    timeout: float = 15,
) -> dict | list:
    """GET JSON with retry logic and VPN-aware rate-limit handling.

    Parameters
    ----------
    url : str
        The full URL to fetch.
    params : dict, optional
        Query parameters.
    retries : int
        Number of retry attempts.
    timeout : float
        HTTP request timeout in seconds.

    Returns
    -------
    dict | list
        Parsed JSON response.

    Raises
    ------
    requests.HTTPError
        If the request fails after all retries.
    """
    for attempt in range(retries):
        try:
            if _vpn is not None:
                _vpn.maybe_rotate()

            resp = requests.get(url, params=params, timeout=timeout)

            # Rate-limit — rotate VPN and retry
            if resp.status_code == 429:
                logger.warning("Rate limited (429) on %s", url)
                if _vpn is not None:
                    _vpn.on_rate_limit()
                wait = 2 ** (attempt + 1)
                logger.info("Backing off %ds before retry", wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            logger.warning("Request failed (%s), retrying in %ds: %s", type(exc).__name__, wait, exc)
            time.sleep(wait)

    # Should not be reached, but satisfy the type checker.
    raise requests.HTTPError(f"Failed after {retries} retries: {url}")
