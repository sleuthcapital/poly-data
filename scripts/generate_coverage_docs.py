#!/usr/bin/env python3
"""Generate the docs/sports-coverage.md page from the coverage registry.

Usage:
    python scripts/generate_coverage_docs.py          # write to docs/
    python scripts/generate_coverage_docs.py --stdout  # print to stdout
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data.coverage import load_registry, SlugInfo

# Human-friendly names for slugs
SLUG_NAMES: dict[str, str] = {
    # Soccer
    "epl": "Premier League", "laliga": "La Liga", "bundesliga": "Bundesliga",
    "ligue-1": "Ligue 1", "mls": "MLS", "ucl": "Champions League",
    "uel": "Europa League", "sea": "Serie A (Italy)", "bra": "Brasileirão Série A",
    "bra2": "Brasileirão Série B", "jap": "J-League", "ja2": "J2 League",
    "kor": "K League", "csl": "Chinese Super League", "mex": "Liga MX",
    "ere": "Eredivisie", "por": "Primeira Liga", "tur": "Süper Lig",
    "nor": "Eliteserien", "den": "Superliga (Denmark)", "spl": "Scottish Premiership",
    "ssc": "EFL Championship", "aus": "A-League", "ruprem": "Russian Premier League",
    "ucol": "Ukrainian Premier League", "sud": "Saudi Pro League",
    "itc": "Coppa Italia", "lib": "Copa Libertadores", "cdr": "Copa del Rey",
    "cde": "Copa del Rey (alt)", "dfb": "DFB-Pokal", "caf": "CAF Champions League",
    "concacaf": "CONCACAF", "conmebol": "CONMEBOL", "uef-qualifiers": "UEFA Qualifiers",
    "afc-wc": "World Cup Qualifiers", "fifa-friendlies": "FIFA Friendlies",
    "acn": "Africa Cup of Nations",
    # US Sports
    "nba": "NBA", "nfl": "NFL", "mlb": "MLB", "nhl": "NHL",
    "cbb": "NCAA Men's Basketball", "cwbb": "NCAA Women's Basketball",
    "cfb": "College Football",
    # Hockey
    "cehl": "Czech Extraliga", "dehl": "DEL (Germany)", "ahl": "AHL",
    "khl": "KHL", "shl": "SHL (Sweden)",
    # Basketball
    "bkcba": "CBA (China)", "bkcl": "Basketball Champions League",
    "bkfr1": "Pro A (France)", "bkkbl": "KBL (Korea)", "bkligend": "Liga Endesa (Spain)",
    "bknbl": "NBL (Australia)", "bkseriea": "Serie A (Italy Basketball)",
    "bkarg": "LNB (Argentina)", "rueuchamp": "EuroLeague",
    # Rugby
    "rusixnat": "Six Nations", "rusrp": "Premiership Rugby",
    "rutopft": "Top 14", "ruurc": "United Rugby Championship",
    # Lacrosse
    "pll": "PLL", "wll": "WLL",
    # Baseball
    "wbc": "World Baseball Classic",
    # Tennis
    "atp": "ATP", "wta": "WTA",
    # Table Tennis
    "wtt-mens-singles": "WTT Men's Singles",
    # Golf
    "golf": "Golf",
    # Esports
    "counter-strike": "Counter-Strike 2", "call-of-duty": "Call of Duty",
    "dota-2": "Dota 2", "league-of-legends": "League of Legends",
    "mobile-legends-bang-bang": "Mobile Legends", "overwatch": "Overwatch 2",
    "rainbow-six-siege": "Rainbow Six Siege", "rocket-league": "Rocket League",
    "starcraft-2": "StarCraft 2", "valorant": "Valorant",
    "mwoh": "Honor of Kings (Men)", "wwoh": "Honor of Kings (Women)",
    # Cricket
    "cricipl": "IPL", "cricpsl": "Pakistan Super League",
    "cricbbl": "Big Bash League", "criccsat20w": "CSA T20",
    "cricps": "Sheffield Shield", "cricss": "New Zealand Cricket",
    "cricthunderbolt": "Thunderbolt T10", "cricwncl": "Women's NCL",
    "criclcl": "Legends Cricket League", "cricpakt20cup": "National T20 Cup",
    "crict20lpl": "Lanka Premier League", "crichkt20w": "T20 (generic)",
    "crint": "International Cricket",
    # No events
    "chi1": "Chilean Primera", "col1": "Colombian Liga", "per1": "Peruvian Liga",
    "rou1": "Romanian Liga", "cze1": "Czech Liga", "egy1": "Egyptian Premier",
    "mar1": "Moroccan Botola",
}

SPORT_DISPLAY: dict[str, str] = {
    "soccer": "⚽ Soccer",
    "basketball": "🏀 Basketball",
    "esports": "🎮 Esports",
    "cricket": "🏏 Cricket",
    "hockey": "🏒 Hockey",
    "rugby": "🏉 Rugby",
    "football": "🏈 American Football",
    "baseball": "⚾ Baseball",
    "lacrosse": "🥍 Lacrosse",
    "tennis": "🎾 Tennis",
    "table-tennis": "🏓 Table Tennis",
    "golf": "⛳ Golf",
    "unknown": "❓ Other",
}

SPORT_ORDER = [
    "soccer", "basketball", "hockey", "esports", "cricket",
    "football", "baseball", "rugby", "lacrosse", "tennis",
    "table-tennis", "golf", "unknown",
]


def _name(slug: str) -> str:
    return SLUG_NAMES.get(slug, slug)


def _market_badge(mt: str | None) -> str:
    if mt == "h2h":
        return "H2H"
    elif mt == "draw":
        return "3-way"
    return "—"


def _status_icon(status: str) -> str:
    return {
        "active": "✅",
        "no_history": "⚠️",
        "no_events": "❌",
        "active_only": "⏳",
        "unknown": "❓",
    }.get(status, "❓")


def generate_page(registry: dict[str, SlugInfo]) -> str:
    lines: list[str] = []
    w = lines.append

    # Group by sport
    by_sport: dict[str, list[SlugInfo]] = {}
    for info in registry.values():
        by_sport.setdefault(info.sport, []).append(info)

    total = len(registry)
    active = sum(1 for s in registry.values() if s.status == "active")
    dates = [s.earliest_date for s in registry.values() if s.earliest_date]
    earliest = min(dates) if dates else "?"
    latest_dates = [s.latest_date for s in registry.values() if s.latest_date]
    latest = max(latest_dates) if latest_dates else "?"
    updated = next(
        (s.updated_at[:10] for s in registry.values() if s.updated_at), "?"
    )

    w("# Sports Coverage")
    w("")
    w(f"poly-data tracks **{active} active leagues** across **{len(by_sport)} sports**")
    w(f"with backtesting data spanning **{earliest}** to **{latest}**.")
    w("")
    w(f"*Last updated: {updated} — regenerate with `python scripts/update_coverage.py`*")
    w("")

    # Summary table
    w("## Overview")
    w("")
    w("| Sport | Active | Market Type | Earliest Data | Latest Data |")
    w("|-------|:------:|:-----------:|:------------:|:-----------:|")
    for sport in SPORT_ORDER:
        if sport not in by_sport:
            continue
        slugs = by_sport[sport]
        act = [s for s in slugs if s.status == "active"]
        if not act:
            w(f"| {SPORT_DISPLAY.get(sport, sport)} | 0/{len(slugs)} | — | — | — |")
            continue
        types = set(s.market_type for s in act if s.market_type)
        type_str = " / ".join(sorted(_market_badge(t) for t in types))
        e_dates = [s.earliest_date for s in act if s.earliest_date]
        l_dates = [s.latest_date for s in act if s.latest_date]
        w(
            f"| {SPORT_DISPLAY.get(sport, sport)} "
            f"| **{len(act)}**/{len(slugs)} "
            f"| {type_str} "
            f"| {min(e_dates) if e_dates else '—'} "
            f"| {max(l_dates) if l_dates else '—'} |"
        )
    w("")

    # Detailed tables per sport
    for sport in SPORT_ORDER:
        if sport not in by_sport:
            continue
        slugs_list = sorted(by_sport[sport], key=lambda s: (s.status != "active", s.earliest_date or "9999"))
        display = SPORT_DISPLAY.get(sport, sport)

        w(f"## {display}")
        w("")
        w("| Status | League | Slug | Type | Earliest | Latest | Events |")
        w("|:------:|--------|------|:----:|:--------:|:------:|:------:|")

        for s in slugs_list:
            icon = _status_icon(s.status)
            name = _name(s.slug)
            badge = _market_badge(s.market_type)
            e = s.earliest_date or "—"
            l = s.latest_date or "—"
            cnt = str(s.event_count) if s.event_count else "—"
            w(f"| {icon} | {name} | `{s.slug}` | {badge} | {e} | {l} | {cnt} |")
        w("")

    # How to query
    w("## Querying Coverage Programmatically")
    w("")
    w("The coverage data is shipped with the library as `coverage_data.json` and")
    w("can be queried without any API calls:")
    w("")
    w("```python")
    w("from poly_data import load_registry, coverage_df, active_slugs, coverage_summary")
    w("")
    w("# Get all active slugs")
    w("slugs = active_slugs()")
    w(f'# → {len([s for s in registry.values() if s.status == "active"])} slugs')
    w("")
    w("# Query a specific slug")
    w("reg = load_registry()")
    w('info = reg["nba"]')
    w("print(info.earliest_date)  # 2023-12-26")
    w("print(info.market_type)    # h2h")
    w("")
    w("# Get a pandas DataFrame of all coverage")
    w("df = coverage_df()")
    w('soccer = df[df["sport"] == "soccer"]')
    w(f"print(len(soccer))  # {sum(1 for s in registry.values() if s.sport == 'soccer')} leagues")
    w("")
    w("# Human-readable summary")
    w("print(coverage_summary())")
    w("```")
    w("")

    # Keeping up to date
    w("## Keeping Coverage Up to Date")
    w("")
    w("Run the update script periodically to refresh date ranges and discover new leagues:")
    w("")
    w("```bash")
    w("# Scan all known slugs (~2 min)")
    w("python scripts/update_coverage.py")
    w("")
    w("# Scan only specific slugs")
    w("python scripts/update_coverage.py --only nba,epl,laliga")
    w("")
    w("# Scan only one sport")
    w("python scripts/update_coverage.py --sport soccer")
    w("")
    w("# Preview without saving")
    w("python scripts/update_coverage.py --dry-run")
    w("")
    w("# Include extra slugs not in DEFAULT_SPORT_SLUGS")
    w("python scripts/update_coverage.py --include-extra")
    w("```")
    w("")

    # Status legend
    w("## Status Legend")
    w("")
    w("| Icon | Status | Meaning |")
    w("|:----:|--------|---------|")
    w("| ✅ | `active` | Has resolved events with detectable H2H or 3-way markets |")
    w("| ⚠️ | `no_history` | Events exist but no compatible market structure detected |")
    w("| ⏳ | `active_only` | Events exist but none have resolved yet |")
    w("| ❌ | `no_events` | No events found in the Gamma API for this slug |")
    w("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate sports coverage docs page")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing file")
    args = parser.parse_args()

    registry = load_registry()
    if not registry:
        print("ERROR: No coverage data found. Run: python scripts/update_coverage.py", file=sys.stderr)
        sys.exit(1)

    page = generate_page(registry)

    if args.stdout:
        print(page)
    else:
        out = ROOT / "docs" / "sports-coverage.md"
        out.write_text(page)
        print(f"Written to {out}")


if __name__ == "__main__":
    main()
