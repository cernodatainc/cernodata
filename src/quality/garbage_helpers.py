"""
src/quality/garbage_helpers.py

Helper functions and character dictionaries for OCR garbage detection and anomaly scoring.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Set, Tuple

# Allowed standalone symbols / bullet points and standard ellipses
ALLOWED_STANDALONE: Set[str] = {
    '*', '-', '–', '—', '•', '+', '/', '&', '%', '$', '€', '£', '§', '©', '®', ':', '=',
    '...', '…'
}

# Common allowed 1-2 letter words across supported languages (PL, EN, DE)
VALID_SHORT_WORDS: Set[str] = {
    'iv', 'vi', 'ix', 'xi',
    # Polish
    'a', 'i', 'o', 'u', 'w', 'z',
    'od', 'do', 'po', 'na', 'za', 'ze', 'we', 'ku', 'tu', 'to', 'ta', 'te',
    'ci', 'co', 'mu', 'go', 'ma', 'im', 'ja', 'ty', 'on', 'my', 'wy', 'iż',
    'aż', 'bo', 'że', 'ni', 'no', 'ba', 'or', 'al', 'np', 'zł', 'gr', 'nr',
    'ul', 'je', 'ją', 'tę', 'sa', 'sp', 'pl', 'eu',
    # English (additional distinct)
    'in', 'at', 'by', 'for', 'of', 'is', 'it', 'as', 'an', 'be',
    'he', 'me', 'us', 'so', 'if', 'up', 'am', 'ok',
    # German (additional distinct)
    'er', 'es', 'um', 'zu', 'ab', 'ob', 'da', 'wo', 'du',
}


def evaluate_unicode_anomalies(text: str) -> int:
    """Counts Unicode replacement characters, private use codepoints, and raw control characters."""
    return sum(
        1 for c in text
        if c == '\ufffd'
        or ('\ue000' <= c <= '\uf8ff')
        or ('\U000f0000' <= c <= '\U0010ffff')
        or (unicodedata.category(c).startswith('C') and c not in '\n\r\t')
    )


def evaluate_character_repetitions(text: str) -> int:
    """Counts characters participating in runs of 4 or more identical consecutive characters."""
    return sum(len(m.group(0)) for m in re.finditer(r'(.)\1{3,}', text))


def evaluate_punctuation_soup_and_noise(text: str, tokens: List[str]) -> Tuple[int, List[str]]:
    """Evaluates unmatched brackets, isolated punctuation soup, and invalid short tokens."""
    open_parens = text.count('(')
    close_parens = text.count(')')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    unmatched_parens = abs(close_parens - open_parens) + abs(close_brackets - open_brackets)

    soup_chars = unmatched_parens * 2
    noise_tokens: List[str] = []

    for t in tokens:
        stripped = t.strip()
        if not stripped:
            continue

        is_bullet_or_allowed = stripped in ALLOWED_STANDALONE
        is_pure_punct = all(unicodedata.category(c).startswith(('P', 'S')) for c in stripped)
        clean_punct = re.sub(r'\.{2,4}$', '', stripped).rstrip('…')

        if is_pure_punct and not is_bullet_or_allowed:
            soup_chars += len(stripped) * 2
            noise_tokens.append(stripped)
        elif clean_punct and re.search(r'([.,;:!?|\(\)\[\]{}])\1+', clean_punct):
            # Repeated punctuation like ';;' or ',,' (excluding legitimate trailing ellipses)
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

    return soup_chars, noise_tokens


def compute_low_alnum_penalty(non_space_chars: List[str]) -> float:
    """Computes penalty if alphanumeric character ratio is below 40% in passages of 6+ characters."""
    if len(non_space_chars) < 6:
        return 0.0
    alnum_count = sum(1 for c in non_space_chars if c.isalnum())
    ratio = alnum_count / len(non_space_chars)
    if ratio < 0.40:
        return 0.40 - ratio
    return 0.0
