"""Rule-based claim extraction for English and Malayalam answers."""

from __future__ import annotations

import re

_BOUNDARY_PATTERN = re.compile(r"(\r?\n+|(?<=[.!?।])\s+)")
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st",
    "v", "vs", "eg", "ie", "etc", "inc", "ltd", "corp", "co",
    "dept", "approx", "no", "vol", "us", "uk",
    "ഡോ",  # Malayalam Dr.
}
_ENGLISH_CLAUSE_BOUNDARY = re.compile(
    r"\s+(?:and|but|while)\s+"
    r"(?=(?:the|a|an|our|their|this|that|it|they|he|she|we|clinic|"
    r"fee|price|consultation|test|service|patients|hospital)\b)",
    re.IGNORECASE,
)
_MALAYALAM_CLAUSE_BOUNDARY = re.compile(r"\s+(?:കൂടാതെ|എന്നാൽ|അതേസമയം)\s+")
_NON_FACTUAL = {
    "hello",
    "hi",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
    "i hope this helps",
    "please let me know if you need anything else",
    "നമസ്കാരം",
    "സുപ്രഭാതം",
}


def _is_malayalam(text: str, lang: str) -> bool:
    if lang == "ml":
        return True
    if lang == "en":
        return False
    return any("\u0d00" <= char <= "\u0d7f" for char in text)


def _clean_piece(piece: str) -> str:
    return piece.strip(" \t\r\n;—–-")


def _is_factual_candidate(piece: str) -> bool:
    normalized = re.sub(r"[.!?।]+$", "", piece).strip().casefold()
    if not normalized or normalized in _NON_FACTUAL:
        return False
    return any(char.isalnum() or "\u0d00" <= char <= "\u0d7f" for char in piece)


def _split_sentences(text: str) -> list[str]:
    tokens = _BOUNDARY_PATTERN.split(text)
    sentences: list[str] = []
    current_chunk = ""

    for i in range(0, len(tokens), 2):
        piece = tokens[i]
        delim = tokens[i + 1] if i + 1 < len(tokens) else ""
        current_chunk += piece
        if not delim:
            if current_chunk:
                sentences.append(current_chunk)
            break

        if "\n" in delim or "\r" in delim:
            sentences.append(current_chunk)
            current_chunk = ""
            continue

        match = re.search(r"(\b[\w\u0d00-\u0d7f]+)[.!?।]$", current_chunk)
        if match:
            word = match.group(1).casefold()
            if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
                current_chunk += delim
                continue

        sentences.append(current_chunk)
        current_chunk = ""

    return sentences


def split_claims(answer: str, lang: str = "en") -> list[str]:
    """Split an answer into candidate factual claims, preserving source text.

    English coordinators are split only before likely clause subjects or clinic
    fact terms, which helps keep lists such as "Monday and Wednesday" intact.
    Malayalam splitting uses explicit clause connectors; agglutinative suffixes
    are deliberately not guessed at.
    """
    if not isinstance(answer, str):
        raise TypeError("answer must be a string")
    if lang not in {"en", "ml"}:
        raise ValueError("lang must be 'en' or 'ml'")

    malayalam = _is_malayalam(answer, lang)
    clause_boundary = _MALAYALAM_CLAUSE_BOUNDARY if malayalam else _ENGLISH_CLAUSE_BOUNDARY
    claims: list[str] = []
    for sentence in _split_sentences(answer):
        for clause in clause_boundary.split(sentence):
            cleaned = _clean_piece(clause)
            if _is_factual_candidate(cleaned):
                claims.append(cleaned)
    return claims
