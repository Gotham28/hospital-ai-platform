"""
AROGYA research harness — cost logger.

Appends one CSV row per LLM run to backend/research/results/cost_log.csv.
The results/ directory and the CSV header are created on first use.

No third-party dependencies — standard library only.
"""

from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path

# Default path resolved relative to *this file*, not the CWD.
_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent / "results" / "cost_log.csv"
)

_HEADER = ["date", "run_id", "model", "calls", "tokens", "cost", "approved_by"]

# Strict YYYY-MM-DD pattern: four digits, dash, exactly two digits, dash,
# exactly two digits.  Rejects "2026-1-5" and similar non-zero-padded strings.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def append_cost(
    date: str,
    run_id: str,
    model: str,
    calls: int,
    tokens: int,
    cost: float,
    approved_by: str,
    path: str | os.PathLike | None = None,
) -> None:
    """Append one cost row to the cost log CSV.

    Parameters
    ----------
    date:
        Date string in strictly zero-padded YYYY-MM-DD format
        (e.g. "2026-01-05", not "2026-1-5").
    run_id:
        Non-empty, non-whitespace-only identifier for the benchmark run.
    model:
        Non-empty, non-whitespace-only model name/identifier.
    calls:
        Number of API calls made (int >= 0).
    tokens:
        Total tokens consumed (int >= 0).
    cost:
        Total cost in USD (finite number >= 0; bool not accepted).
    approved_by:
        Non-empty, non-whitespace-only string identifying who approved the spend.
    path:
        Path to the CSV file.  Defaults to
        ``backend/research/results/cost_log.csv`` resolved from the package
        location.  The parent directory is created if it does not exist.
    """
    # --- Validate inputs ---------------------------------------------------

    # Non-empty, non-whitespace-only string checks.
    for name, value in (
        ("run_id", run_id),
        ("model", model),
        ("approved_by", approved_by),
    ):
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(
                f"{name}: must be a non-empty, non-whitespace-only string, "
                f"got {value!r}"
            )

    # date must match YYYY-MM-DD with strict zero-padding, and be a real date.
    if not isinstance(date, str) or not _DATE_RE.match(date):
        raise ValueError(
            f"date: must be a zero-padded YYYY-MM-DD string (e.g. '2026-01-05'), "
            f"got {date!r}"
        )
    # Verify the date is actually valid (e.g. reject "2026-02-30").
    try:
        # strftime on a parsed date reproduces the zero-padded form; comparing
        # it back to the input catches any mismatch that slipped through the regex.
        from datetime import datetime as _dt
        parsed = _dt.strptime(date, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != date:
            raise ValueError()
    except ValueError:
        raise ValueError(
            f"date: must be a valid zero-padded YYYY-MM-DD string, got {date!r}"
        )

    # calls and tokens: int >= 0, bool excluded.
    for name, value in (("calls", calls), ("tokens", tokens)):
        if type(value) is bool or not isinstance(value, int):  # noqa: E721
            raise ValueError(
                f"{name}: expected int >= 0 (bool not accepted), "
                f"got {type(value).__name__}"
            )
        if value < 0:
            raise ValueError(f"{name}: must be >= 0, got {value!r}")

    # cost: finite number >= 0, bool excluded.
    if type(cost) is bool or not isinstance(cost, (int, float)):  # noqa: E721
        raise ValueError(
            f"cost: expected number >= 0 (bool not accepted), "
            f"got {type(cost).__name__}"
        )
    if not math.isfinite(cost):
        raise ValueError(
            f"cost: must be a finite number (NaN and infinity are not accepted), "
            f"got {cost!r}"
        )
    if cost < 0:
        raise ValueError(f"cost: must be >= 0, got {cost!r}")

    # --- Resolve path and ensure directory exists -------------------------

    target = Path(path) if path is not None else _DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    # --- Write header once, then append the data row ----------------------

    write_header = not target.exists() or target.stat().st_size == 0

    with open(target, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(_HEADER)
        writer.writerow([date, run_id, model, calls, tokens, cost, approved_by])
