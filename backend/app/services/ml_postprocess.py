import re

_MALAYALAM_BLOCK_RE = re.compile('[\u0D00-\u0D7F]')

_RULES = [
    # Rule 1 - chillu normalisation
    (re.compile('\u0D30\u0D4D\u200D'), '\u0D7C'),
    (re.compile('\u0D28\u0D4D\u200D'), '\u0D7B'),
    (re.compile('\u0D32\u0D4D\u200D'), '\u0D7D'),
    (re.compile('\u0D33\u0D4D\u200D'), '\u0D7E'),
    (re.compile('\u0D23\u0D4D\u200D'), '\u0D7A'),

    # Rule 2 - abbreviated title
    (re.compile(r'ഡോ\.(\s+)'), r'ഡോക്ടർ\1'),

    # Rule 3 - untranslated Latin title
    (re.compile(r'\bDr\.?\s+'), 'ഡോക്ടർ '),
]

def normalise_malayalam(text: str) -> str:
    if not text or text.isspace():
        return text

    if not _MALAYALAM_BLOCK_RE.search(text):
        return text

    result = text
    for pattern, replacement in _RULES:
        result = pattern.sub(replacement, result)

    return result


_MALAYALAM_RANGE = range(0x0D00, 0x0D80)


def contains_malayalam(text: str) -> bool:
    """True if any character falls in the Malayalam Unicode block.

    Used as a guard before an en->ml translation call: text that already
    contains Malayalam must not be sent through en->ml, which would treat
    it as English and garble it. Deliberately conservative — ANY Malayalam
    character suppresses translation, including in mixed English/Malayalam
    text, because leaving mixed text untranslated is a smaller harm than
    corrupting the Malayalam half of it.
    """
    return any(ord(ch) in _MALAYALAM_RANGE for ch in text)
