"""Build script for the AROGYA research benchmark public release pack.

Exports public fields for benchmark items, strictly filters unconsented or non-synthetic
data, and runs automated privacy pattern guards before emitting records.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from backend.research.real_queries.anonymise import _PHONE_PATTERN, _ID_PATTERN

PUBLIC_FIELDS = {
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
}


@dataclass(frozen=True)
class ReleaseStats:
    total_input: int
    exported_count: int
    rejected_non_synthetic: int
    rejected_privacy_leak: int


def export_benchmark_item(item: dict[str, Any], allow_non_synthetic: bool = False) -> dict[str, Any]:
    """Validate and filter a single benchmark record for public release."""
    source_type = item.get("source_type", "synthetic")
    if source_type != "synthetic" and not allow_non_synthetic:
        raise ValueError(
            f"Item {item.get('id')} rejected: non-synthetic source '{source_type}' "
            "requires explicit consent verification before public export."
        )

    # Privacy safety scan on context and answer
    combined_text = " ".join(
        [
            item.get("answer", ""),
            item.get("instructions", ""),
            " ".join(item.get("context", [])),
        ]
    )
    if _PHONE_PATTERN.search(combined_text):
        raise ValueError(f"Item {item.get('id')} rejected: potential phone number detected.")
    if _ID_PATTERN.search(combined_text):
        raise ValueError(f"Item {item.get('id')} rejected: potential national/hospital ID detected.")

    return {key: item[key] for key in PUBLIC_FIELDS if key in item}


def build_release_pack(
    input_items: list[dict[str, Any]],
    output_path: Path,
    allow_non_synthetic: bool = False,
) -> ReleaseStats:
    """Export benchmark dataset, enforcing privacy and provenance constraints."""
    exported: list[dict[str, Any]] = []
    rejected_non_synthetic = 0
    rejected_privacy = 0

    for item in input_items:
        try:
            exported_item = export_benchmark_item(item, allow_non_synthetic=allow_non_synthetic)
            exported.append(exported_item)
        except ValueError as exc:
            msg = str(exc)
            if "non-synthetic source" in msg:
                rejected_non_synthetic += 1
            else:
                rejected_privacy += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in exported:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    return ReleaseStats(
        total_input=len(input_items),
        exported_count=len(exported),
        rejected_non_synthetic=rejected_non_synthetic,
        rejected_privacy_leak=rejected_privacy,
    )
