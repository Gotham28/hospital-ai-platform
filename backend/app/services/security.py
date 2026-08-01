import re
from typing import Optional

# =============================================================================
# INJECTION DETECTION
# =============================================================================

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompt|rules?|guidelines?)", re.IGNORECASE),
    re.compile(r"(disregard|forget|override|bypass|circumvent)\s+(your\s+)?(instructions?|guidelines?|rules?|prompt|training)", re.IGNORECASE),
    re.compile(r"(your\s+new|new\s+instructions?\s+(are|is)|from\s+now\s+on\s+you)", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\b(act|behave|pretend|roleplay|role-play|simulate)\s+(as|like)\b", re.IGNORECASE),
    re.compile(r"\b(DAN|jailbreak|do\s+anything\s+now)\b", re.IGNORECASE),
    re.compile(r"(^|\s)(system|assistant)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"(\[INST\]|<<SYS>>|<</SYS>>|\[/INST\])", re.IGNORECASE),
    re.compile(r"(repeat|show|print|reveal|display|tell me|what (are|is))\s+(your\s+)?(system\s+)?(prompt|instructions?|guidelines?|rules?)", re.IGNORECASE),
]

def detect_prompt_injection(text: str) -> Optional[str]:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return "Prompt injection detected."
    return None
