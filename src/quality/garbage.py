"""
src/quality/garbage.py

Garbage character ratio & non-printable character metrics.
Detects real-world OCR damage:
- Unicode anomalies: U+FFFD, control characters, private-use code points
- Character repetition: 4+ identical characters in a row
- Punctuation soup & unmatched brackets/parentheses
- Broken/isolated 1-2 character non-words and fragments
- Low alphanumeric ratio in punctuation-heavy sections
"""

import string
import re
import unicodedata
from typing import Dict, Any, List, Set

# Allowed standalone symbols / bullet points
ALLOWED_STANDALONE: Set[str] = {
    '*', '-', '–', '—', '•', '+', '/', '&', '%', '$', '€', '£', '§', '©', '®', ':', '='
}

# Common allowed 1-2 letter words across supported languages (PL, EN, DE)
VALID_SHORT_WORDS: Set[str] = {
    # Polish
    'a', 'i', 'o', 'u', 'w', 'z',
    'od', 'do', 'po', 'na', 'za', 'ze', 'we', 'ku', 'tu', 'to', 'ta', 'te',
    'ci', 'co', 'mu', 'go', 'ma', 'im', 'ja', 'ty', 'on', 'my', 'wy', 'iż',
    'aż', 'bo', 'że', 'ni', 'no', 'ba', 'or', 'al', 'np', 'zł', 'gr', 'nr',
    'ul', 'iv', 'vi', 'ix', 'xi', 'je', 'ją', 'tę', 'sa', 'sp', 'pl', 'eu',
    # English
    'in', 'on', 'at', 'by', 'for', 'of', 'to', 'is', 'it', 'as', 'an', 'be',
    'he', 'we', 'me', 'us', 'my', 'so', 'no', 'if', 'up', 'am', 'or', 'ok',
    # German
    'er', 'es', 'im', 'in', 'am', 'an', 'um', 'zu', 'ab', 'ob', 'ja', 'da', 'wo', 'so', 'du'
}


def compute_garbage_details(text: str) -> Dict[str, Any]:
    """
    Evaluates text for OCR damage signals and returns detailed signal breakdowns
    and composite ratio in range [0.0, 1.0].
    """
    if not text or not text.strip():
        return {
            "ratio": 0.0,
            "unicode_ratio": 0.0,
            "rep_ratio": 0.0,
            "soup_ratio": 0.0,
            "low_alnum_penalty": 0.0,
            "noise_tokens": []
        }

    clean_text = text.strip()
    total_len = len(clean_text)
    non_space_chars = [c for c in clean_text if not c.isspace()]
    if not non_space_chars:
        return {
            "ratio": 0.0,
            "unicode_ratio": 0.0,
            "rep_ratio": 0.0,
            "soup_ratio": 0.0,
            "low_alnum_penalty": 0.0,
            "noise_tokens": []
        }

    # 1. Unicode anomalies & control chars (U+FFFD, control chars, private use)
    unicode_anom = sum(
        1 for c in clean_text
        if c == '\ufffd'
        or ('\ue000' <= c <= '\uf8ff')
        or ('\U000f0000' <= c <= '\U0010ffff')
        or (unicodedata.category(c).startswith('C') and c not in '\n\r\t')
    )
    unicode_ratio = unicode_anom / total_len

    # 2. Character repetition (4+ identical characters in a row)
    rep_chars = sum(len(m.group(0)) for m in re.finditer(r'(.)\1{3,}', clean_text))
    rep_ratio = rep_chars / total_len

    # 3. Punctuation soup, unmatched brackets, & fragmented OCR tokens
    tokens = clean_text.split()
    total_tokens = len(tokens)

    open_parens = clean_text.count('(')
    close_parens = clean_text.count(')')
    open_brackets = clean_text.count('[')
    close_brackets = clean_text.count(']')
    unmatched_parens = max(0, close_parens - open_parens) + max(0, close_brackets - open_brackets)

    soup_chars = unmatched_parens * 2
    noise_tokens: List[str] = []

    for t in tokens:
        stripped = t.strip()
        if not stripped:
            continue

        is_bullet_or_allowed = stripped in ALLOWED_STANDALONE
        is_pure_punct = all(unicodedata.category(c).startswith(('P', 'S')) for c in stripped)

        if is_pure_punct and not is_bullet_or_allowed:
            soup_chars += len(stripped) * 2
            noise_tokens.append(stripped)
        elif re.search(r'([.,;:!?|\(\)\[\]{}])\1+', stripped):
            # Repeated punctuation like ';;' or '..'
            soup_chars += len(stripped) * 2
            noise_tokens.append(stripped)
        elif len(stripped) <= 2 and any(unicodedata.category(c).startswith('P') for c in stripped) and not is_bullet_or_allowed:
            # Short fragment containing punctuation like 'h)'
            soup_chars += len(stripped) * 2
            noise_tokens.append(stripped)
        elif len(stripped) <= 2 and stripped.isalnum() and not stripped.isdigit():
            # 1-2 char word not in valid list
            if stripped.lower() not in VALID_SHORT_WORDS:
                soup_chars += len(stripped)
                noise_tokens.append(stripped)

    soup_ratio = soup_chars / total_len

    # If the text has very low alphanumeric ratio (< 0.40), apply low_alnum_penalty
    alnum_count = sum(1 for c in non_space_chars if c.isalnum())
    low_alnum_penalty = 0.0
    if len(non_space_chars) >= 6 and (alnum_count / len(non_space_chars)) < 0.40:
        low_alnum_penalty = (0.40 - (alnum_count / len(non_space_chars)))

    # Composite garbage ratio
    composite = min(
        1.0,
        (unicode_ratio * 1.5) +
        (rep_ratio * 1.0) +
        (soup_ratio * 0.9) +
        low_alnum_penalty
    )

    return {
        "ratio": round(composite, 4),
        "unicode_ratio": round(unicode_ratio, 4),
        "rep_ratio": round(rep_ratio, 4),
        "soup_ratio": round(soup_ratio, 4),
        "low_alnum_penalty": round(low_alnum_penalty, 4),
        "noise_tokens": noise_tokens
    }


def compute_garbage_ratio(text: str) -> float:
    """
    Measures ratio of non-printable, unicode corrupt, or fragmented OCR garbage.
    Returns float in range [0.0, 1.0].
    """
    return compute_garbage_details(text)["ratio"]
