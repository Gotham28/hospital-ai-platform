"""
services/vocabulary.py
───────────────────────
Department synonym table, name normalisation helpers, and the
score_doctor_relevance() function used by the doctor RAG filter.

Extracted from app.api.v1.endpoints.ai — Stage 3 of service extraction.
Also used by rag.py (Stage 4) — keep this module free of FastAPI/SQLAlchemy
imports so it remains lightweight and importable anywhere.

NOTE: score_doctor_relevance() is confirmed unused as of 2026-08-02 (no call
sites outside this file and the Stage 3 import in ai.py).  It is retained
here because Stage 4 (rag.py) will wire it in.  Remove if Stage 4 is
ultimately descoped.
"""
import re

# =============================================================================
# DEPARTMENT SYNONYM TABLE
# =============================================================================
# Shared by patient_context.py (_update_patient_ctx dept extraction) and
# rag.py (score_doctor_relevance synonym expansion).  One source of truth.

_DEPT_SYNONYMS: dict[str, list[str]] = {
    "orthopaedics":     ["orthopedics", "ortho", "orthopedic", "orthopaedic", "bone", "joint"],
    "orthopedics":      ["orthopaedics", "ortho", "orthopedic", "orthopaedic", "bone", "joint"],
    "cardiology":       ["cardiac", "heart", "cardio"],
    "general medicine": ["general", "medicine", "physician", "gm"],
    "gynaecology":      ["gynecology", "gynae", "obstetrics", "obgyn", "ob-gyn", "women"],
    "gynecology":       ["gynaecology", "gynae", "obstetrics", "obgyn", "ob-gyn", "women"],
    "paediatrics":      ["pediatrics", "paediatric", "pediatric", "child", "children"],
    "pediatrics":       ["paediatrics", "paediatric", "pediatric", "child", "children"],
    "dermatology":      ["derma", "skin"],
    "neurology":        ["neuro", "brain", "nerve"],
    "ophthalmology":    ["eye", "ophthal", "vision"],
    "ent":              ["ear", "nose", "throat", "otolaryngology"],
    "psychiatry":       ["mental health", "psychology", "psych"],
    "oncology":         ["cancer", "tumor", "tumour"],
    "urology":          ["urological", "kidney", "bladder"],
    "nephrology":       ["kidney", "renal"],
    "pulmonology":      ["lung", "chest", "respiratory", "pulmonary"],
    "gastroenterology": ["gastro", "digestive", "stomach", "gut", "gi"],
    "endocrinology":    ["diabetes", "thyroid", "hormones", "endocrine"],
    "rheumatology":     ["arthritis", "rheumatic", "joints"],
    "surgery":          ["surgical", "general surgery", "laparoscopy", "laproscopy"],
    "dentistry":        ["dental", "teeth", "tooth"],
    "physiotherapy":    ["physio", "rehabilitation", "rehab"],
    "radiology":        ["xray", "x-ray", "imaging", "scan", "mri"],
    "anesthesiology":   ["anaesthesia", "anesthesia", "anaesthesiology"],
}


# =============================================================================
# HELPERS
# =============================================================================

def _expand_with_synonyms(tokens: set) -> set:
    expanded = set(tokens)
    for token in tokens:
        for canonical, variants in _DEPT_SYNONYMS.items():
            if token == canonical or token in variants:
                expanded.add(canonical)
                expanded.update(variants)
    return expanded


def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"dr\.?\s*", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# =============================================================================
# DOCTOR RELEVANCE SCORE
# =============================================================================
# NOTE: As of 2026-08-02, score_doctor_relevance() has no call sites outside
# this module.  It is imported by ai.py for completeness and will be wired in
# by rag.py in Stage 4.

def score_doctor_relevance(question: str, doctor) -> float:
    """
    Return a 0-1 relevance score for `doctor` given the patient's `question`.
    `doctor` is a Doctor ORM instance; typed as Any to keep this module
    free of SQLAlchemy imports.
    """
    q_norm = normalize_name(question)
    q_tokens = set(q_norm.split())
    if not q_tokens:
        return 0.0

    dept  = normalize_name(doctor.department or "")
    name  = normalize_name(doctor.name or "")
    sched = normalize_name(
        getattr(doctor, "base_schedule", None)
        or getattr(doctor, "schedule", None)
        or ""
    )

    d_tokens = set((dept + " " + name + " " + sched).split())
    if not d_tokens:
        return 0.0

    q_expanded = _expand_with_synonyms(q_tokens)
    d_expanded = _expand_with_synonyms(d_tokens)

    token_score = len(q_expanded & d_expanded) / len(q_expanded)

    substring_score = 0.0
    for qt in q_tokens:
        if len(qt) >= 4 and qt in dept:
            substring_score = max(substring_score, 0.6)

    return max(token_score, substring_score)
