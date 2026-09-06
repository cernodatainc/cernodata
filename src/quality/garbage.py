"""
src/quality/garbage.py

Garbage character ratio & non-printable character metrics.
"""

import string


def compute_garbage_ratio(text: str) -> float:
    """
    Measures ratio of non-printable or suspicious control characters.
    Returns float in range [0.0, 1.0].
    """
    if not text:
        return 0.0
    printable_count = sum(1 for c in text if c in string.printable or c.isprintable())
    garbage_count = len(text) - printable_count
    return garbage_count / len(text)
