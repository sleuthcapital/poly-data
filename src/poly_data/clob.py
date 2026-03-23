"""CLOB API client — order books, midpoints, price history."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from poly_data._http import CLOB_API, get_json

logger = logging.getLogger(__name__)


class ClobClient:
    """Client for the Polymarket CLOB API (live & historical prices).

    Parameters
    ----------
    base_url : str
        Override the CLOB API base URL.
    """

    def __init__(self, base_url: str = CLOB_API) -> None:
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Live market data
    # ------------------------------------------------------------------
    def fetch_orderbook(self, token_id: str) -> dict[str, Any]:
        """Fetch full order book for a token.

        Returns
        -------
        dict
            Raw order book with ``bids`` and ``asks`` lists.
        """
        return get_json(f"{self.base_url}/book", params={"token_id": token_id})

    def fetch_midpoint(self, token_id: str) -> float | None:
        """Fetch the midpoint price for a token.

        Returns
        -------
        float | None
            Midpoint price, or None if unavailable.
        """
        try:
            data = get_json(f"{self.base_url}/midpoint", params={"token_id": token_id})
            mid = data.get("mid") if isinstance(data, dict) else None
            return float(mid) if mid is not None else None
        except Exception:
            logger.debug("Could not fetch midpoint for %s", token_id, exc_info=True)
            return None

    def fetch_last_trade(self, token_id: str) -> dict[str, Any] | None:
        """Fetch the most recent trade for a token.

        Returns
        -------
        dict | None
            Last trade dict, or None if no trades exist.
        """
        try:
            data = get_json(f"{self.base_url}/trades", params={"token_id": token_id, "limit": 1})
            if isinstance(data, list) and data:
                return data[0]
            return None
        except Exception:
            logger.debug("Could not fetch last trade for %s", token_id, exc_info=True)
            return None

    def snapshot_market(self, market: dict[str, Any]) -> dict[str, Any]:
        """Take a full price snapshot of a market (all tokens).

        Parameters
        ----------
        market : dict
            A Gamma market dict containing ``tokens`` (list with ``token_id``).

        Returns
        -------
        dict
            Snapshot with midpoint, best bid/ask, depth, and last trade per token.
        """
        from poly_data.markets import parse_json_field

        tokens = parse_json_field(market.get("tokens", []))
        outcomes = parse_json_field(market.get("outcomes", []))

        snapshot: dict[str, Any] = {"condition_id": market.get("conditionId", "")}
        for i, token in enumerate(tokens):
            tid = token.get("token_id", "") if isinstance(token, dict) else str(token)
            outcome = outcomes[i] if i < len(outcomes) else f"outcome_{i}"

            mid = self.fetch_midpoint(tid)
            book = self.fetch_orderbook(tid)
            last = self.fetch_last_trade(tid)

            bids = book.get("bids", []) if isinstance(book, dict) else []
            asks = book.get("asks", []) if isinstance(book, dict) else []

            snapshot[outcome] = {
                "token_id": tid,
                "midpoint": mid,
                "best_bid": float(bids[0]["price"]) if bids else None,
                "best_ask": float(asks[0]["price"]) if asks else None,
                "bid_depth": sum(float(b.get("size", 0)) for b in bids),
                "ask_depth": sum(float(a.get("size", 0)) for a in asks),
                "last_trade_price": float(last["price"]) if last and "price" in last else None,
                "last_trade_size": float(last["size"]) if last and "size" in last else None,
            }

        return snapshot

    # ------------------------------------------------------------------
    # Historical prices
    # ------------------------------------------------------------------
    def fetch_price_history(
        self,
        token_id: str,
        *,
        fidelity: int = 1,
        interval: str = "max",
    ) -> list[dict[str, Any]]:
        """Fetch historical price time series for a token.

        .. warning::
            CLOB price history is **purged after market resolution**.
            Use :class:`DataAPIClient` for post-resolution trade data.

        Parameters
        ----------
        token_id : str
            The token to fetch history for.
        fidelity : int
            Resolution parameter (1 = highest fidelity).
        interval : str
            Time range (``"max"`` for full history).

        Returns
        -------
        list[dict]
            Price points with ``t`` (timestamp) and ``p`` (price).
        """
        data = get_json(
            f"{self.base_url}/prices-history",
            params={"market": token_id, "interval": interval, "fidelity": fidelity},
        )
        if isinstance(data, dict):
            return data.get("history", [])
        return data if isinstance(data, list) else []

    def fetch_price_history_df(self, token_id: str, **kwargs) -> pd.DataFrame:
        """Like :meth:`fetch_price_history` but return a DataFrame.

        Columns: ``timestamp`` (datetime), ``price`` (float).
        """
        history = self.fetch_price_history(token_id, **kwargs)
        if not history:
            return pd.DataFrame(columns=["timestamp", "price"])
        df = pd.DataFrame(history)
        if "t" in df.columns:
            df = df.rename(columns={"t": "timestamp", "p": "price"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        return df
