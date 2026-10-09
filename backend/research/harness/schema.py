"""
AROGYA research harness — result row schema, validator, and JSONL I/O.

Allowed field values are exposed as module-level constants so experiment
scripts can reference them without hard-coding strings.

No third-party dependencies — standard library only.
"""

from __future__ import annotations

import json
import math
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Allowed-value sets (module-level constants — do not rename or reorder)
# ---------------------------------------------------------------------------

PARTS = {"A", "B", "C", "D"}
LANGS = {"en", "ml"}
MODES = {"lab", "system"}
DATA_CONDITIONS = {"none", "correct", "altered_h", "altered_m"}
INSTRUCTION_CONDITIONS = {"none", "normal", "conflict", "other_tenant", "trick"}
ML_STRATEGIES = {"direct", "bridge", "na"}
GUARDS = {"off", "on", "baseline"}
SCORE_LABELS = {
    "follows_data",
    "contradicts_data",
    "follows_instruction",
    "abstains",
    "invents",
    "unclear",
}

# The complete, ordered list of required fields (exactly 21).
_REQUIRED_FIELDS = [
    "run_id",
    "timestamp_utc",
    "part",
    "question_id",
    "lang",
    "mode",
    "data_condition",
    "instruction_condition",
    "ml_strategy",
    "model",
    "model_version",
    "translator",
    "temperature",
    "prompt_snapshot_commit",
    "guard",
    "repeat_index",
    "answer_text",
    "score_label",
    "tokens_in",
    "tokens_out",
    "cost_usd",
]

# Fields that must be non-empty, non-whitespace-only strings.
_NONEMPTY_STRING_FIELDS = {
    "run_id",
    "question_id",
    "model",
    "model_version",
    "translator",
    "prompt_snapshot_commit",
}

# Fields that are non-negative integers (bool counts as NOT int per spec).
_NON_NEG_INT_FIELDS = {"repeat_index", "tokens_in", "tokens_out"}

# Fields that are non-negative, finite numbers (bool counts as NOT number per spec).
_NON_NEG_NUM_FIELDS = {"temperature", "cost_usd"}

# Enum-constrained fields mapped to their allowed sets.
_ENUM_FIELDS: dict[str, set[str]] = {
    "part": PARTS,
    "lang": LANGS,
    "mode": MODES,
    "data_condition": DATA_CONDITIONS,
    "instruction_condition": INSTRUCTION_CONDITIONS,
    "ml_strategy": ML_STRATEGIES,
    "guard": GUARDS,
    "score_label": SCORE_LABELS,
}


# ---------------------------------------------------------------------------
# Dataclass record
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ResultRow:
    """One benchmark result row.  All 21 fields are required."""

    run_id: str
    timestamp_utc: str
    part: str
    question_id: str
    lang: str
    mode: str
    data_condition: str
    instruction_condition: str
    ml_strategy: str
    model: str
    model_version: str
    translator: str
    temperature: float
    prompt_snapshot_commit: str
    guard: str
    repeat_index: int
    answer_text: str
    score_label: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def _is_bool(value: Any) -> bool:
    """Return True if *value* is exactly a bool (bool is a subclass of int)."""
    return type(value) is bool  # noqa: E721  — deliberate isinstance-bypass


def _parse_utc_timestamp(value: Any) -> bool:
    """Return True if *value* is a string that parses as a UTC datetime.

    Accepts trailing 'Z' or '+00:00'.  Rejects naive times and any other
    offset.
    """
    if not isinstance(value, str) or _is_bool(value):
        return False
    # Normalise 'Z' suffix so fromisoformat handles it on Python < 3.11.
    normalised = value.rstrip()
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalised)
    except ValueError:
        return False
    # Must be timezone-aware and UTC.
    if dt.tzinfo is None:
        return False
    offset = dt.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        return False
    return True


def validate_row(row: dict) -> list[str]:
    """Validate *row* against the result-row contract.

    Returns an empty list if the row is valid, or a list of human-readable
    error strings (each naming the offending field) if it is not.
    """
    errors: list[str] = []

    if not isinstance(row, dict):
        return ["row is not a dict"]

    row_keys = set(row.keys())
    required_keys = set(_REQUIRED_FIELDS)

    # Missing fields.
    for field in _REQUIRED_FIELDS:
        if field not in row:
            errors.append(f"{field}: missing required field")

    # Unknown extra fields.
    for key in sorted(row_keys - required_keys):
        errors.append(f"{key}: unknown field not in schema")

    # If any field is missing we cannot safely check types — return early so
    # subsequent checks don't raise KeyError.
    if errors:
        return errors

    # Non-empty, non-whitespace-only string fields.
    for field in _NONEMPTY_STRING_FIELDS:
        value = row[field]
        if not isinstance(value, str) or _is_bool(value):
            errors.append(
                f"{field}: expected a non-empty string, got {type(value).__name__}"
            )
        elif value.strip() == "":
            errors.append(f"{field}: must not be empty or whitespace-only")

    # answer_text — string (empty allowed).
    if not isinstance(row["answer_text"], str) or _is_bool(row["answer_text"]):
        errors.append(
            f"answer_text: expected a string, got {type(row['answer_text']).__name__}"
        )

    # timestamp_utc.
    if not _parse_utc_timestamp(row["timestamp_utc"]):
        errors.append(
            "timestamp_utc: must be an ISO-8601 string with UTC offset "
            "(trailing 'Z' or '+00:00'); naive times and other offsets are rejected "
            f"(got {row['timestamp_utc']!r})"
        )

    # Non-negative integer fields (bool excluded).
    for field in _NON_NEG_INT_FIELDS:
        value = row[field]
        if _is_bool(value) or not isinstance(value, int):
            errors.append(
                f"{field}: expected int >= 0 (bool is not accepted), "
                f"got {type(value).__name__}"
            )
        elif value < 0:
            errors.append(f"{field}: must be >= 0, got {value!r}")

    # Non-negative, finite numeric fields (bool excluded).
    for field in _NON_NEG_NUM_FIELDS:
        value = row[field]
        if _is_bool(value) or not isinstance(value, (int, float)):
            errors.append(
                f"{field}: expected number >= 0 (bool is not accepted), "
                f"got {type(value).__name__}"
            )
        elif not math.isfinite(value):
            errors.append(
                f"{field}: must be a finite number (NaN and infinity are not accepted), "
                f"got {value!r}"
            )
        elif value < 0:
            errors.append(f"{field}: must be >= 0, got {value!r}")

    # Enum-constrained fields.
    for field, allowed in _ENUM_FIELDS.items():
        value = row.get(field)
        if not isinstance(value, str) or _is_bool(value):
            errors.append(
                f"{field}: expected a string, got {type(value).__name__}"
            )
        elif value not in allowed:
            errors.append(
                f"{field}: {value!r} is not one of {sorted(allowed)}"
            )

    return errors


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------

def write_jsonl(path: str | Any, rows: list[dict]) -> None:
    """Validate all *rows* then write them to *path* as UTF-8 JSONL.

    If any row is invalid, nothing is written and ``ValueError`` is raised
    with the row index and the list of errors for that row.  The parent
    directory is created if it does not exist.
    """
    # Validate first — write nothing if any row is bad.
    for idx, row in enumerate(rows):
        errs = validate_row(row)
        if errs:
            raise ValueError(
                f"Row {idx} is invalid:\n" + "\n".join(f"  {e}" for e in errs)
            )

    # All rows valid — ensure parent directory exists, then write.
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Any) -> list[dict]:
    """Read JSONL from *path*, validate every line, and return list of dicts.

    Raises ``ValueError`` with the 1-based line number on any invalid line.
    """
    results: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line.strip():
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Line {lineno}: JSON parse error — {exc}"
                ) from exc
            errs = validate_row(obj)
            if errs:
                raise ValueError(
                    f"Line {lineno}: invalid row:\n"
                    + "\n".join(f"  {e}" for e in errs)
                )
            results.append(obj)
    return results
