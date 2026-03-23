#!/usr/bin/env python3
"""Refresh the slug coverage registry by scanning the Gamma API.

For every known slug, this script:
1. Fetches the newest resolved event (to get latest_date + market type).
2. Fetches the oldest resolved event (to get earliest_date).
3. Counts total resolved events.
4. Writes the results to ``src/poly_data/coverage_data.json``.

Usage:
    python scripts/update_coverage.py              # scan all slugs
    python scripts/update_coverage.py --only nba,epl,laliga
    python scripts/update_coverage.py --sport soccer
    python scripts/update_coverage.py --dry-run     # print without saving
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from poly_data._http import GAMMA_API, get_json
from poly_data.gamma import DEFAULT_SPORT_SLUGS, TAG_SLUG_MAP, resolve_tag_slug
from poly_data.markets import MarketFilter, parse_json_field
from poly_data.coverage import SlugInfo, load_registry, save_registry


# ---------------------------------------------------------------------------
# Sport classification (mirrors test_all_slugs.py SLUG_ESPN_MAP)
# ---------------------------------------------------------------------------
SLUG_SPORT: dict[str, str] = {
    # US traditional
    "nba": "basketball", "nfl": "football", "mlb": "baseball", "nhl": "hockey",
    "cbb": "basketball", "cwbb": "basketball", "cfb": "football",
    # Soccer
    "epl": "soccer", "laliga": "soccer", "bundesliga": "soccer",
    "ligue-1": "soccer", "mls": "soccer", "ucl": "soccer", "uel": "soccer",
    "sea": "soccer", "bra": "soccer", "bra2": "soccer", "jap": "soccer",
    "ja2": "soccer", "kor": "soccer", "csl": "soccer", "mex": "soccer",
    "ere": "soccer", "por": "soccer", "tur": "soccer", "nor": "soccer",
    "den": "soccer", "spl": "soccer", "ssc": "soccer", "aus": "soccer",
    "ruprem": "soccer", "ucol": "soccer", "sud": "soccer", "itc": "soccer",
    "lib": "soccer", "cdr": "soccer", "cde": "soccer", "dfb": "soccer",
    "caf": "soccer", "concacaf": "soccer", "conmebol": "soccer",
    "uef-qualifiers": "soccer", "afc-wc": "soccer", "fifa-friendlies": "soccer",
    "acn": "soccer",
    # Hockey (non-NHL)
    "cehl": "hockey", "dehl": "hockey", "ahl": "hockey", "khl": "hockey",
    "shl": "hockey",
    # Basketball (international)
    "bkcba": "basketball", "bkcl": "basketball", "bkfr1": "basketball",
    "bkkbl": "basketball", "bkligend": "basketball", "bknbl": "basketball",
    "bkseriea": "basketball", "bkarg": "basketball", "rueuchamp": "basketball",
    # Rugby
    "rusixnat": "rugby", "rusrp": "rugby", "rutopft": "rugby", "ruurc": "rugby",
    # Lacrosse
    "pll": "lacrosse", "wll": "lacrosse",
    # Baseball (international)
    "wbc": "baseball",
    # Tennis
    "atp": "tennis", "wta": "tennis",
    # Table Tennis
    "wtt-mens-singles": "table-tennis",
    # Golf
    "golf": "golf",
    # Esports
    "counter-strike": "esports", "call-of-duty": "esports",
    "dota-2": "esports", "league-of-legends": "esports",
    "mobile-legends-bang-bang": "esports", "overwatch": "esports",
    "rainbow-six-siege": "esports", "rocket-league": "esports",
    "starcraft-2": "esports", "valorant": "esports",
    "mwoh": "esports", "wwoh": "esports",
    # Cricket
    "cricipl": "cricket", "cricpsl": "cricket", "cricbbl": "cricket",
    "criccsat20w": "cricket", "cricps": "cricket", "cricss": "cricket",
    "cricthunderbolt": "cricket", "cricwncl": "cricket", "criclcl": "cricket",
    "cricpakt20cup": "cricket", "crict20lpl": "cricket", "crichkt20w": "cricket",
    "crint": "cricket",
}

SLUG_ESPN: dict[str, str | None] = {
    "nba": "nba", "nfl": "nfl", "mlb": "mlb", "nhl": "nhl",
    "cbb": "ncaam", "cwbb": "wnba", "cfb": "ncaaf",
    "epl": "soccer", "laliga": "soccer", "bundesliga": "soccer",
    "ligue-1": "soccer", "mls": "soccer", "ucl": "soccer", "uel": "soccer",
    "bra": "soccer", "jap": "soccer", "kor": "soccer", "mex": "soccer",
    "ere": "soccer", "por": "soccer", "tur": "soccer", "nor": "soccer",
    "den": "soccer", "spl": "soccer", "ssc": "soccer", "aus": "soccer",
    "ruprem": "soccer", "ucol": "soccer", "sud": "soccer", "itc": "soccer",
    "lib": "soccer", "cdr": "soccer", "cde": "soccer", "dfb": "soccer",
    "caf": "soccer", "concacaf": "soccer", "conmebol": "soccer",
    "uef-qualifiers": "soccer", "afc-wc": "soccer", "fifa-friendlies": "soccer",
    "ja2": "soccer", "acn": "soccer", "csl": "soccer",
    "ahl": "nhl", "atp": "tennis", "wta": "tennis", "golf": "golf",
    "cricbbl": "cricket", "criccsat20w": "cricket", "cricipl": "cricket",
    "criclcl": "cricket", "cricpakt20cup": "cricket", "cricps": "cricket",
    "cricpsl": "cricket", "cricss": "cricket", "cricthunderbolt": "cricket",
    "cricwncl": "cricket", "crict20lpl": "cricket", "crichkt20w": "cricket",
    "crint": "cricket",
}

# Slugs that don't appear in DEFAULT_SPORT_SLUGS but existed in the taxonomy
EXTRA_SLUGS = [
    "chi1", "col1", "per1", "rou1", "cze1", "egy1", "mar1", "acn",
]


# ---------------------------------------------------------------------------
# Gamma API helpers
# ---------------------------------------------------------------------------
def _fetch_events(tag: str, *, ascending: bool = False, limit: int = 100) -> list[dict]:
    """Fetch closed events for a tag_slug, ordered by endDate."""
    params = {
        "tag_slug": tag,
        "closed": "true",
        "limit": limit,
        "order": "endDate",
        "ascending": "true" if ascending else "false",
    }
    try:
        data = get_json(f"{GAMMA_API}/events", params=params)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _fetch_active_count(tag: str) -> int:
    """Count active (non-closed) events for a tag_slug."""
    try:
        data = get_json(
            f"{GAMMA_API}/events",
            params={"tag_slug": tag, "closed": "false", "limit": 1},
        )
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def _detect_market_type(events: list[dict]) -> str | None:
    """Detect whether a slug uses H2H or 3-way draw markets."""
    for ev in events[:10]:
        markets = ev.get("markets", [])
        # H2H check
        for mkt in markets:
            if MarketFilter.is_head_to_head(mkt):
                return "h2h"
        # 3-way draw check
        draw_markets = [m for m in markets if m.get("groupItemTitle")]
        if len(draw_markets) == 3:
            draw_mkts = [
                m for m in draw_markets
                if "draw" in (m.get("groupItemTitle") or "").lower()
            ]
            if len(draw_mkts) == 1:
                return "draw"
    return None


def _extract_date(event: dict) -> str | None:
    """Extract YYYY-MM-DD from an event's endDate."""
    raw = event.get("endDate") or event.get("end_date") or ""
    if raw:
        return raw[:10]
    return None


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------
def scan_slug(slug: str) -> SlugInfo:
    """Scan a single slug and return its SlugInfo."""
    api_tag = resolve_tag_slug(slug)
    sport = SLUG_SPORT.get(slug, "unknown")
    espn = SLUG_ESPN.get(slug)
    now = datetime.now(timezone.utc).isoformat()

    info = SlugInfo(
        slug=slug,
        api_tag=api_tag,
        sport=sport,
        espn_sport=espn,
        updated_at=now,
    )

    # Fetch newest events
    newest = _fetch_events(api_tag, ascending=False, limit=30)
    if not newest:
        # Check if there are active events
        active = _fetch_active_count(api_tag)
        if active > 0:
            info.status = "active_only"
            info.event_count = 0
        else:
            info.status = "no_events"
        return info

    # Fetch oldest events
    oldest = _fetch_events(api_tag, ascending=True, limit=5)

    info.event_count = len(newest)  # approximate (capped at limit)

    # Dates
    if oldest:
        info.earliest_date = _extract_date(oldest[0])
    if newest:
        info.latest_date = _extract_date(newest[0])
        info.sample_title = newest[0].get("title", "")[:100]

    # Market type
    info.market_type = _detect_market_type(newest)

    if info.market_type:
        info.status = "active"
    else:
        info.status = "no_history"

    return info


def scan_all(slugs: list[str], existing: dict[str, SlugInfo] | None = None) -> dict[str, SlugInfo]:
    """Scan a list of slugs and return a fresh registry.

    If *existing* is provided, entries not being re-scanned are preserved.
    """
    registry: dict[str, SlugInfo] = dict(existing or {})

    total = len(slugs)
    active = 0
    for i, slug in enumerate(slugs):
        print(f"[{i + 1}/{total}] {slug:30s}", end=" ", flush=True)
        info = scan_slug(slug)
        registry[slug] = info

        if info.status == "active":
            active += 1
            date_range = ""
            if info.earliest_date and info.latest_date:
                date_range = f" ({info.earliest_date} → {info.latest_date})"
            print(
                f"— ✓ {info.market_type:5s} {info.event_count:3d} events{date_range}"
            )
        elif info.status == "active_only":
            print(f"— ⏳ active only (no resolved events)")
        elif info.status == "no_events":
            print(f"— ✗ no events")
        else:
            print(f"— ✗ {info.event_count} events, no matchup detected")

        time.sleep(0.2)  # polite rate limit

    return registry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Refresh the slug coverage registry by scanning the Gamma API.",
    )
    parser.add_argument(
        "--only", help="Comma-separated list of slugs to scan",
    )
    parser.add_argument(
        "--sport", help="Only scan slugs for this sport category",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print results without saving to disk",
    )
    parser.add_argument(
        "--include-extra", action="store_true",
        help="Also scan slugs not in DEFAULT_SPORT_SLUGS (e.g. chi1, col1)",
    )
    args = parser.parse_args()

    # Determine which slugs to scan
    if args.only:
        slugs = [s.strip() for s in args.only.split(",")]
    else:
        slugs = list(DEFAULT_SPORT_SLUGS)
        if args.include_extra:
            slugs.extend(s for s in EXTRA_SLUGS if s not in slugs)

    if args.sport:
        slugs = [s for s in slugs if SLUG_SPORT.get(s, "unknown") == args.sport]

    if not slugs:
        print("No slugs to scan.")
        return

    # Load existing registry to preserve un-scanned entries
    existing = load_registry() if not args.only else None

    print(f"Scanning {len(slugs)} slugs...\n")
    registry = scan_all(slugs, existing)

    # Summary
    active = sum(1 for s in registry.values() if s.status == "active")
    total = len(registry)

    # Date range stats
    dates = [s.earliest_date for s in registry.values() if s.earliest_date]
    earliest = min(dates) if dates else "?"
    latest_dates = [s.latest_date for s in registry.values() if s.latest_date]
    latest = max(latest_dates) if latest_dates else "?"

    # Sport breakdown
    sport_counts: dict[str, int] = {}
    for s in registry.values():
        if s.status == "active":
            sport_counts[s.sport] = sport_counts.get(s.sport, 0) + 1

    print(f"\n{'=' * 60}")
    print(f"  COVERAGE SUMMARY: {active}/{total} slugs active")
    print(f"  Backtest range:   {earliest} → {latest}")
    print()
    for sport, count in sorted(sport_counts.items(), key=lambda x: -x[1]):
        print(f"    {sport:15s}: {count} slugs")
    print(f"{'=' * 60}")

    if args.dry_run:
        print("\n[dry-run] Not saving to disk.")
    else:
        out = save_registry(registry)
        print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
