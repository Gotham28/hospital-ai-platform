#!/usr/bin/env python3
"""
Fixture validator for AROGYA research test hospitals.

Checks both hospital_a.json and hospital_b.json for structural integrity,
value-format correctness, cross-file uniqueness, and the presence of the
five deliberate overlaps required by M-03.

Usage (from the repository root):
    python -m backend.research.fixtures.validate_fixtures

Exit code:
    0 — all checks PASS
    1 — one or more checks FAIL
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent
FACT_ID_RE = re.compile(r"^([AB])-([A-Z]+)-(\d{3})$")
VALID_DAYS = frozenset({"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"})
NUMERIC_ATTRS = frozenset({"price_inr", "fasting_hours", "turnaround_hours"})
REQUIRED_FIELDS = frozenset({"fact_id", "category", "statement", "attribute", "value"})
MIN_FACTS = 55
MAX_FACTS = 65

FILES = [
    ("hospital_a", FIXTURES_DIR / "hospital_a.json", "A"),
    ("hospital_b", FIXTURES_DIR / "hospital_b.json", "B"),
]

# Days in the canonical Mon-Sun order used for exact-match overlap checks.
_ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hhmm(t):
    """Return minutes-from-midnight for an 'HH:MM' string, or raise ValueError."""
    parts = str(t).split(":")
    if len(parts) != 2:
        raise ValueError("bad time format: {!r}".format(t))
    return int(parts[0]) * 60 + int(parts[1])


def _check_time_value(v):
    """Return an error string, or None if the time-range dict is valid."""
    if not isinstance(v, dict):
        return "value is not a dict"
    missing = {"start", "end", "days"} - set(v)
    if missing:
        return "missing keys: {}".format(sorted(missing))
    try:
        start = _parse_hhmm(v["start"])
        end = _parse_hhmm(v["end"])
    except (ValueError, TypeError) as exc:
        return "time parse error: {}".format(exc)
    if start >= end:
        return "start {!r} >= end {!r}".format(v["start"], v["end"])
    if not isinstance(v["days"], list) or not v["days"]:
        return "days must be a non-empty list"
    bad = [d for d in v["days"] if d not in VALID_DAYS]
    if bad:
        return "invalid day names: {}".format(bad)
    return None


def _has(facts, attribute, value, name_substr=""):
    """
    Return True if any fact in *facts* matches all criteria:
      - f["attribute"] == attribute
      - f["value"] == value
      - name_substr in f["statement"]  (only checked when name_substr is non-empty)
    """
    for f in facts:
        if f.get("attribute") != attribute:
            continue
        if name_substr and name_substr not in f.get("statement", ""):
            continue
        if f.get("value") == value:
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pass_count = 0
    fail_count = 0

    def check(label, passed, detail=""):
        nonlocal pass_count, fail_count
        tag = "PASS" if passed else "FAIL"
        line = "  [{}] {}".format(tag, label)
        if detail:
            line += "  ({})".format(detail)
        print(line)
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        return passed

    all_ids = {}   # fact_id -> first filename that claimed it
    loaded = {}    # file_key -> list[dict]

    # ------------------------------------------------------------------
    # Per-file checks
    # ------------------------------------------------------------------
    for file_key, path, prefix in FILES:
        print("\n=== {} ===".format(path.name))

        # 1. Valid JSON
        data = None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            check("valid JSON", True)
        except Exception as exc:
            check("valid JSON", False, str(exc))
            continue

        facts = data.get("facts", [])
        loaded[file_key] = facts

        # 2. Fact count in [MIN_FACTS, MAX_FACTS]
        n = len(facts)
        check(
            "fact count in [{}, {}]".format(MIN_FACTS, MAX_FACTS),
            MIN_FACTS <= n <= MAX_FACTS,
            "{} facts".format(n),
        )

        # 3. Required fields present on every fact
        missing_fields = [
            (f.get("fact_id", "?"), sorted(REQUIRED_FIELDS - set(f)))
            for f in facts
            if not REQUIRED_FIELDS <= set(f)
        ]
        check(
            "required fields present on all facts",
            not missing_fields,
            "{} offenders: {}".format(len(missing_fields), missing_fields[:3])
            if missing_fields else "",
        )

        # 4. fact_id format and correct prefix
        bad_fmt = [
            f.get("fact_id", "")
            for f in facts
            if not FACT_ID_RE.fullmatch(f.get("fact_id", ""))
            or not f.get("fact_id", "").startswith(prefix + "-")
        ]
        check(
            "fact_id format ^{}-[A-Z]+-\\d{{3}}$".format(prefix),
            not bad_fmt,
            "bad IDs: {}".format(bad_fmt[:5]) if bad_fmt else "",
        )

        # 5. fact_id unique within file
        seen = set()
        dups = []
        for f in facts:
            fid = f.get("fact_id", "")
            if fid in seen:
                dups.append(fid)
            seen.add(fid)
        check(
            "fact_id unique within file",
            not dups,
            "duplicates: {}".format(dups) if dups else "",
        )

        # Accumulate IDs for cross-file uniqueness check
        for fid in seen:
            if fid in all_ids:
                all_ids[fid] = "{}, {}".format(all_ids[fid], file_key)
            else:
                all_ids[fid] = file_key

        # 6. Time-range values: start < end
        time_errs = []
        for f in facts:
            v = f.get("value")
            if isinstance(v, dict) and ("start" in v or "end" in v):
                err = _check_time_value(v)
                if err:
                    time_errs.append((f.get("fact_id"), err))
        check(
            "time ranges valid (start < end)",
            not time_errs,
            "{} errors: {}".format(len(time_errs), time_errs[:3]) if time_errs else "",
        )

        # 7. Day names are valid Mon–Sun
        day_errs = []
        for f in facts:
            v = f.get("value")
            if isinstance(v, dict) and "days" in v:
                bad_days = [d for d in v.get("days", []) if d not in VALID_DAYS]
                if bad_days:
                    day_errs.append((f.get("fact_id"), bad_days))
        check(
            "day names are valid (Mon–Sun)",
            not day_errs,
            "{} errors: {}".format(len(day_errs), day_errs[:3]) if day_errs else "",
        )

        # 8. Numeric attributes are numbers >= 0
        num_errs = []
        for f in facts:
            if f.get("attribute") in NUMERIC_ATTRS:
                v = f.get("value")
                if not isinstance(v, (int, float)) or v < 0:
                    num_errs.append((f.get("fact_id"), v))
        check(
            "numeric attributes (price_inr / fasting_hours / turnaround_hours) >= 0",
            not num_errs,
            "bad values: {}".format(num_errs) if num_errs else "",
        )

    # ------------------------------------------------------------------
    # Cross-file checks
    # ------------------------------------------------------------------
    print("\n=== Cross-file checks ===")

    # 9. fact_id unique across both files
    cross_dups = {
        fid: files
        for fid, files in all_ids.items()
        if "," in files  # comma indicates the same ID appeared in two files
    }
    check(
        "fact_id unique across both files",
        not cross_dups,
        "collisions: {}".format(dict(list(cross_dups.items())[:5])) if cross_dups else "",
    )

    # 10. Five deliberate overlaps present with expected values
    if "hospital_a" in loaded and "hospital_b" in loaded:
        fa = loaded["hospital_a"]
        fb = loaded["hospital_b"]

        visiting_a = {"days": _ALL_DAYS, "start": "16:00", "end": "19:00"}
        visiting_b = {"days": _ALL_DAYS, "start": "17:00", "end": "20:00"}

        overlap_checks = [
            # --- overlap a: Dr. Priya Nair, department differs ---
            (
                "overlap-a  Dr. Priya Nair  dept=General Medicine in A",
                _has(fa, attribute="department", value="General Medicine",
                     name_substr="Dr. Priya Nair"),
            ),
            (
                "overlap-a  Dr. Priya Nair  dept=Dermatology in B",
                _has(fb, attribute="department", value="Dermatology",
                     name_substr="Dr. Priya Nair"),
            ),
            # --- overlap b: Dr. Rajesh Varma, department differs ---
            (
                "overlap-b  Dr. Rajesh Varma  dept=Cardiology in A",
                _has(fa, attribute="department", value="Cardiology",
                     name_substr="Dr. Rajesh Varma"),
            ),
            (
                "overlap-b  Dr. Rajesh Varma  dept=ENT in B",
                _has(fb, attribute="department", value="ENT",
                     name_substr="Dr. Rajesh Varma"),
            ),
            # --- overlap c: Metformin 500mg, price differs ---
            (
                "overlap-c  Metformin 500mg  price=4.0 INR in A",
                _has(fa, attribute="price_inr", value=4.0,
                     name_substr="Metformin 500mg"),
            ),
            (
                "overlap-c  Metformin 500mg  price=5.5 INR in B",
                _has(fb, attribute="price_inr", value=5.5,
                     name_substr="Metformin 500mg"),
            ),
            # --- overlap d: Comprehensive Lipid Profile, price and fasting differ ---
            (
                "overlap-d  Lipid Profile  price=650 INR in A",
                _has(fa, attribute="price_inr", value=650,
                     name_substr="Lipid Profile"),
            ),
            (
                "overlap-d  Lipid Profile  price=850 INR in B",
                _has(fb, attribute="price_inr", value=850,
                     name_substr="Lipid Profile"),
            ),
            (
                "overlap-d  Lipid Profile  fasting=12 h in A",
                _has(fa, attribute="fasting_hours", value=12,
                     name_substr="Lipid Profile"),
            ),
            (
                "overlap-d  Lipid Profile  fasting=8 h in B",
                _has(fb, attribute="fasting_hours", value=8,
                     name_substr="Lipid Profile"),
            ),
            # --- overlap e: visiting hours differ ---
            (
                "overlap-e  visiting hours 16:00-19:00 in A",
                _has(fa, attribute="visiting_hours", value=visiting_a),
            ),
            (
                "overlap-e  visiting hours 17:00-20:00 in B",
                _has(fb, attribute="visiting_hours", value=visiting_b),
            ),
        ]

        for label, passed in overlap_checks:
            check(label, passed)
    else:
        print("  [SKIP] overlap checks — one or both files failed to load")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  PASS: {}   FAIL: {}".format(pass_count, fail_count))
    if fail_count:
        print("OVERALL: FAIL")
        return 1
    print("OVERALL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
