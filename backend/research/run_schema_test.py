"""
AROGYA research — schema and cost-log test script.

Run from the repo root as:
    python -m backend.research.run_schema_test

No pytest or third-party libraries used.
All file I/O goes to a temporary directory so the real results/ directory
is never touched.
"""

from __future__ import annotations

import csv
import math
import sys
import tempfile
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the modules under test
# ---------------------------------------------------------------------------
from backend.research.harness.schema import validate_row, write_jsonl, read_jsonl
from backend.research.harness.cost_log import append_cost

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASS_COUNT = 0
_FAIL_COUNT = 0


def _report(label: str, passed: bool, detail: str = "") -> None:
    global _PASS_COUNT, _FAIL_COUNT
    if passed:
        _PASS_COUNT += 1
        print(f"PASS  {label}")
    else:
        _FAIL_COUNT += 1
        print(f"FAIL  {label}")
        if detail:
            for line in detail.splitlines():
                print(f"      {line}")


def _assert(label: str, condition: bool, detail: str = "") -> None:
    _report(label, condition, detail)


def _assert_raises(label: str, exc_type: type, fn) -> None:
    try:
        fn()
        _report(label, False, f"Expected {exc_type.__name__} but no exception was raised")
    except exc_type:
        _report(label, True)
    except Exception as exc:  # noqa: BLE001
        _report(label, False, f"Expected {exc_type.__name__}, got {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# A canonical valid row (obviously made-up data)
# ---------------------------------------------------------------------------

_VALID_ROW = {
    "run_id": "run-abc-001",
    "timestamp_utc": "2026-01-15T08:30:00+00:00",
    "part": "A",
    "question_id": "Q001",
    "lang": "en",
    "mode": "lab",
    "data_condition": "correct",
    "instruction_condition": "normal",
    "ml_strategy": "na",
    "model": "gpt-fake-mini",
    "model_version": "2026-01-01",
    "translator": "none",
    "temperature": 0.0,
    "prompt_snapshot_commit": "abc1234",
    "guard": "off",
    "repeat_index": 0,
    "answer_text": "The clinic opens at 9 am.",
    "score_label": "follows_data",
    "tokens_in": 120,
    "tokens_out": 30,
    "cost_usd": 0.0001,
}


def _valid_row(**overrides) -> dict:
    """Return a copy of the valid row with *overrides* applied."""
    row = dict(_VALID_ROW)
    row.update(overrides)
    return row


def _valid_row_without(*fields) -> dict:
    """Return a copy of the valid row with *fields* removed."""
    row = dict(_VALID_ROW)
    for f in fields:
        row.pop(f, None)
    return row


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

def test_valid_row_passes():
    """(a) One valid row produces an empty error list."""
    errs = validate_row(_VALID_ROW)
    _assert(
        "valid_row_passes",
        errs == [],
        f"Unexpected errors: {errs}",
    )


def test_broken_rows():
    """(b) Six categories of broken rows each fail with a clear message."""

    # (1) A required field is missing — remove 'timestamp_utc'
    row1 = _valid_row_without("timestamp_utc")
    errs1 = validate_row(row1)
    passed1 = any("timestamp_utc" in e and "missing" in e for e in errs1)
    _assert(
        "broken_missing_field",
        passed1,
        f"errors were: {errs1}",
    )

    # (2) An unknown extra field
    row2 = _valid_row(unknown_extra_field="oops")
    errs2 = validate_row(row2)
    passed2 = any("unknown_extra_field" in e and "unknown" in e for e in errs2)
    _assert(
        "broken_extra_field",
        passed2,
        f"errors were: {errs2}",
    )

    # (3) lang = "fr"
    row3 = _valid_row(lang="fr")
    errs3 = validate_row(row3)
    passed3 = any("lang" in e and "fr" in e for e in errs3)
    _assert(
        "broken_lang_fr",
        passed3,
        f"errors were: {errs3}",
    )

    # (4) score_label = "hallucinated"
    row4 = _valid_row(score_label="hallucinated")
    errs4 = validate_row(row4)
    passed4 = any("score_label" in e and "hallucinated" in e for e in errs4)
    _assert(
        "broken_score_label_hallucinated",
        passed4,
        f"errors were: {errs4}",
    )

    # (5a) tokens_in as a string
    row5a = _valid_row(tokens_in="100")
    errs5a = validate_row(row5a)
    passed5a = any("tokens_in" in e for e in errs5a)
    _assert(
        "broken_tokens_in_string",
        passed5a,
        f"errors were: {errs5a}",
    )

    # (5b) tokens_in = True  (bool must NOT be accepted as int)
    row5b = _valid_row(tokens_in=True)
    errs5b = validate_row(row5b)
    passed5b = any("tokens_in" in e for e in errs5b)
    _assert(
        "broken_tokens_in_bool",
        passed5b,
        f"errors were: {errs5b}",
    )

    # (6) negative cost_usd
    row6 = _valid_row(cost_usd=-0.5)
    errs6 = validate_row(row6)
    passed6 = any("cost_usd" in e for e in errs6)
    _assert(
        "broken_negative_cost_usd",
        passed6,
        f"errors were: {errs6}",
    )

    # Bonus: bad timestamp (naive — no UTC offset)
    rowT = _valid_row(timestamp_utc="2026-01-15T08:30:00")
    errsT = validate_row(rowT)
    passedT = any("timestamp_utc" in e for e in errsT)
    _assert(
        "broken_naive_timestamp",
        passedT,
        f"errors were: {errsT}",
    )


def test_roundtrip_malayalam(tmp_dir: Path):
    """(c) write_jsonl then read_jsonl round-trips a row with Malayalam text."""
    ml_answer = "ക്ലിനിക്ക് രാവിലെ 9 മണിക്ക് തുറക്കുന്നു."
    row = _valid_row(lang="ml", answer_text=ml_answer)
    outfile = tmp_dir / "roundtrip.jsonl"

    write_jsonl(str(outfile), [row])
    loaded = read_jsonl(str(outfile))

    passed = (
        len(loaded) == 1
        and loaded[0]["answer_text"] == ml_answer
        and loaded[0]["lang"] == "ml"
    )
    _assert(
        "roundtrip_malayalam_answer_text",
        passed,
        f"answer_text back: {loaded[0]['answer_text']!r}" if loaded else "no rows loaded",
    )


def test_write_jsonl_partial_invalid(tmp_dir: Path):
    """(d) write_jsonl with one valid + one invalid row writes NOTHING."""
    valid_row = _valid_row()
    invalid_row = _valid_row(lang="fr")  # bad enum value

    outfile = tmp_dir / "partial_invalid.jsonl"

    raised = False
    try:
        write_jsonl(str(outfile), [valid_row, invalid_row])
    except ValueError:
        raised = True

    # The file must not exist (or be empty) because validation aborted the write.
    file_empty = not outfile.exists() or outfile.stat().st_size == 0
    _assert(
        "write_jsonl_partial_invalid_raises",
        raised,
        "ValueError was not raised",
    )
    _assert(
        "write_jsonl_partial_invalid_no_output",
        file_empty,
        f"File exists and has {outfile.stat().st_size if outfile.exists() else 0} bytes",
    )


def test_cost_log(tmp_dir: Path):
    """(e) Cost log: header written once across two appends; negative cost raises."""
    log_path = tmp_dir / "test_cost_log.csv"

    # First append.
    append_cost(
        date="2026-01-15",
        run_id="run-001",
        model="gpt-fake-mini",
        calls=10,
        tokens=500,
        cost=0.0025,
        approved_by="researcher-A",
        path=str(log_path),
    )

    # Second append.
    append_cost(
        date="2026-01-16",
        run_id="run-002",
        model="gpt-fake-mini",
        calls=5,
        tokens=250,
        cost=0.0012,
        approved_by="researcher-A",
        path=str(log_path),
    )

    # Read back and check: header appears exactly once, two data rows.
    with open(log_path, "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))

    header_rows = [r for r in rows if r == ["date", "run_id", "model", "calls", "tokens", "cost", "approved_by"]]
    _assert(
        "cost_log_header_once",
        len(header_rows) == 1,
        f"Header appears {len(header_rows)} times in: {rows}",
    )
    _assert(
        "cost_log_two_data_rows",
        len(rows) == 3,  # 1 header + 2 data
        f"Total rows: {len(rows)}, contents: {rows}",
    )

    # Negative cost must raise ValueError.
    _assert_raises(
        "cost_log_negative_cost_raises",
        ValueError,
        lambda: append_cost(
            date="2026-01-17",
            run_id="run-003",
            model="gpt-fake-mini",
            calls=1,
            tokens=50,
            cost=-0.001,
            approved_by="researcher-A",
            path=str(log_path),
        ),
    )


# ---------------------------------------------------------------------------
# New tests (Fix 7)
# ---------------------------------------------------------------------------

def test_enum_non_string_values():
    """lang=None and lang=5 must each produce an error naming 'lang'."""
    # lang = None
    row_none = _valid_row(lang=None)
    errs_none = validate_row(row_none)
    passed_none = any("lang" in e for e in errs_none)
    _assert(
        "lang_none_fails",
        passed_none,
        f"errors were: {errs_none}",
    )

    # lang = 5 (integer)
    row_int = _valid_row(lang=5)
    errs_int = validate_row(row_int)
    passed_int = any("lang" in e for e in errs_int)
    _assert(
        "lang_int_fails",
        passed_int,
        f"errors were: {errs_int}",
    )

    # score_label = ["x"]  (a list — not a string)
    row_list = _valid_row(score_label=["x"])
    errs_list = validate_row(row_list)
    passed_list = any("score_label" in e for e in errs_list)
    _assert(
        "score_label_list_fails",
        passed_list,
        f"errors were: {errs_list}",
    )


def test_nan_inf_numeric():
    """temperature=NaN and cost_usd=inf must each produce an error."""
    # temperature = NaN
    row_nan = _valid_row(temperature=math.nan)
    errs_nan = validate_row(row_nan)
    passed_nan = any("temperature" in e for e in errs_nan)
    _assert(
        "temperature_nan_fails",
        passed_nan,
        f"errors were: {errs_nan}",
    )

    # cost_usd = +infinity
    row_inf = _valid_row(cost_usd=math.inf)
    errs_inf = validate_row(row_inf)
    passed_inf = any("cost_usd" in e for e in errs_inf)
    _assert(
        "cost_usd_inf_fails",
        passed_inf,
        f"errors were: {errs_inf}",
    )


def test_whitespace_only_run_id():
    """run_id that is only whitespace must fail."""
    row = _valid_row(run_id="   ")
    errs = validate_row(row)
    passed = any("run_id" in e for e in errs)
    _assert(
        "whitespace_only_run_id_fails",
        passed,
        f"errors were: {errs}",
    )


def test_cost_log_nan_raises(tmp_dir: Path):
    """append_cost with NaN cost must raise ValueError."""
    _assert_raises(
        "cost_log_nan_cost_raises",
        ValueError,
        lambda: append_cost(
            date="2026-01-20",
            run_id="run-nan",
            model="gpt-fake-mini",
            calls=1,
            tokens=10,
            cost=math.nan,
            approved_by="researcher-A",
            path=str(tmp_dir / "nan_cost_log.csv"),
        ),
    )


def test_cost_log_bad_date_raises(tmp_dir: Path):
    """append_cost with non-zero-padded date '2026-1-5' must raise ValueError."""
    _assert_raises(
        "cost_log_bad_date_raises",
        ValueError,
        lambda: append_cost(
            date="2026-1-5",
            run_id="run-baddate",
            model="gpt-fake-mini",
            calls=1,
            tokens=10,
            cost=0.001,
            approved_by="researcher-A",
            path=str(tmp_dir / "bad_date_log.csv"),
        ),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        test_valid_row_passes()
        test_broken_rows()
        test_roundtrip_malayalam(tmp_dir)
        test_write_jsonl_partial_invalid(tmp_dir)
        test_cost_log(tmp_dir)
        # New tests (Fix 7)
        test_enum_non_string_values()
        test_nan_inf_numeric()
        test_whitespace_only_run_id()
        test_cost_log_nan_raises(tmp_dir)
        test_cost_log_bad_date_raises(tmp_dir)

    total = _PASS_COUNT + _FAIL_COUNT
    print(f"\n{_PASS_COUNT} passed, {_FAIL_COUNT} failed (of {total})")
    return 0 if _FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
