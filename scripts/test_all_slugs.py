#!/usr/bin/env python3
"""Batch-test all known Polymarket sport slugs.

Runs each slug through the test pipeline and produces a summary CSV.

Usage:
    python scripts/test_all_slugs.py
    python scripts/test_all_slugs.py --only nba,cbb,epl
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data import ClobClient, DataAPIClient, ESPNClient
from test_slug import fetch_resolved_events, find_game_with_history, price_df

OUTPUT_DIR = ROOT / "scripts" / "slug_plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Polymarket slug → ESPN sport key mapping ----------
# None = no ESPN coverage expected
SLUG_ESPN_MAP: dict[str, str | None] = {
    # --- US sports ---
    "nba": "nba",
    "nfl": "nfl",
    "mlb": "mlb",
    "nhl": "nhl",
    "cbb": "ncaam",
    "cwbb": "wnba",
    "cfb": "ncaaf",
    # --- Soccer ---
    "epl": "soccer",
    "laliga": "soccer",
    "bundesliga": "soccer",
    "ligue-1": "soccer",
    "mls": "soccer",
    "ucl": "soccer",
    "uel": "soccer",
    "sea": None,
    "bra": "soccer",
    "bra2": "soccer",
    "chi1": "soccer",
    "col1": "soccer",
    "mex": "soccer",
    "per1": "soccer",
    "jap": "soccer",
    "kor": "soccer",
    "csl": "soccer",
    "ere": "soccer",
    "por": "soccer",
    "tur": "soccer",
    "nor": "soccer",
    "den": "soccer",
    "spl": "soccer",
    "rou1": "soccer",
    "cze1": "soccer",
    "egy1": "soccer",
    "mar1": "soccer",
    "sud": "soccer",
    "ssc": "soccer",
    "cdr": "soccer",
    "cde": "soccer",
    "dfb": "soccer",
    "itc": "soccer",
    "acn": "soccer",
    "afc-wc": "soccer",
    "caf": "soccer",
    "concacaf": "soccer",
    "conmebol": "soccer",
    "crint": "soccer",
    "cehl": None,
    "dehl": None,
    "fifa-friendlies": "soccer",
    "ja2": "soccer",
    "lib": "soccer",
    "ucol": "soccer",
    "uef-qualifiers": "soccer",
    "ruprem": None,
    "rueuchamp": None,
    "rusixnat": None,
    "rusrp": None,
    "rutopft": None,
    "ruurc": None,
    # --- Hockey ---
    "ahl": "nhl",
    "khl": None,
    "shl": None,
    # --- Basketball (international) ---
    "bkarg": None,
    "bkcba": None,
    "bkcl": None,
    "bkfr1": None,
    "bkkbl": None,
    "bkligend": None,
    "bknbl": None,
    "bkseriea": None,
    # --- Combat ---
    "mwoh": "mma",
    "wwoh": "mma",
    "pll": None,
    "wll": None,
    "wbc": None,
    # --- Tennis ---
    "atp": "tennis",
    "wta": "tennis",
    "wtt-mens-singles": "tennis",
    # --- Cricket ---
    "cricbbl": "cricket",
    "criccsat20w": "cricket",
    "crichkt20w": "cricket",
    "cricipl": "cricket",
    "criclcl": "cricket",
    "cricpakt20cup": "cricket",
    "cricps": "cricket",
    "cricpsl": "cricket",
    "cricss": "cricket",
    "crict20lpl": "cricket",
    "cricthunderbolt": "cricket",
    "cricwncl": "cricket",
    # --- Esports ---
    "counter-strike": None,
    "call-of-duty": None,
    "dota-2": None,
    "league-of-legends": None,
    "mobile-legends-bang-bang": None,
    "overwatch": None,
    "rainbow-six-siege": None,
    "rocket-league": None,
    "starcraft-2": None,
    "valorant": None,
    # --- Other ---
    "aus": "soccer",
    "golf": "golf",
}


def test_one_slug(slug: str, espn_sport: str | None) -> dict:
    """Test a single slug. Returns a result dict."""
    result = {
        "slug": slug,
        "espn_key": espn_sport or "",
        "events": 0,
        "game_found": False,
        "market_type": "",
        "game_title": "",
        "num_outcomes": 0,
        "total_points": 0,
        "source": "",
        "espn_match": False,
        "plot": "",
        "error": "",
    }

    try:
        events = fetch_resolved_events(slug)
        result["events"] = len(events)
        if not events:
            result["error"] = "no resolved events"
            return result

        clob = ClobClient()
        data_api = DataAPIClient()
        game = find_game_with_history(events, clob, data_api)

        if not game:
            result["error"] = "no game with history"
            return result

        ev = game["event"]
        result["game_found"] = True
        result["game_title"] = ev.get("title", "?")[:80]
        result["market_type"] = game["market_type"]
        result["num_outcomes"] = len(game["labels"])
        result["total_points"] = sum(len(h) for h in game["histories"])
        result["source"] = game["source"]

        # ESPN matching
        if espn_sport:
            try:
                espn = ESPNClient()
                title = ev.get("title", "")
                end_date = ev.get("endDate", "")
                match = espn.find_game_event(title, end_date, espn_sport)
                if match:
                    result["espn_match"] = True
            except Exception:
                pass

        # Generate plot
        labels = game["labels"]
        histories = game["histories"]
        COLORS = ["#5C6BC0", "#FF7043", "#66BB6A", "#AB47BC"]
        STYLES = ["-", "--", ":"]

        dfs = [price_df(h) for h in histories]

        fig, ax = plt.subplots(figsize=(10, 5))
        for i, (label, df) in enumerate(zip(labels, dfs)):
            if not df.empty:
                ax.plot(df["timestamp"], df["price"], linewidth=1,
                        color=COLORS[i % len(COLORS)],
                        linestyle=STYLES[i % len(STYLES)],
                        label=label[:25])
        ax.set_title(f"[{slug}] {result['game_title'][:60]}", fontsize=11)
        ax.set_ylabel("Price ($)")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        fig.autofmt_xdate()
        plt.tight_layout()
        out = OUTPUT_DIR / f"{slug}.png"
        fig.savefig(out, dpi=100)
        plt.close(fig)
        result["plot"] = str(out.name)

    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch-test Polymarket sport slugs")
    parser.add_argument("--only", help="Comma-separated list of slugs to test")
    parser.add_argument("--skip-known", action="store_true", help="Skip slugs that already have plots")
    args = parser.parse_args()

    if args.only:
        slugs = [(s.strip(), SLUG_ESPN_MAP.get(s.strip())) for s in args.only.split(",")]
    else:
        slugs = list(SLUG_ESPN_MAP.items())

    print(f"Testing {len(slugs)} slugs...\n")
    results = []

    for i, (slug, espn_sport) in enumerate(slugs):
        if args.skip_known and (OUTPUT_DIR / f"{slug}.png").exists():
            print(f"[{i+1}/{len(slugs)}] {slug:30s} — SKIPPED (plot exists)")
            continue

        print(f"[{i+1}/{len(slugs)}] {slug:30s}", end=" ", flush=True)
        r = test_one_slug(slug, espn_sport)
        results.append(r)

        if r["game_found"]:
            espn_icon = "ESPN✓" if r["espn_match"] else "ESPN✗"
            print(f"— ✓ {r['total_points']:5d} pts ({r['market_type']}/{r['source']}) {espn_icon}  {r['game_title'][:40]}")
        elif r["events"] > 0:
            print(f"— ✗ {r['events']} events, {r['error']}")
        else:
            print(f"— ✗ {r['error']}")

        time.sleep(0.3)

    # Save CSV
    csv_path = OUTPUT_DIR / "slug_test_results.csv"
    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)

    # Summary
    total = len(results)
    found = sum(1 for r in results if r["game_found"])
    espn = sum(1 for r in results if r["espn_match"])
    no_ev = sum(1 for r in results if r["events"] == 0)
    draw = sum(1 for r in results if r["market_type"] == "draw")
    h2h = sum(1 for r in results if r["market_type"] == "h2h")

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {found}/{total} slugs have game with history")
    print(f"    H2H: {h2h}  |  3-way draw: {draw}")
    print(f"    ESPN matched: {espn}/{total}")
    print(f"    No events:    {no_ev}/{total}")
    print(f"  Results: {csv_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
