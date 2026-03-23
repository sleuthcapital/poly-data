#!/usr/bin/env python3
"""Test a Polymarket sport slug end-to-end.

For a given slug, this script:
1. Fetches recent resolved events from the Gamma API
2. Finds a head-to-head market with price history
3. Attempts ESPN game time lookup
4. Generates a price history plot with game time markers

Usage:
    python scripts/test_slug.py nba
    python scripts/test_slug.py cbb --espn-sport ncaam
    python scripts/test_slug.py epl --espn-sport soccer
    python scripts/test_slug.py counter-strike   # no ESPN
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data import GammaClient, ClobClient, DataAPIClient, ESPNClient, MarketFilter
from poly_data._http import GAMMA_API, get_json
from poly_data.gamma import TAG_SLUG_MAP, resolve_tag_slug
from poly_data.markets import detect_sport, parse_json_field
from poly_data.espn import ESPN_SPORT_PATHS

OUTPUT_DIR = ROOT / "scripts" / "slug_plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_resolved_events(slug: str, limit: int = 30) -> list[dict]:
    """Fetch recent resolved events for a given Polymarket slug.

    Automatically remaps frontend URL slugs to the real Gamma API
    ``tag_slug`` values when they differ.
    """
    real_tag = resolve_tag_slug(slug)
    data = get_json(
        f"{GAMMA_API}/events",
        params={
            "tag_slug": real_tag,
            "closed": "true",
            "limit": limit,
            "order": "endDate",
            "ascending": "false",
        },
    )
    return data if isinstance(data, list) else []


def _get_history(mkt: dict, clob: ClobClient, data_api: DataAPIClient, min_points: int = 10):
    """Get price history for a single market (CLOB first, then trades)."""
    tokens = parse_json_field(mkt.get("clobTokenIds") or mkt.get("tokens", []))
    outcomes = parse_json_field(mkt.get("outcomes", []))
    if not tokens or not outcomes:
        return None, None, None

    token_a = str(tokens[0]) if not isinstance(tokens[0], dict) else tokens[0].get("token_id", "")

    # Try CLOB
    hist = clob.fetch_price_history(token_a)
    if len(hist) > min_points:
        return hist, "clob", outcomes

    # Fall back to trades
    cid = mkt.get("conditionId") or mkt.get("condition_id")
    if cid:
        trades = data_api.fetch_trades(cid, max_offset=3000)
        if len(trades) > min_points:
            # For Yes/No markets, "Yes" side price history
            label = outcomes[0] if outcomes[0] not in ("Yes", "No") else "Yes"
            hist = DataAPIClient.trades_to_price_history(trades, label)
            if not hist:
                # Try without filter
                hist = DataAPIClient.trades_to_price_history(trades)
            if len(hist) > min_points:
                return hist, "trades", outcomes

    return None, None, None


def find_game_with_history(events: list[dict], clob: ClobClient, data_api: DataAPIClient, min_points: int = 10):
    """Find first game event with sufficient price history.
    
    Supports both H2H (2-outcome) and 3-way draw (grouped Yes/No) markets.
    
    Returns dict with keys: event, markets, labels, histories, source, market_type
    or None if nothing found.
    """
    for ev in events:
        markets = ev.get("markets", [])
        title = ev.get("title", "")

        # --- Try H2H first (2-outcome market) ---
        for mkt in markets:
            if MarketFilter.is_head_to_head(mkt):
                tokens = parse_json_field(mkt.get("clobTokenIds") or mkt.get("tokens", []))
                outcomes = parse_json_field(mkt.get("outcomes", []))
                if tokens and len(tokens) >= 2 and outcomes and len(outcomes) >= 2:
                    token_a = str(tokens[0]) if not isinstance(tokens[0], dict) else tokens[0].get("token_id", "")
                    token_b = str(tokens[1]) if not isinstance(tokens[1], dict) else tokens[1].get("token_id", "")
                    label_a, label_b = outcomes[0], outcomes[1]

                    # Try CLOB
                    hist_a = clob.fetch_price_history(token_a)
                    if len(hist_a) > min_points:
                        hist_b = clob.fetch_price_history(token_b)
                        return {
                            "event": ev, "markets": [mkt],
                            "labels": [label_a, label_b],
                            "histories": [hist_a, hist_b],
                            "source": "clob", "market_type": "h2h",
                        }

                    # Try trades
                    cid = mkt.get("conditionId") or mkt.get("condition_id")
                    if cid:
                        trades = data_api.fetch_trades(cid, max_offset=3000)
                        if len(trades) > min_points:
                            hist_a = DataAPIClient.trades_to_price_history(trades, label_a)
                            hist_b = DataAPIClient.trades_to_price_history(trades, label_b)
                            if len(hist_a) > min_points:
                                return {
                                    "event": ev, "markets": [mkt],
                                    "labels": [label_a, label_b],
                                    "histories": [hist_a, hist_b],
                                    "source": "trades", "market_type": "h2h",
                                }

        # --- Try 3-way draw market (grouped Yes/No per outcome) ---
        # Detect: event has exactly 3 markets, each with groupItemTitle containing team names or "Draw"
        # Skip events with suffixes like "- Halftime Result", "- Exact Score" etc.
        has_suffix = " - " in title and any(
            s in title for s in ("Exact Score", "Halftime", "Player Props", "Total Corner", "More Markets")
        )
        if has_suffix:
            continue

        draw_markets = [m for m in markets if m.get("groupItemTitle")]
        if len(draw_markets) == 3:
            # Check if one group is a "Draw" market
            draw_mkts = [m for m in draw_markets if "draw" in (m.get("groupItemTitle") or "").lower()]
            team_mkts = [m for m in draw_markets if "draw" not in (m.get("groupItemTitle") or "").lower()]
            if len(draw_mkts) == 1 and len(team_mkts) == 2:
                labels = []
                histories = []
                source = None
                all_ok = True
                for m in team_mkts + draw_mkts:
                    hist, src, _ = _get_history(m, clob, data_api, min_points)
                    if hist and len(hist) > min_points:
                        grp = m.get("groupItemTitle", "?")
                        labels.append(grp)
                        histories.append(hist)
                        if src:
                            source = src
                    else:
                        all_ok = False
                        break
                if all_ok and len(histories) == 3:
                    return {
                        "event": ev, "markets": draw_markets,
                        "labels": labels, "histories": histories,
                        "source": source, "market_type": "draw",
                    }

    return None


def try_espn_match(title: str, end_date: str, espn_sport: str, espn: ESPNClient):
    """Attempt ESPN game time lookup."""
    if not ESPN_SPORT_PATHS.get(espn_sport):
        return None, None, f"No ESPN paths for '{espn_sport}'"

    event = espn.find_game_event(title, end_date[:10], espn_sport, search_days=3)
    if not event:
        return None, None, "No ESPN match found"

    game_start = event.get("date")
    game_end = espn.estimate_game_end(event, espn_sport)
    name = event.get("name", "?")
    return game_start, game_end, f"ESPN: {name}"


def price_df(raw: list[dict]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["timestamp", "price"])
    df = pd.DataFrame(raw)
    if "t" in df.columns:
        df = df.rename(columns={"t": "timestamp", "p": "price"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


def trim_pregame(df: pd.DataFrame, game_start: str | None, hours: float = 6) -> pd.DataFrame:
    if df.empty or not game_start:
        return df
    try:
        cutoff = pd.to_datetime(game_start, utc=True) - pd.Timedelta(hours=hours)
        trimmed = df[df["timestamp"] >= cutoff].reset_index(drop=True)
        return trimmed if not trimmed.empty else df
    except Exception:
        return df


def generate_plot(
    slug: str,
    title: str,
    labels: list[str],
    histories: list[list[dict]],
    game_start: str | None,
    game_end: str | None,
):
    """Generate and save a price history plot (supports 2 or 3 outcomes)."""
    COLORS = ["#5C6BC0", "#FF7043", "#66BB6A", "#AB47BC"]
    STYLES = ["-", "--", ":"]

    dfs = []
    for hist in histories:
        df = price_df(hist)
        if game_start:
            df = trim_pregame(df, game_start)
        dfs.append(df)

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (label, df) in enumerate(zip(labels, dfs)):
        c = COLORS[i % len(COLORS)]
        ls = STYLES[i % len(STYLES)]
        if not df.empty:
            ax.plot(df["timestamp"], df["price"], linewidth=1.5, color=c, label=label, linestyle=ls)
            ax.fill_between(df["timestamp"], df["price"], alpha=0.08, color=c)

    ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.4)

    for time_str, label, color, ls in [
        (game_start, "Game Start", "#2E7D32", "-"),
        (game_end, "Game End (est.)", "#C62828", "--"),
    ]:
        if time_str:
            try:
                dt = pd.to_datetime(time_str, utc=True)
                ax.axvline(x=dt, color=color, linestyle=ls, linewidth=1.5, alpha=0.8, label=label)
            except Exception:
                pass

    short = title[:65] + "…" if len(title) > 65 else title
    ax.set_title(f"[{slug}] {short}", fontsize=12)
    ax.set_ylabel("Price (implied probability)")
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()

    out_path = OUTPUT_DIR / f"{slug}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


def test_slug(slug: str, espn_sport: str | None = None):
    """Run the full test for a single slug."""
    print(f"\n{'='*60}")
    print(f"  TESTING SLUG: {slug}")
    if espn_sport:
        print(f"  ESPN sport:   {espn_sport}")
    print(f"{'='*60}")

    # Step 1: Fetch resolved events
    print("\n[1] Fetching resolved events...")
    events = fetch_resolved_events(slug)
    print(f"    Found {len(events)} resolved events")
    if not events:
        print("    ✗ No resolved events — try a different slug or check if it's active-only")
        return False

    # Step 2: Find game with price history (H2H or 3-way)
    print("\n[2] Finding game with price history...")
    clob = ClobClient()
    data_api = DataAPIClient()
    result = find_game_with_history(events, clob, data_api)
    if not result:
        print("    ✗ No game with price history found")
        for e in events[:5]:
            print(f"      - {e.get('title', '?')[:60]}")
        return False

    ev = result["event"]
    labels = result["labels"]
    histories = result["histories"]
    source = result["source"]
    market_type = result["market_type"]
    title = ev.get("title", "?")
    end_date = ev.get("endDate", "")

    print(f"    ✓ {title[:70]}")
    print(f"      Type: {market_type} ({len(labels)} outcomes)")
    print(f"      Source: {source}")
    for lbl, hist in zip(labels, histories):
        print(f"      {len(hist):5d} pts — {lbl}")

    # Step 3: ESPN matching
    game_start, game_end = None, None
    if espn_sport:
        print(f"\n[3] ESPN matching (sport={espn_sport})...")
        espn = ESPNClient()
        game_start, game_end, msg = try_espn_match(title, end_date, espn_sport, espn)
        if game_start:
            print(f"    ✓ {msg}")
            print(f"      Start: {game_start}")
            print(f"      End:   {game_end}")
        else:
            print(f"    ✗ {msg}")
    else:
        print(f"\n[3] ESPN: skipped (no ESPN sport mapping)")

    # Auto-detect sport from title for ESPN if not provided
    if not espn_sport:
        detected = detect_sport(title, tags=ev.get("tags"))
        print(f"    detect_sport() → {detected}")

    # Step 4: Generate plot
    print(f"\n[4] Generating plot...")
    out_path = generate_plot(slug, title, labels, histories, game_start, game_end)
    print(f"    ✓ Saved to {out_path}")

    # Summary
    pts_str = " / ".join(str(len(h)) for h in histories)
    print(f"\n{'─'*60}")
    print(f"  RESULT: {slug}")
    print(f"    Events:       {len(events)}")
    print(f"    Game:         {title[:60]}")
    print(f"    Type:         {market_type}")
    print(f"    Price points: {pts_str}")
    print(f"    ESPN match:   {'YES' if game_start else 'NO'}")
    print(f"    Plot:         {out_path.name}")
    print(f"{'─'*60}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test a Polymarket sport slug end-to-end")
    parser.add_argument("slug", help="Polymarket sport slug (e.g. nba, cbb, epl)")
    parser.add_argument("--espn-sport", "-e", help="ESPN sport key (e.g. nba, soccer, ncaam)")
    args = parser.parse_args()
    test_slug(args.slug, args.espn_sport)


if __name__ == "__main__":
    main()
