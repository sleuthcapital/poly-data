"""poly-data — Polymarket data client.

Wraps the Gamma, CLOB, Data, and ESPN APIs into a clean Python interface
that returns pandas DataFrames (or writes Parquet).  No trading logic.
"""

from poly_data.gamma import GammaClient
from poly_data.clob import ClobClient
from poly_data.data_api import DataAPIClient
from poly_data.espn import ESPNClient
from poly_data.markets import MarketFilter, DrawMarketGroup, group_draw_markets

__all__ = [
    "GammaClient",
    "ClobClient",
    "DataAPIClient",
    "ESPNClient",
    "MarketFilter",
    "DrawMarketGroup",
    "group_draw_markets",
]

__version__ = "0.1.0"
