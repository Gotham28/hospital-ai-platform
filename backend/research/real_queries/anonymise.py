"""Anonymisation utilities for scrubbed patient inquiries.

Replaces personal identifiers (names, phone numbers, addresses, DOBs, IDs, places)
with redaction tags across English and Malayalam text. Never processes unapproved real data.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AnonymisationResult:
    anonymised_text: str
    redactions: list[dict[str, str]]
    modified: bool


# Phone numbers (Indian standard 10-digit, +91, with spaces/hyphens)
_PHONE_PATTERN = re.compile(
    r"(?:\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}|\b\d{10}\b",
    re.IGNORECASE,
)

# Identification numbers (Aadhaar 12-digit, UHID, MRN, PAN)
_ID_PATTERN = re.compile(
    r"\b\d{4}[\-\s]\d{4}[\-\s]\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b|\b(?:UHID|MRN|PATIENT\s*ID)[:\-\s]*[A-Z0-9\-]+\b",
    re.IGNORECASE,
)

# Date of birth / dates attached to birth keywords
_DOB_PATTERN = re.compile(
    r"(?:DOB|Date\s+of\s+birth|ജനനത്തീയതി)[:\-\s]*(?:\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    re.IGNORECASE,
)

# Place names and Kerala districts / towns (English & Malayalam)
_PLACES_EN = [
    "Kochi", "Ernakulam", "Trivandrum", "Thiruvananthapuram", "Kozhikode",
    "Calicut", "Thrissur", "Kollam", "Alappuzha", "Palakkad", "Malappuram",
    "Kannur", "Kottayam", "Kasaragod", "Pathanamthitta", "Idukki", "Wayanad",
    "Edappally", "Kaloor", "Aluva", "Vytilla", "Angamaly",
]
_PLACES_ML = [
    "കൊച്ചി", "എറണാകുളം", "തിരുവനന്തപുരം", "കോഴിക്കോട്", "തൃശ്ശൂർ",
    "കൊല്ലം", "ആലപ്പുഴ", "പാലക്കാട്", "മലപ്പുറം", "കണ്ണൂർ", "കോട്ടയം",
    "കാസർഗോഡ്", "പത്തനംതിട്ട", "ഇടുക്കി", "വയനാട്", "ഇടപ്പള്ളി", "ആലുവ",
]

_PLACE_REGEX_EN = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _PLACES_EN) + r")\b",
    re.IGNORECASE,
)
_PLACE_REGEX_ML = re.compile(
    r"(?:" + "|".join(re.escape(p) for p in _PLACES_ML) + r")",
)

# Common honorifics and name markers
_NAME_PREFIXES = re.compile(
    r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt\.|ശ്രീ|ശ്രീമതി|ഡോക്ടർ|ഡോ\.)\s+([A-Za-z\u0d00-\u0d7f]+(?:\s+[A-Za-z\u0d00-\u0d7f]+)?)",
    re.IGNORECASE,
)

# Address keywords
_ADDRESS_PATTERN = re.compile(
    r"(?:Address|House\s+No|Villa\s+No|മേൽവിലാസം)[:\-\s]*[A-Za-z0-9\u0d00-\u0d7f\s,\-\./]+?(?=\.|\n|$)",
    re.IGNORECASE,
)


def anonymise_text(text: str) -> AnonymisationResult:
    """Scrub PII from text and return redaction details."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    output = text
    redactions: list[dict[str, str]] = []

    # 1. Phone numbers
    for match in _PHONE_PATTERN.finditer(output):
        redactions.append({"tag": "[PHONE]", "span": match.group(0)})
    output = _PHONE_PATTERN.sub("[PHONE]", output)

    # 2. Identification numbers
    for match in _ID_PATTERN.finditer(output):
        redactions.append({"tag": "[ID]", "span": match.group(0)})
    output = _ID_PATTERN.sub("[ID]", output)

    # 3. Date of birth
    for match in _DOB_PATTERN.finditer(output):
        redactions.append({"tag": "[DOB]", "span": match.group(0)})
    output = _DOB_PATTERN.sub("[DOB]", output)

    # 4. Addresses
    for match in _ADDRESS_PATTERN.finditer(output):
        redactions.append({"tag": "[ADDRESS]", "span": match.group(0)})
    output = _ADDRESS_PATTERN.sub("[ADDRESS]", output)

    # 5. Names after honorifics
    for match in _NAME_PREFIXES.finditer(output):
        redactions.append({"tag": "[NAME]", "span": match.group(0)})
    output = _NAME_PREFIXES.sub("[NAME]", output)

    # 6. Specific location and place names
    for match in _PLACE_REGEX_EN.finditer(output):
        redactions.append({"tag": "[PLACE]", "span": match.group(0)})
    output = _PLACE_REGEX_EN.sub("[PLACE]", output)

    for match in _PLACE_REGEX_ML.finditer(output):
        redactions.append({"tag": "[PLACE]", "span": match.group(0)})
    output = _PLACE_REGEX_ML.sub("[PLACE]", output)

    return AnonymisationResult(
        anonymised_text=output,
        redactions=redactions,
        modified=output != text,
    )
