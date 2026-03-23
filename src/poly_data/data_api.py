"""Data API client — post-resolution trade history."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from poly_data._http import DATA_API, get_json

logger = logging.getLogger(__name__)


class DataAPIClient:
    """Client for the Polymarket Data API (trade history, survives resolution).

    Parameters
    ----------
    base_url : str
        Override the Data API base URL.
    """

    def __init__(self, base_url: str = DATA_API) -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_trades(
        self,
        condition_id: str,
        *,
        max_offset: int = 3000,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all trades for a condition, paginated.

        Parameters
        ----------
        condition_id : str
            The market condition ID.
        max_offset : int
            Stop paginating after this offset (API hard limit).
        page_size : int
            Trades per page (API default is 100).

        Returns
        -------
        list[dict]
            All trades sorted by timestamp ascending.
        """
        all_trades: list[dict[str, Any]] = []
        offset = 0

        while offset <= max_offset:
            try:
                data = get_json(
                    f"{self.base_url}/trades",
                    params={"market": condition_id, "offset": offset},
                )
            except Exception:
                logger.warning(
                    "Trade fetch failed for %s at offset %d", condition_id, offset, exc_info=True
                )
                break

            if not isinstance(data, list) or not data:
                break

            all_trades.extend(data)

            if len(data) < page_size:
                break  # Last page
            offset += page_size

        all_trades.sort(key=lambda t: t.get("timestamp", ""))
        return all_trades

    def fetch_trades_df(self, condition_id: str, **kwargs) -> pd.DataFrame:
        """Like :meth:`fetch_trades` but return a DataFrame.

        Columns include ``timestamp``, ``price``, ``size``, ``side``, etc.
        """
        trades = self.fetch_trades(condition_id, **kwargs)
        if not trades:
            return pd.DataFrame()
        df = pd.DataFrame(trades)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df
