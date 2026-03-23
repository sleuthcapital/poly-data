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
import pandas as pd

# Ensure poly-data is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data import GammaClient, ClobClient, DataAPIClient, MarketFilter
from poly_data.markets import detect_sport, parse_json_field, DrawMarketGroup

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


def _price_df(raw: list[dict]) -> pd.DataFrame:
    """Convert raw price history to a clean DataFrame."""
    if not raw:
        return pd.DataFrame(columns=["timestamp", "price"])
    df = pd.DataFrame(raw)
    if "t" in df.columns:
        df = df.rename(columns={"t": "timestamp", "p": "price"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


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

    # 2. Find a good H2H market with both tokens for price/book plots
    h2h_market = None
    for ev in events:
        for mkt in ev.get("markets", []):
            if MarketFilter.is_head_to_head(mkt):
                tokens = parse_json_field(
                    mkt.get("clobTokenIds") or mkt.get("tokens", [])
                )
                outcomes = parse_json_field(mkt.get("outcomes", []))
                if tokens and len(tokens) >= 2 and outcomes and len(outcomes) >= 2:
                    h2h_market = mkt
                    break
        if h2h_market:
            break

    # Extract both token IDs and their outcome labels
    token_a, token_b = "", ""
    label_a, label_b = "Outcome A", "Outcome B"
    if h2h_market:
        tokens = parse_json_field(h2h_market.get("clobTokenIds") or h2h_market.get("tokens", []))
        outcomes = parse_json_field(h2h_market.get("outcomes", []))
        token_a = str(tokens[0]) if not isinstance(tokens[0], dict) else tokens[0].get("token_id", "")
        token_b = str(tokens[1]) if not isinstance(tokens[1], dict) else tokens[1].get("token_id", "")
        label_a = outcomes[0] if outcomes else "Team A"
        label_b = outcomes[1] if len(outcomes) > 1 else "Team B"

    print(f"  H2H market: {h2h_market['question'][:80] if h2h_market else 'NONE'}")
    print(f"  {label_a}: token {token_a[:20]}…")
    print(f"  {label_b}: token {token_b[:20]}…")

    # 3. Price history for BOTH outcomes
    price_history_a = load_or_fetch("price_history_a", lambda: clob.fetch_price_history(token_a)) if token_a else []
    price_history_b = load_or_fetch("price_history_b", lambda: clob.fetch_price_history(token_b)) if token_b else []

    # 4. Order book for primary token
    orderbook = load_or_fetch("orderbook", lambda: clob.fetch_orderbook(token_a)) if token_a else {"bids": [], "asks": []}

    # 5. Trades (Data API)
    condition_id = (h2h_market.get("conditionId") or h2h_market.get("condition_id")) if h2h_market else None
    trades = load_or_fetch("trades", lambda: data_api.fetch_trades(condition_id, max_offset=1000)) if condition_id else []

    # 6. Find a soccer draw-market group
    draw_group = None
    draw_midpoints: dict[str, float] = {}
    for ev in events:
        if MarketFilter.is_soccer_event(ev):
            grp = DrawMarketGroup(ev)
            if grp.is_complete:
                draw_group = grp
                break

    if draw_group:
        draw_tokens = draw_group.yes_token_ids()
        for role, tid in draw_tokens.items():
            mid = load_or_fetch(f"draw_mid_{role}", lambda t=tid: clob.fetch_midpoint(t))
            if mid is not None:
                draw_midpoints[role] = float(mid) if not isinstance(mid, float) else mid

    return {
        "events": events,
        "h2h_market": h2h_market,
        "token_a": token_a, "token_b": token_b,
        "label_a": label_a, "label_b": label_b,
        "price_history_a": price_history_a,
        "price_history_b": price_history_b,
        "orderbook": orderbook,
        "trades": trades,
        "draw_group": draw_group,
        "draw_midpoints": draw_midpoints,
    }


# ── Plot generators ──────────────────────────────────────────────────

def plot_sport_distribution(events: list[dict]):
    """Horizontal bar chart of sports event counts (fetching-events.md)."""
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


def plot_price_history(data: dict):
    """Price line chart with BOTH outcomes labeled (price-data.md)."""
    df_a = _price_df(data["price_history_a"])
    df_b = _price_df(data["price_history_b"])
    if df_a.empty and df_b.empty:
        print("  ⚠ No price history data")
        return

    title = data["h2h_market"]["question"] if data["h2h_market"] else "Market"
    label_a, label_b = data["label_a"], data["label_b"]

    fig, ax = plt.subplots(figsize=(10, 4))
    if not df_a.empty:
        ax.plot(df_a["timestamp"], df_a["price"], linewidth=1.5,
                color="#5C6BC0", label=label_a)
        ax.fill_between(df_a["timestamp"], df_a["price"], alpha=0.1, color="#5C6BC0")
    if not df_b.empty:
        ax.plot(df_b["timestamp"], df_b["price"], linewidth=1.5,
                color="#FF7043", label=label_b, linestyle="--")
        ax.fill_between(df_b["timestamp"], df_b["price"], alpha=0.08, color="#FF7043")

    ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.4, label="50/50")
    short = title[:60] + "…" if len(title) > 60 else title
    ax.set_title(f"Price History — {short}")
    ax.set_ylabel("Price (implied probability)")
    ax.set_xlabel("Time")
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(ASSETS / "price_history.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ price_history.png")


def plot_depth_chart(data: dict):
    """Cumulative depth chart — unified (for both price-data.md and plotting.md)."""
    orderbook = data["orderbook"]
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    if not bids and not asks:
        print("  ⚠ No orderbook data")
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
    ax.set_title(f"Order Book Depth — {data['label_a']}")
    ax.legend()
    plt.tight_layout()
    # Save to both filenames (used by different doc pages)
    plt.savefig(ASSETS / "orderbook_depth.png", dpi=150, bbox_inches="tight")
    plt.savefig(ASSETS / "depth_chart.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ orderbook_depth.png + depth_chart.png")


def plot_sport_pie(events: list[dict]):
    """Sport distribution pie chart (market-filtering.md)."""
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


def plot_price_line(data: dict):
    """Full-width price line with both teams (plotting.md)."""
    df_a = _price_df(data["price_history_a"])
    df_b = _price_df(data["price_history_b"])
    if df_a.empty and df_b.empty:
        print("  ⚠ No price history for price_line")
        return

    title = data["h2h_market"]["question"] if data["h2h_market"] else "Market"
    label_a, label_b = data["label_a"], data["label_b"]

    fig, ax = plt.subplots(figsize=(12, 5))
    if not df_a.empty:
        ax.plot(df_a["timestamp"], df_a["price"], color="#3F51B5", linewidth=1.5,
                label=label_a)
        ax.fill_between(df_a["timestamp"], df_a["price"], alpha=0.1, color="#3F51B5")
    if not df_b.empty:
        ax.plot(df_b["timestamp"], df_b["price"], color="#FF7043", linewidth=1.5,
                label=label_b, linestyle="--")
        ax.fill_between(df_b["timestamp"], df_b["price"], alpha=0.08, color="#FF7043")
    ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.4, label="50/50")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Implied Probability")
    short = title[:60] + "…" if len(title) > 60 else title
    ax.set_title(short, fontsize=13)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(ASSETS / "price_line.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ price_line.png")


def plot_sport_bars(events: list[dict]):
    """Horizontal bar chart of sports coverage (plotting.md)."""
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
    """H2H market share by sport (plotting.md)."""
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
    """Hourly trade volume bar chart (plotting.md)."""
    if not trades:
        print("  ⚠ No trades data for volume chart")
        return
    df = pd.DataFrame(trades)

    if "timestamp" in df.columns:
        ts = df["timestamp"]
        try:
            df["timestamp"] = pd.to_datetime(ts, utc=True)
        except Exception:
            try:
                df["timestamp"] = pd.to_datetime(ts.astype(float), unit="s", utc=True)
            except Exception:
                print("  ⚠ Could not parse trade timestamps")
                return

    if "size" not in df.columns:
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


def plot_draw_market(draw_group, midpoints: dict[str, float]):
    """Bar chart showing draw-market implied probabilities (new plot)."""
    if draw_group is None or not draw_group.is_complete or not midpoints:
        print("  ⚠ No draw market data for draw chart")
        return

    probs = draw_group.implied_probabilities(midpoints)
    labels = [draw_group.team_a, draw_group.team_b, "Draw"]
    raw = [midpoints.get("team_a", 0), midpoints.get("team_b", 0), midpoints.get("draw", 0)]
    normed = [probs.get("team_a", 0), probs.get("team_b", 0), probs.get("draw", 0)]
    overround = probs.get("overround", 1.0)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(labels))
    ax.bar([xi - 0.2 for xi in x], raw, 0.35, label="Raw Yes Price",
           color=["#5C6BC0", "#FF7043", "#66BB6A"], alpha=0.7)
    bars_norm = ax.bar([xi + 0.2 for xi in x], normed, 0.35, label="Normalized Prob",
                       color=["#5C6BC0", "#FF7043", "#66BB6A"], alpha=1.0)

    for i, (r, n) in enumerate(zip(raw, normed)):
        ax.text(i - 0.2, r + 0.01, f"{r:.0%}", ha="center", fontsize=10)
        ax.text(i + 0.2, n + 0.01, f"{n:.0%}", ha="center", fontsize=10, fontweight="bold")

    ax.set_ylabel("Probability")
    ax.set_title(f"{draw_group.team_a} vs {draw_group.team_b}\n"
                 f"Overround: {overround:.1%}", fontsize=13)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max(raw + normed) * 1.2)
    ax.legend()
    plt.tight_layout()
    plt.savefig(ASSETS / "draw_market.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ draw_market.png")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("Fetching data…")
    data = fetch_all_data()
    events = data["events"]

    print(f"\nGenerating plots ({len(events)} events)…")
    plot_sport_distribution(events)
    plot_price_history(data)
    plot_depth_chart(data)
    plot_sport_pie(events)
    plot_price_line(data)
    plot_sport_bars(events)
    plot_h2h_pie(events)
    plot_trade_volume(data["trades"])
    plot_draw_market(data["draw_group"], data["draw_midpoints"])

    pngs = list(ASSETS.glob("*.png"))
    print(f"\nDone — {len(pngs)} images in {ASSETS}")


if __name__ == "__main__":
    main()
