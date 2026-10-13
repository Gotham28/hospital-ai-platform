"""Rule-based claim extraction for English and Malayalam answers."""

from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।])\s+|\r?\n+")
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
    for sentence in _SENTENCE_BOUNDARY.split(answer):
        for clause in clause_boundary.split(sentence):
            cleaned = _clean_piece(clause)
            if _is_factual_candidate(cleaned):
                claims.append(cleaned)
    return claims
