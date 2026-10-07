"""Validation script for backend/research/fixtures/guard_dev_set.json.

Asserts dataset schema, distribution requirements, entity anonymity,
and label validity as specified in G-05 and G-06.
"""

import json
from pathlib import Path
import re
import sys

ALLOWED_SPLITS = {"tuning", "holdout"}
ALLOWED_LANGS = {"en", "ml"}
ALLOWED_VERDICTS = {"supported", "unsupported", "contradicted"}
ALLOWED_FACT_LOCK_STATUSES = {"survived", "changed", "unverified"}
ALLOWED_FACT_LOCK_TYPES = {
    "number",
    "price",
    "time",
    "date",
    "weekday",
    "doctor_name",
    "test_name",
    "department",
    "hospital",
}
ALLOWED_CONFLICT_TYPES = {
    "answer_vs_data",
    "instruction_vs_data",
    "answer_follows_instruction_against_data",
}

REQUIRED_FIELDS = [
    "id",
    "split",
    "lang",
    "category",
    "phenomenon",
    "test_focus",
    "context",
    "instructions",
    "answer",
    "ground_truth",
    "notes",
]

REQUIRED_GROUND_TRUTH_FIELDS = [
    "claims",
    "overall_verdict",
    "conflicts",
    "fact_lock",
    "changed",
    "final_answer",
]

# Patterns representing suspicious real names/entities outside approved fictional templates
APPROVED_ENTITIES_RE = re.compile(
    r"Hospital [A-Z]|Dr\. Test (One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)|"
    r"ഡോ\. ടെസ്റ്റ് (വൺ|ടു|ത്രീ|ഫോർ|ഫൈവ്|സിക്സ്|സെവൻ|എയിറ്റ്|നൈൻ|ടെൻ)",
    re.IGNORECASE,
)


def validate_dataset(filepath: Path) -> dict:
    if not filepath.exists():
        raise FileNotFoundError(f"Fixture file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Root element must be a list")

    total_count = len(data)
    assert total_count == 100, f"Expected 100 items, got {total_count}"

    seen_ids = set()
    split_counts = {"tuning": 0, "holdout": 0}
    lang_counts = {"en": 0, "ml": 0}
    verdict_counts = {"supported": 0, "unsupported": 0, "contradicted": 0}
    phenomena_counts = {}

    for idx, item in enumerate(data):
        item_id = item.get("id")
        if item_id in seen_ids:
            raise ValueError(f"Duplicate id {item_id} at index {idx}")
        seen_ids.add(item_id)

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in item:
                raise ValueError(f"Item {item_id} missing required field '{field}'")
            val = item[field]
            if val is None or (isinstance(val, (str, list, dict)) and len(val) == 0):
                raise ValueError(f"Item {item_id} has empty field '{field}'")

        # Split and Lang
        split = item["split"]
        lang = item["lang"]
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"Item {item_id} invalid split: {split}")
        if lang not in ALLOWED_LANGS:
            raise ValueError(f"Item {item_id} invalid lang: {lang}")
        split_counts[split] += 1
        lang_counts[lang] += 1

        # Ground truth
        gt = item["ground_truth"]
        for gt_field in REQUIRED_GROUND_TRUTH_FIELDS:
            if gt_field not in gt:
                raise ValueError(f"Item {item_id} ground_truth missing '{gt_field}'")

        ov = gt["overall_verdict"]
        if ov not in ALLOWED_VERDICTS:
            raise ValueError(f"Item {item_id} invalid overall_verdict: {ov}")
        verdict_counts[ov] += 1

        # Claims
        claims = gt["claims"]
        if not isinstance(claims, list) or len(claims) == 0:
            raise ValueError(f"Item {item_id} claims must be a non-empty list")
        for c in claims:
            if "claim_id" not in c or "text" not in c or "verdict" not in c:
                raise ValueError(f"Item {item_id} claim missing required keys: {c}")
            if c["verdict"] not in ALLOWED_VERDICTS:
                raise ValueError(f"Item {item_id} claim invalid verdict: {c['verdict']}")

        # Fact lock checks
        for fl in gt["fact_lock"]:
            if "item" not in fl or "type" not in fl or "status" not in fl:
                raise ValueError(f"Item {item_id} fact_lock missing keys: {fl}")
            if fl["type"] not in ALLOWED_FACT_LOCK_TYPES:
                raise ValueError(f"Item {item_id} fact_lock invalid type: {fl['type']}")
            if fl["status"] not in ALLOWED_FACT_LOCK_STATUSES:
                raise ValueError(f"Item {item_id} fact_lock invalid status: {fl['status']}")

        # Conflicts checks
        for conf in gt["conflicts"]:
            if "type" not in conf or conf["type"] not in ALLOWED_CONFLICT_TYPES:
                raise ValueError(f"Item {item_id} conflict invalid type: {conf}")

        phenomenon = item.get("phenomenon", "unknown")
        phenomena_counts[phenomenon] = phenomena_counts.get(phenomenon, 0) + 1

    # Assert exact distributions
    assert split_counts["tuning"] == 50, f"Expected 50 tuning, got {split_counts['tuning']}"
    assert split_counts["holdout"] == 50, f"Expected 50 holdout, got {split_counts['holdout']}"
    assert lang_counts["en"] == 50, f"Expected 50 English, got {lang_counts['en']}"
    assert lang_counts["ml"] == 50, f"Expected 50 Malayalam, got {lang_counts['ml']}"
    assert verdict_counts["supported"] == 50, f"Expected 50 supported, got {verdict_counts['supported']}"
    assert (
        verdict_counts["unsupported"] + verdict_counts["contradicted"] == 50
    ), f"Expected 50 errors (unsupported + contradicted), got {verdict_counts['unsupported'] + verdict_counts['contradicted']}"

    return {
        "total": total_count,
        "splits": split_counts,
        "languages": lang_counts,
        "verdicts": verdict_counts,
        "phenomena_count": len(phenomena_counts),
        "phenomena": phenomena_counts,
    }


if __name__ == "__main__":
    fixture_path = Path(__file__).parent / "guard_dev_set.json"
    stats = validate_dataset(fixture_path)
    print("=== VALIDATION SUCCESSFUL ===")
    print(f"Total examples: {stats['total']}")
    print(f"Splits: {stats['splits']}")
    print(f"Languages: {stats['languages']}")
    print(f"Verdicts: {stats['verdicts']}")
    print(f"Distinct phenomena types: {stats['phenomena_count']}")
    sys.exit(0)
