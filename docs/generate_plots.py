#!/usr/bin/env python3
"""Generate documentation plot images using real Polymarket API data.

Caches API responses in docs/assets/cache/ so subsequent runs skip the API.
Outputs PNG files to docs/assets/.

Usage:
    python docs/generate_plots.py              # use cache if available
    python docs/generate_plots.py --refresh    # force re-fetch from API
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Ensure poly-data is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data import GammaClient, ClobClient, DataAPIClient, MarketFilter
from poly_data.markets import detect_sport, parse_json_field

ASSETS = ROOT / "docs" / "assets"
CACHE = ASSETS / "cache"
ASSETS.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

REFRESH = "--refresh" in sys.argv

# ── Shared style ──────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#FAFAFA",
    "axes.edgecolor": "#CCCCCC",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
    "font.family": "sans-serif",
})


# ── Helpers ───────────────────────────────────────────────────────────

def cache_path(name: str) -> Path:
    return CACHE / f"{name}.json"


def load_or_fetch(name: str, fetcher):
    """Load from cache or call fetcher(), cache the result."""
    path = cache_path(name)
    if path.exists() and not REFRESH:
        print(f"  [cache] {name}")
        return json.loads(path.read_text())
    print(f"  [api]   {name}")
    data = fetcher()
    path.write_text(json.dumps(data, default=str))
    return data


# ── Data fetching ─────────────────────────────────────────────────────

def fetch_all_data():
    """Fetch and cache all data needed for plots."""
    gamma = GammaClient()
    clob = ClobClient()
    data_api = DataAPIClient()

    # 1. Active events (broad set of sport slugs)
    all_slugs = [
        "nba", "nfl", "mlb", "nhl", "soccer", "mma", "tennis",
        "cricket", "rugby", "f1", "boxing", "golf",
        "cs2", "valorant", "league-of-legends", "dota-2",
    ]
    events = load_or_fetch("events_active", lambda: gamma.fetch_events(
        active_only=True, sport_slugs=all_slugs,
    ))

    # 2. Find a good H2H market with a token_id for price/book plots
    h2h_market = None
    h2h_token_id = None
    for ev in events:
        for mkt in ev.get("markets", []):
            if MarketFilter.is_head_to_head(mkt):
                tokens = parse_json_field(
                    mkt.get("clobTokenIds") or mkt.get("tokens", [])
                )
                if tokens:
                    tid = str(tokens[0]) if not isinstance(tokens[0], dict) else tokens[0].get("token_id", "")
                    if tid:
                        h2h_market = mkt
                        h2h_token_id = tid
                        break
        if h2h_token_id:
            break

    print(f"  H2H market: {h2h_market['question'][:80] if h2h_market else 'NONE'}")
    print(f"  Token ID:   {h2h_token_id}")

    # 3. Price history
    price_history = []
    if h2h_token_id:
        price_history = load_or_fetch("price_history", lambda: clob.fetch_price_history(h2h_token_id))

    # 4. Order book
    orderbook = {"bids": [], "asks": []}
    if h2h_token_id:
        orderbook = load_or_fetch("orderbook", lambda: clob.fetch_orderbook(h2h_token_id))

    # 5. Trades (Data API) — use a condition_id from a resolved or active market
    condition_id = None
    if h2h_market:
        condition_id = h2h_market.get("conditionId") or h2h_market.get("condition_id")

    trades = []
    if condition_id:
        trades = load_or_fetch("trades", lambda: data_api.fetch_trades(condition_id, max_offset=1000))

    return {
        "events": events,
        "h2h_market": h2h_market,
        "h2h_token_id": h2h_token_id,
        "price_history": price_history,
        "orderbook": orderbook,
        "trades": trades,
    }


# ── Plot generators ──────────────────────────────────────────────────

def plot_sport_distribution(events: list[dict]):
    """Horizontal bar chart of sports event counts (for fetching-events.md)."""
    sports = Counter(
        detect_sport(ev.get("title", ""), tags=ev.get("tags"))
        for ev in events
    )
    items = sports.most_common(15)
    if not items:
        print("  ⚠ No sport data for distribution chart")
        return
    labels, counts = zip(*items)

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = plt.cm.Set3(range(len(labels)))
    bars = ax.barh(labels, counts, color=colors)
    ax.set_xlabel("Number of Active Events")
    ax.set_title("Polymarket Sports Event Distribution")
    ax.invert_yaxis()
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(ASSETS / "sport_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ sport_distribution.png")


def plot_price_history(price_history: list[dict], title: str):
    """Price line chart with fill (for price-data.md)."""
    if not price_history:
        print("  ⚠ No price history data")
        return
    import pandas as pd
    df = pd.DataFrame(price_history)
    if "t" in df.columns:
        df = df.rename(columns={"t": "timestamp", "p": "price"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    if df.empty:
        print("  ⚠ Price history DataFrame empty")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["timestamp"], df["price"], linewidth=1.5, color="#5C6BC0")
    ax.fill_between(df["timestamp"], df["price"], alpha=0.15, color="#5C6BC0")
    ax.set_ylabel("Price (probability)")
    ax.set_xlabel("Time")
    short_title = title[:60] + "…" if len(title) > 60 else title
    ax.set_title(f"Price History — {short_title}")
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    plt.tight_layout()
    plt.savefig(ASSETS / "price_history.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ price_history.png")


def plot_orderbook_depth(orderbook: dict):
    """Order book bar chart (for price-data.md)."""
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    if not bids and not asks:
        print("  ⚠ No orderbook data")
        return

    bid_prices = [float(b["price"]) for b in bids]
    bid_sizes = [float(b["size"]) for b in bids]
    ask_prices = [float(a["price"]) for a in asks]
    ask_sizes = [float(a["size"]) for a in asks]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(bid_prices, bid_sizes, width=0.005, color="#4CAF50", alpha=0.8, label="Bids")
    ax.bar(ask_prices, ask_sizes, width=0.005, color="#F44336", alpha=0.8, label="Asks")
    ax.set_xlabel("Price")
    ax.set_ylabel("Size ($)")
    ax.set_title("Order Book Depth")
    ax.legend()
    plt.tight_layout()
    plt.savefig(ASSETS / "orderbook_depth.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ orderbook_depth.png")


def plot_sport_pie(events: list[dict]):
    """Sport distribution pie chart (for market-filtering.md)."""
    sports = Counter(
        detect_sport(ev.get("title", ""), tags=ev.get("tags"))
        for ev in events
    )
    top = sports.most_common(10)
    if not top:
        print("  ⚠ No sport data for pie chart")
        return
    labels = [f"{k} ({v})" for k, v in top]
    sizes = [v for _, v in top]

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = plt.cm.Set3(range(len(labels)))
    ax.pie(sizes, labels=labels, autopct="%1.0f%%", colors=colors, pctdistance=0.85)
    ax.set_title("Polymarket Event Distribution by Sport")
    plt.tight_layout()
    plt.savefig(ASSETS / "sport_pie.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ sport_pie.png")


def plot_price_line(price_history: list[dict], title: str):
    """Price line chart with 50/50 line (for plotting.md)."""
    if not price_history:
        print("  ⚠ No price history for price_line")
        return
    import pandas as pd
    df = pd.DataFrame(price_history)
    if "t" in df.columns:
        df = df.rename(columns={"t": "timestamp", "p": "price"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["timestamp"], df["price"], color="#3F51B5", linewidth=1.5)
    ax.fill_between(df["timestamp"], df["price"], alpha=0.1, color="#3F51B5")
    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5, label="50/50")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Implied Probability")
    short_title = title[:60] + "…" if len(title) > 60 else title
    ax.set_title(short_title, fontsize=13)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    ax.legend()
    plt.tight_layout()
    plt.savefig(ASSETS / "price_line.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ price_line.png")


def plot_depth_chart(orderbook: dict):
    """Cumulative depth chart (for plotting.md)."""
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    if not bids and not asks:
        print("  ⚠ No orderbook data for depth_chart")
        return

    bid_sorted = sorted(bids, key=lambda x: -float(x["price"]))
    ask_sorted = sorted(asks, key=lambda x: float(x["price"]))

    bid_prices = [float(b["price"]) for b in bid_sorted]
    bid_cum = list(np.cumsum([float(b["size"]) for b in bid_sorted]))
    ask_prices = [float(a["price"]) for a in ask_sorted]
    ask_cum = list(np.cumsum([float(a["size"]) for a in ask_sorted]))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(bid_prices, bid_cum, alpha=0.4, color="#4CAF50", step="post", label="Bids")
    ax.fill_between(ask_prices, ask_cum, alpha=0.4, color="#F44336", step="post", label="Asks")
    ax.step(bid_prices, bid_cum, color="#4CAF50", linewidth=1.5, where="post")
    ax.step(ask_prices, ask_cum, color="#F44336", linewidth=1.5, where="post")
    ax.set_xlabel("Price")
    ax.set_ylabel("Cumulative Size ($)")
    ax.set_title("Order Book Depth")
    ax.legend()
    plt.tight_layout()
    plt.savefig(ASSETS / "depth_chart.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ depth_chart.png")


def plot_sport_bars(events: list[dict]):
    """Horizontal bar chart of sports coverage (for plotting.md)."""
    sports = Counter(
        detect_sport(ev.get("title", ""), tags=ev.get("tags"))
        for ev in events
    )
    items = sports.most_common(12)
    if not items:
        print("  ⚠ No sport data for sport_bars")
        return
    labels, counts = zip(*items)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#3F51B5" if c > 50 else "#9FA8DA" for c in counts]
    bars = ax.barh(labels, counts, color=colors)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontweight="bold", fontsize=10)
    ax.set_xlabel("Number of Active Events", fontsize=11)
    ax.set_title("Polymarket Sports Coverage", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(ASSETS / "sport_bars.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ sport_bars.png")


def plot_h2h_pie(events: list[dict]):
    """H2H market share by sport (for plotting.md)."""
    h2h_sports = Counter()
    for ev in events:
        sport = detect_sport(ev.get("title", ""), tags=ev.get("tags"))
        for mkt in ev.get("markets", []):
            if MarketFilter.is_head_to_head(mkt):
                h2h_sports[sport] += 1

    top = h2h_sports.most_common(8)
    if not top:
        print("  ⚠ No H2H data for pie chart")
        return
    labels, sizes = zip(*top)

    fig, ax = plt.subplots(figsize=(8, 8))
    explode = [0.05] * len(labels)
    colors = plt.cm.Paired(range(len(labels)))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%",
           explode=explode, colors=colors,
           textprops={"fontsize": 11}, pctdistance=0.82)
    ax.set_title("H2H Markets by Sport", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(ASSETS / "h2h_pie.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ h2h_pie.png")


def plot_trade_volume(trades: list[dict]):
    """Hourly trade volume bar chart (for plotting.md)."""
    if not trades:
        print("  ⚠ No trades data for volume chart")
        return
    import pandas as pd
    df = pd.DataFrame(trades)

    # Handle different timestamp formats
    if "timestamp" in df.columns:
        ts = df["timestamp"]
        # Try ISO string first, then unix seconds
        try:
            df["timestamp"] = pd.to_datetime(ts, utc=True)
        except Exception:
            try:
                df["timestamp"] = pd.to_datetime(ts.astype(float), unit="s", utc=True)
            except Exception:
                print("  ⚠ Could not parse trade timestamps")
                return

    if "size" not in df.columns:
        # Some trade responses use 'match_amount' or similar
        for alt in ["match_amount", "amount", "value"]:
            if alt in df.columns:
                df["size"] = df[alt]
                break
    if "size" not in df.columns:
        print("  ⚠ No size column in trades")
        return

    df["size"] = pd.to_numeric(df["size"], errors="coerce").fillna(0)
    df["hour"] = df["timestamp"].dt.floor("h")
    hourly = df.groupby("hour")["size"].sum().reset_index()

    if hourly.empty:
        print("  ⚠ No hourly data")
        return

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(hourly["hour"], hourly["size"], width=0.03, color="#FF7043", alpha=0.8)
    ax.set_xlabel("Time")
    ax.set_ylabel("Volume ($)")
    ax.set_title("Hourly Trade Volume")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    plt.tight_layout()
    plt.savefig(ASSETS / "trade_volume.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ trade_volume.png")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("Fetching data…")
    data = fetch_all_data()
    events = data["events"]
    title = data["h2h_market"]["question"] if data["h2h_market"] else "Market"

    print(f"\nGenerating plots ({len(events)} events)…")
    plot_sport_distribution(events)
    plot_price_history(data["price_history"], title)
    plot_orderbook_depth(data["orderbook"])
    plot_sport_pie(events)
    plot_price_line(data["price_history"], title)
    plot_depth_chart(data["orderbook"])
    plot_sport_bars(events)
    plot_h2h_pie(events)
    plot_trade_volume(data["trades"])

    pngs = list(ASSETS.glob("*.png"))
    print(f"\nDone — {len(pngs)} images in {ASSETS}")


if __name__ == "__main__":
    main()
