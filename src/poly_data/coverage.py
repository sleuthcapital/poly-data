"""Slug coverage registry — tracks which leagues have backtesting data.

The registry is stored as a JSON file (``coverage_data.json``) next to this
module and is refreshed by ``scripts/update_coverage.py``.  Library users
can query it without any API calls:

    >>> from poly_data.coverage import load_registry, coverage_df
    >>> reg = load_registry()
    >>> reg["nba"].earliest_date
    '2024-10-22'
    >>> df = coverage_df()
    >>> df[df["status"] == "active"].shape[0]
    85
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).with_name("coverage_data.json")


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------
@dataclass
class SlugInfo:
    """Metadata for a single Polymarket sport slug."""

    slug: str
    """Frontend URL slug (e.g. ``"laliga"``)."""

    api_tag: str
    """Resolved Gamma API ``tag_slug`` (e.g. ``"la-liga"``)."""

    sport: str
    """High-level sport category (``soccer``, ``basketball``, …)."""

    market_type: str | None = None
    """``"h2h"`` (2-outcome), ``"draw"`` (3-way), or *None*."""

    status: str = "unknown"
    """One of ``active`` · ``no_history`` · ``no_events`` · ``active_only`` · ``unknown``."""

    espn_sport: str | None = None
    """ESPN sport key for game-time matching, or *None*."""

    earliest_date: str | None = None
    """ISO date of the earliest resolved event (``YYYY-MM-DD``)."""

    latest_date: str | None = None
    """ISO date of the most recent resolved event (``YYYY-MM-DD``)."""

    event_count: int = 0
    """Total number of resolved events found."""

    sample_title: str | None = None
    """Example event title for quick identification."""

    updated_at: str | None = None
    """ISO timestamp of when this entry was last refreshed."""


# ------------------------------------------------------------------
# Registry I/O
# ------------------------------------------------------------------
def load_registry(path: str | Path | None = None) -> dict[str, SlugInfo]:
    """Load the coverage registry from disk.

    Parameters
    ----------
    path : str or Path, optional
        Override the default JSON file path.

    Returns
    -------
    dict[str, SlugInfo]
        Mapping from slug name to :class:`SlugInfo`.
    """
    p = Path(path) if path else _DATA_FILE
    if not p.exists():
        logger.warning("Coverage data not found at %s — returning empty registry", p)
        return {}

    with open(p, "r") as f:
        raw = json.load(f)

    registry: dict[str, SlugInfo] = {}
    for slug, info in raw.get("slugs", {}).items():
        registry[slug] = SlugInfo(
            slug=slug,
            api_tag=info.get("api_tag", slug),
            sport=info.get("sport", "unknown"),
            market_type=info.get("market_type"),
            status=info.get("status", "unknown"),
            espn_sport=info.get("espn_sport"),
            earliest_date=info.get("earliest_date"),
            latest_date=info.get("latest_date"),
            event_count=info.get("event_count", 0),
            sample_title=info.get("sample_title"),
            updated_at=info.get("updated_at"),
        )
    return registry


def save_registry(
    registry: dict[str, SlugInfo],
    path: str | Path | None = None,
) -> Path:
    """Persist the registry to disk as JSON.

    Parameters
    ----------
    registry : dict[str, SlugInfo]
        The slug registry to save.
    path : str or Path, optional
        Override the default JSON file path.

    Returns
    -------
    Path
        The file that was written.
    """
    p = Path(path) if path else _DATA_FILE
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_slugs": len(registry),
        "active_slugs": sum(1 for s in registry.values() if s.status == "active"),
        "slugs": {
            slug: {k: v for k, v in asdict(info).items() if k != "slug"}
            for slug, info in sorted(registry.items())
        },
    }
    with open(p, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return p


# ------------------------------------------------------------------
# Convenience helpers
# ------------------------------------------------------------------
def coverage_df():
    """Return the coverage registry as a pandas DataFrame.

    Columns: slug, api_tag, sport, market_type, status, espn_sport,
    earliest_date, latest_date, event_count, sample_title, updated_at.
    """
    import pandas as pd

    reg = load_registry()
    if not reg:
        return pd.DataFrame()
    rows = [asdict(info) for info in reg.values()]
    df = pd.DataFrame(rows)
    # Sort by sport, then slug
    return df.sort_values(["sport", "slug"]).reset_index(drop=True)


def active_slugs() -> list[str]:
    """Return slugs that have confirmed backtesting data."""
    reg = load_registry()
    return sorted(s for s, info in reg.items() if info.status == "active")


def slugs_by_sport(sport: str) -> list[SlugInfo]:
    """Return all slug entries for a given sport category."""
    reg = load_registry()
    return [info for info in reg.values() if info.sport == sport]


def coverage_summary() -> str:
    """Return a human-readable coverage summary string."""
    reg = load_registry()
    if not reg:
        return "No coverage data found. Run: python scripts/update_coverage.py"

    by_status: dict[str, int] = {}
    by_sport: dict[str, list[str]] = {}
    for info in reg.values():
        by_status[info.status] = by_status.get(info.status, 0) + 1
        if info.status == "active":
            by_sport.setdefault(info.sport, []).append(info.slug)

    lines = [
        f"Coverage Registry — {len(reg)} slugs total",
        "=" * 50,
    ]
    for status, count in sorted(by_status.items()):
        lines.append(f"  {status:15s}: {count}")
    lines.append("")

    if by_sport:
        lines.append("Active slugs by sport:")
        for sport in sorted(by_sport):
            slugs = by_sport[sport]
            lines.append(f"  {sport} ({len(slugs)}): {', '.join(sorted(slugs))}")

    # Date range
    earliest = min(
        (info.earliest_date for info in reg.values() if info.earliest_date),
        default=None,
    )
    latest = max(
        (info.latest_date for info in reg.values() if info.latest_date),
        default=None,
    )
    if earliest and latest:
        lines.append(f"\nBacktest date range: {earliest} → {latest}")

    return "\n".join(lines)
