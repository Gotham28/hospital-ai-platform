import logging

import httpx

logger = logging.getLogger(__name__)

# =============================================================================
# GOOGLE TRANSLATE BRIDGE
# =============================================================================
# Extracted from app.api.v1.endpoints.ai — Stage 2 of service extraction.
# Uses the public gtx endpoint (no API key required).  A future task will
# upgrade this to Sarvam AI — see docs/MASTER_PLAN.md §1.3.

_GTRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def _translate(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text
    try:
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
        resp = httpx.get(_GTRANSLATE_URL, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        if isinstance(e, httpx.HTTPStatusError):
            logger.warning(
                "Translation failed (%s->%s): %s (status=%s)",
                source, target, type(e).__name__, e.response.status_code
            )
        else:
            logger.warning(
                "Translation failed (%s->%s): %s",
                source, target, type(e).__name__
            )
        return text


async def _translate_async(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text
    try:
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
        async with httpx.AsyncClient() as http:
            resp = await http.get(_GTRANSLATE_URL, params=params, timeout=8.0)
            resp.raise_for_status()
            data = resp.json()
            return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        if isinstance(e, httpx.HTTPStatusError):
            logger.warning(
                "Async translation failed (%s->%s): %s (status=%s)",
                source, target, type(e).__name__, e.response.status_code
            )
        else:
            logger.warning(
                "Async translation failed (%s->%s): %s",
                source, target, type(e).__name__
            )
        return text
