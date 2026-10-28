"""Deterministic fact-lock extraction and context comparison."""

from __future__ import annotations

from dataclasses import dataclass
import re

_DIGIT_TRANSLATION = str.maketrans("൦൧൨൩൪൫൬൭൮൯", "0123456789")
_NUMBER = re.compile(r"(?<!\w)(\d+(?::\d+)?(?:\.\d+)?)(?!\w)")
_PRICE = re.compile(r"₹|\brs\.?\b|\brupees?\b|\binr\b|\bfee\b|\bcosts?\b|രൂപ|ഫീസ്|(?<!രാ)വില|ചെലവ്", re.I)
_DATE = re.compile(r"(?<!\d)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?!\d)")
_MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\b",
    re.I,
)
_TIME_12 = re.compile(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d|0))?\s*(am|pm)\b", re.I)
_TIME_24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d|0)\b")
_TIME_ML = re.compile(
    r"(രാവിലെ|ഉച്ചയ്ക്ക്|വൈകുന്നേരം|രാത്രി)\s*(\d{1,2})(?::([0-5]\d|0))?",
    re.I,
)
_DURATION = re.compile(r"\b(?:days?|weeks?|hours?)\b|ദിവസം|ആഴ്ച|മണിക്കൂർ", re.I)
_WEEKDAYS = {
    "monday": ("Monday", "തിങ്കൾ", "തിങ്കളാഴ്ച"),
    "tuesday": ("Tuesday", "ചൊവ്വ", "ചൊവ്വാഴ്ച"),
    "wednesday": ("Wednesday", "ബുധൻ", "ബുധനാഴ്ച"),
    "thursday": ("Thursday", "വ്യാഴം", "വ്യാഴാഴ്ച"),
    "friday": ("Friday", "വെള്ളി", "വെള്ളിയാഴ്ച"),
    "saturday": ("Saturday", "ശനി", "ശനിയാഴ്ച"),
    "sunday": ("Sunday", "ഞായർ", "ഞായറാഴ്ച"),
}
_DOCTOR_NUMBERS = {
    "one": ("വൺ",), "two": ("ടു",), "three": ("ത്രീ",),
    "four": ("ഫോർ",), "five": ("ഫൈവ്",), "six": ("സിക്സ്",),
    "seven": ("സെവൻ",), "eight": ("എയ്റ്റ്",), "nine": ("നൈൻ",),
    "ten": ("ടെൻ",),
}
_TEST_NAMES = {
    "blood glucose test": ("blood glucose", "ബ്ലഡ് ഗ്ലൂക്കോസ്"),
    "fasting blood sugar": ("fasting blood sugar", "ഫാസ്റ്റിംഗ് ബ്ലഡ് ഷുഗർ"),
    "lipid profile": ("lipid profile", "ലിപിഡ് പ്രൊഫൈൽ"),
    "rheumatoid factor": ("rheumatoid factor", "റൂമറ്റോയ്ഡ് ഫാക്ടർ"),
    "hemogram": ("hemogram", "ഹീമോഗ്രാം"),
    "thyroid test": ("thyroid test", "തൈറോയ്ഡ് പരിശോധന"),
    "urine routine": ("urine routine", "യൂറീൻ റൂട്ടീൻ"),
    "ultrasound": ("ultrasound", "അൾട്രാസൗണ്ട്"),
    "ecg": ("ecg", "ഇസിജി"),
}


@dataclass(frozen=True)
class _Lock:
    item: str
    type: str
    value: str
    entity: str


def _canonical_time(hour: int, minute: int, meridiem: str | None = None) -> str:
    if meridiem:
        hour = hour % 12 + (12 if meridiem.casefold() == "pm" else 0)
    return f"{hour:02d}:{minute:02d}"


def _entity_mentions(text: str) -> list[tuple[int, int, str, str]]:
    lowered = text.casefold()
    mentions: list[tuple[int, int, str, str]] = []
    doctor_pattern = re.compile(r"\bdr\.?\s*test\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b", re.I)
    for match in doctor_pattern.finditer(lowered):
        mentions.append((match.start(), match.end(), "doctor_name", f"doctor:{match.group(1).casefold()}"))
    for word, aliases in _DOCTOR_NUMBERS.items():
        pattern = re.compile(rf"ഡോ\.?\s*ടെസ്റ്റ്\s*{re.escape(aliases[0])}", re.I)
        for match in pattern.finditer(text):
            mentions.append((match.start(), match.end(), "doctor_name", f"doctor:{word}"))

    for canonical, aliases in _TEST_NAMES.items():
        for alias in aliases:
            for match in re.finditer(re.escape(alias), text, re.I):
                mentions.append((match.start(), match.end(), "test_name", f"test:{canonical}"))
    for match in re.finditer(r"\bHospital\s+([A-Z])\b", text, re.I):
        mentions.append((match.start(), match.end(), "hospital", f"hospital:{match.group(1).casefold()}"))
    for match in re.finditer(r"ഹോസ്പിറ്റൽ\s+([എബി])", text, re.I):
        hospital = "a" if match.group(1) == "എ" else "b"
        mentions.append((match.start(), match.end(), "hospital", f"hospital:{hospital}"))
    return sorted(mentions)


def _nearest_entity(position: int, mentions: list[tuple[int, int, str, str]]) -> str:
    if not mentions:
        return ""
    start, end, _, key = min(
        mentions,
        key=lambda mention: min(abs(position - mention[0]), abs(position - mention[1])),
    )
    return key if min(abs(position - start), abs(position - end)) <= 80 else ""


def _extract(text: str) -> list[_Lock]:
    normalized = text.translate(_DIGIT_TRANSLATION)
    mentions = _entity_mentions(text)
    locks: list[_Lock] = []
    occupied: list[tuple[int, int]] = []

    for match in _DATE.finditer(normalized):
        locks.append(_Lock(match.group(1), "date", match.group(1), ""))
        occupied.append(match.span())
    for match in _MONTH_DATE.finditer(normalized):
        value = f"{match.group(1).casefold()}-{int(match.group(2)):02d}"
        locks.append(_Lock(match.group(0), "date", value, ""))
        occupied.append(match.span())

    for match in _TIME_ML.finditer(normalized):
        hour = int(match.group(2))
        minute = int(match.group(3) or "0")
        period = match.group(1)
        if period == "രാവിലെ":
            value = _canonical_time(hour, minute, "am")
        elif period == "രാത്രി":
            value = _canonical_time(hour, minute, "am" if hour == 12 else "pm")
        else:
            value = _canonical_time(hour, minute, "pm")
        locks.append(_Lock(match.group(0), "time", value, _nearest_entity(match.start(), mentions)))
        occupied.append(match.span())
    for match in _TIME_12.finditer(normalized):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        hour, minute, period = int(match.group(1)), int(match.group(2) or "0"), match.group(3)
        locks.append(_Lock(match.group(0), "time", _canonical_time(hour, minute, period), _nearest_entity(match.start(), mentions)))
        occupied.append(match.span())
    for match in _TIME_24.finditer(normalized):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        locks.append(_Lock(match.group(0), "time", _canonical_time(int(match.group(1)), int(match.group(2))), _nearest_entity(match.start(), mentions)))
        occupied.append(match.span())

    for canonical_day, aliases in _WEEKDAYS.items():
        for alias in aliases:
            pattern = re.compile(re.escape(alias), re.I)
            for match in pattern.finditer(text):
                locks.append(_Lock(match.group(0), "weekday", canonical_day, _nearest_entity(match.start(), mentions)))

    for match in _NUMBER.finditer(normalized):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        nearby = normalized[max(0, match.start() - 24) : match.end() + 24]
        if _PRICE.search(nearby):
            kind = "price"
        elif _DURATION.search(nearby):
            kind = "number"
        else:
            kind = "number"
        val = match.group(1)
        if kind in ("price", "number"):
            try:
                fval = float(val)
                if fval.is_integer():
                    val = str(int(fval))
            except ValueError:
                pass
        locks.append(_Lock(match.group(0), kind, val, _nearest_entity(match.start(), mentions)))

    for start, end, kind, key in mentions:
        locks.append(_Lock(text[start:end], kind, key, ""))

    unique: dict[tuple[str, str, str, str], _Lock] = {}
    for lock in locks:
        unique[(lock.item.casefold(), lock.type, lock.value, lock.entity)] = lock
    return list(unique.values())


def compare_fact_locks(context: list[str], answer: str) -> list[dict[str, str]]:
    """Report answer values as survived, changed, or unverified."""
    context_locks = [lock for passage in context for lock in _extract(passage)]
    answer_locks = _extract(answer)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for answer_lock in answer_locks:
        exact = [
            lock
            for lock in context_locks
            if lock.type == answer_lock.type
            and lock.value == answer_lock.value
            and (not answer_lock.entity or lock.entity == answer_lock.entity)
        ]
        relevant = [
            lock
            for lock in context_locks
            if lock.type == answer_lock.type
            and (not answer_lock.entity or lock.entity == answer_lock.entity)
        ]
        status = "survived" if exact else "changed" if relevant else "unverified"
        key = (answer_lock.type, answer_lock.value, answer_lock.entity, status)
        if key in seen:
            continue
        results.append({"item": answer_lock.item, "type": answer_lock.type, "status": status})
        seen.add(key)
    return results
