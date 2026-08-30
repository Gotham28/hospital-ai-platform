import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# PROVIDERS
# =============================================================================
# Primary: Sarvam AI (sarvam-translate:v1 — NOT mayura:v1, see STATUS.md
# Catch-up 2026-08-23). Fallback: Google Translate's public gtx endpoint.
# MASTER_PLAN.md §1.3a Task A.

_SARVAM_URL = "https://api.sarvam.ai/translate"
_SARVAM_MODEL = "sarvam-translate:v1"
_SARVAM_INPUT_LIMIT = 2000
_SARVAM_LANG_CODES = {"en": "en-IN", "ml": "ml-IN"}

_GTRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

_BREAKER_FAILURE_THRESHOLD = 3
_BREAKER_COOLDOWN_SECONDS = 60


class TranslationUnavailableError(Exception):
    """Raised when both Sarvam and Google fail to translate the given text.

    Callers must not treat the untranslated input as a translation — this is
    the failure-visibility contract §1.3a Task A owns (STATUS.md Catch-up
    2026-08-23).
    """


# =============================================================================
# CIRCUIT BREAKER — per provider, in-process, module-level (NOT Redis; see
# MASTER_PLAN.md §1.3a design decisions).
# =============================================================================

class _CircuitBreaker:
    def __init__(self, name: str):
        self._name = name
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= _BREAKER_COOLDOWN_SECONDS:
            logger.info("[Breaker] %s: cooldown elapsed, closing", self._name)
            self._opened_at = None
            self._consecutive_failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _BREAKER_FAILURE_THRESHOLD and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning(
                "[Breaker] %s: opened after %d consecutive failures",
                self._name, self._consecutive_failures,
            )


_sarvam_breaker = _CircuitBreaker("sarvam")
_google_breaker = _CircuitBreaker("google")


# =============================================================================
# CHUNKING — Sarvam only. Google accepts longer input and is never chunked.
# =============================================================================

_SENTENCE_SEPARATORS = (". ", "? ", "! ", "\n")


def _split_into_chunks(text: str, limit: int = _SARVAM_INPUT_LIMIT) -> list[str]:
    """Splits text into pieces each <= limit chars, on sentence boundaries
    where possible, filling greedily. A single sentence over the limit is
    hard-split at the limit so this always terminates. Each piece keeps its
    trailing separator, so "".join(chunks) reconstructs the original text
    (or its translated equivalent, chunk-for-chunk)."""
    if len(text) <= limit:
        return [text]

    sentences: list[str] = []
    remaining = text
    while remaining:
        cut = None
        for sep in _SENTENCE_SEPARATORS:
            idx = remaining.find(sep)
            if idx != -1:
                end = idx + len(sep)
                if cut is None or end < cut:
                    cut = end
        if cut is None:
            sentences.append(remaining)
            remaining = ""
        else:
            sentences.append(remaining[:cut])
            remaining = remaining[cut:]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(sentence):
                chunks.append(sentence[start:start + limit])
                start += limit
            continue
        if len(current) + len(sentence) <= limit:
            current += sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


# =============================================================================
# SARVAM BRIDGE
# =============================================================================
# NOTE: sarvam-translate:v1's acceptance of `mode` / `output_script` is
# untested in this environment — api.sarvam.ai is unreachable here (network
# egress block, same failure mode as api.openai.com; verified 2026-08-30:
# DNS resolves, TCP connect times out on the resolved IP). The request below
# deliberately omits both fields rather than guessing at values that may be
# rejected; only the fields common to every Sarvam translate call are sent.

def _sarvam_payload(text: str, source: str, target: str) -> dict:
    return {
        "input": text,
        "source_language_code": _SARVAM_LANG_CODES.get(source, source),
        "target_language_code": _SARVAM_LANG_CODES.get(target, target),
        "model": _SARVAM_MODEL,
    }


def _sarvam_headers() -> dict:
    return {
        "api-subscription-key": settings.SARVAM_API_KEY,
        "Content-Type": "application/json",
    }


def _sarvam_translate_one(text: str, source: str, target: str) -> str:
    resp = httpx.post(
        _SARVAM_URL, headers=_sarvam_headers(), json=_sarvam_payload(text, source, target), timeout=15.0
    )
    resp.raise_for_status()
    return resp.json()["translated_text"]


async def _sarvam_translate_one_async(text: str, source: str, target: str) -> str:
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            _SARVAM_URL, headers=_sarvam_headers(), json=_sarvam_payload(text, source, target), timeout=15.0
        )
        resp.raise_for_status()
        return resp.json()["translated_text"]


def _sarvam_translate(text: str, source: str, target: str) -> str:
    chunks = _split_into_chunks(text)
    parts = []
    for chunk in chunks:
        stripped = chunk.rstrip()
        trailing = chunk[len(stripped):]
        parts.append(_sarvam_translate_one(stripped, source, target) + trailing)
    return "".join(parts)


async def _sarvam_translate_async(text: str, source: str, target: str) -> str:
    chunks = _split_into_chunks(text)
    parts = []
    for chunk in chunks:
        stripped = chunk.rstrip()
        trailing = chunk[len(stripped):]
        parts.append(await _sarvam_translate_one_async(stripped, source, target) + trailing)
    return "".join(parts)


# =============================================================================
# GOOGLE TRANSLATE BRIDGE (fallback)
# =============================================================================
# Uses the public gtx endpoint (no API key required).

def _google_translate(text: str, source: str, target: str) -> str:
    params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
    resp = httpx.get(_GTRANSLATE_URL, params=params, timeout=8.0)
    resp.raise_for_status()
    data = resp.json()
    return "".join(part[0] for part in data[0] if part[0])


async def _google_translate_async(text: str, source: str, target: str) -> str:
    async with httpx.AsyncClient() as http:
        resp = await http.get(_GTRANSLATE_URL, params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        return "".join(part[0] for part in data[0] if part[0])


def _log_provider_failure(provider: str, source: str, target: str, e: Exception) -> None:
    if isinstance(e, httpx.HTTPStatusError):
        logger.warning(
            "Translation failed (%s, %s->%s): %s (status=%s)",
            provider, source, target, type(e).__name__, e.response.status_code,
        )
    else:
        logger.warning(
            "Translation failed (%s, %s->%s): %s",
            provider, source, target, type(e).__name__,
        )


# =============================================================================
# PUBLIC ENTRY POINTS
# =============================================================================
# Sarvam primary, Google fallback, per-provider circuit breaker. Raises
# TranslationUnavailableError when both fail — never again returns the
# untranslated input as though it were a translation.

def _translate(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text

    if settings.SARVAM_API_KEY and not _sarvam_breaker.is_open():
        try:
            result = _sarvam_translate(text, source, target)
            _sarvam_breaker.record_success()
            return result
        except Exception as e:
            _sarvam_breaker.record_failure()
            _log_provider_failure("sarvam", source, target, e)

    if not _google_breaker.is_open():
        try:
            result = _google_translate(text, source, target)
            _google_breaker.record_success()
            return result
        except Exception as e:
            _google_breaker.record_failure()
            _log_provider_failure("google", source, target, e)

    raise TranslationUnavailableError(f"Both providers failed or unavailable ({source}->{target})")


async def _translate_async(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text

    if settings.SARVAM_API_KEY and not _sarvam_breaker.is_open():
        try:
            result = await _sarvam_translate_async(text, source, target)
            _sarvam_breaker.record_success()
            return result
        except Exception as e:
            _sarvam_breaker.record_failure()
            _log_provider_failure("sarvam", source, target, e)

    if not _google_breaker.is_open():
        try:
            result = await _google_translate_async(text, source, target)
            _google_breaker.record_success()
            return result
        except Exception as e:
            _google_breaker.record_failure()
            _log_provider_failure("google", source, target, e)

    raise TranslationUnavailableError(f"Both providers failed or unavailable ({source}->{target})")
