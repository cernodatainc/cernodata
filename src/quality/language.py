"""
src/quality/language.py

Tier 2 Language & Dictionary Verification rules and diacritic anomaly metrics.
"""

import re

LANGUAGE_DIACRITICS = {
    "pl": set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"),
    "de": set("äöüßÄÖÜ"),
    "fr": set("éèêëàâçîïôûùÉÈÊËÀÂÇÎÏÔÛÙ"),
    "es": set("ñáéíóúü¿¡ÑÁÉÍÓÚÜ")
}


def compute_language_score(text: str, language: str = "en") -> float:
    """
    Tier 2 Language & Dictionary Verification:
    Evaluates text fidelity against specified language norms and detects common OCR
    diacritic substitution errors (such as 'q' replacing 'ą' in Polish text contexts).
    """
    lang = language.lower().strip()
    if not text or lang == "en":
        return 1.0

    score = 1.0

    if lang == "pl":
        anomalous_q_matches = re.findall(r"\b\w*q\w*\b", text, re.IGNORECASE)
        anomalous_q = [
            w for w in anomalous_q_matches
            if w.lower() not in {"sql", "query", "q1", "q2", "q3", "q4", "quality", "qr", "quick"}
        ]
        if anomalous_q:
            penalty = min(0.50, len(anomalous_q) * 0.15)
            score -= penalty

        diacritics = LANGUAGE_DIACRITICS.get("pl", set())
        has_diacritics = any(c in diacritics for c in text)
        words = text.split()
        if len(words) > 12 and not has_diacritics:
            score -= 0.15

    elif lang in LANGUAGE_DIACRITICS:
        diacritics = LANGUAGE_DIACRITICS[lang]
        has_diacritics = any(c in diacritics for c in text)
        words = text.split()
        if len(words) > 15 and not has_diacritics:
            score -= 0.15

    return max(0.0, score)
