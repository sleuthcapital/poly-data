"""Convenience I/O — save/load events, snapshots, trades as JSON or Parquet."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def save_json(data: Any, path: str | Path) -> Path:
    """Write *data* as pretty-printed JSON to *path* (creating dirs as needed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def append_jsonl(record: dict, path: str | Path) -> Path:
    """Append a single JSON record to a JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return path


def load_json(path: str | Path) -> Any:
    """Read and parse a JSON file."""
    return json.loads(Path(path).read_text())


def load_jsonl(path: str | Path) -> list[dict]:
    """Read all records from a JSONL file."""
    records = []
    with Path(path).open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Parquet helpers
# ---------------------------------------------------------------------------
def save_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    """Write a DataFrame to Parquet (creating dirs as needed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def load_parquet(path: str | Path) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame."""
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Batch loaders (scan directories)
# ---------------------------------------------------------------------------
def load_games_from_dir(directory: str | Path) -> list[dict]:
    """Load all ``*.json`` game files from a directory."""
    directory = Path(directory)
    games = []
    for p in sorted(directory.glob("*.json")):
        try:
            games.append(json.loads(p.read_text()))
        except Exception:
            logger.warning("Failed to load %s", p, exc_info=True)
    return games


def load_trades_from_dir(directory: str | Path) -> dict[str, list[dict]]:
    """Load all ``*_trades.json`` files from a directory.

    Returns a dict keyed by condition_id.
    """
    directory = Path(directory)
    result: dict[str, list[dict]] = {}
    for p in sorted(directory.glob("*_trades.json")):
        condition_id = p.stem.replace("_trades", "")
        try:
            result[condition_id] = json.loads(p.read_text())
        except Exception:
            logger.warning("Failed to load %s", p, exc_info=True)
    return result
