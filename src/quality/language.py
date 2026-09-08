"""
src/quality/language.py

Tier 2 Language & Dictionary Verification rules and diacritic anomaly metrics.
"""

import re
from typing import Optional, List, Dict, Tuple, Any
from src.quality.language_config import (
    LanguageConfig,
    LANGUAGE_CONFIGS,
    ALL_KNOWN_DIACRITICS,
    get_language_config,
    register_language_config
)
from src.dom import DOMNode, DocumentDOM

LANGUAGE_DIACRITICS = {
    code: cfg.valid_diacritics
    for code, cfg in LANGUAGE_CONFIGS.items()
    if cfg.valid_diacritics
}

LANGUAGE_STOPWORDS: Dict[str, set[str]] = {
    "pl": {
        "w", "z", "i", "na", "do", "nie", "się", "jest", "jak", "to", "od", "dla", "po",
        "oraz", "że", "o", "przez", "ale", "ze", "czy", "co", "za", "ich", "tym", "pan",
        "pani", "rok", "roku", "jego", "jej", "ma", "może", "tak", "tylko", "więcej", "już",
        "też", "lub", "albo", "nad", "pod", "przed", "między", "bez", "gdy", "jeśli", "tam",
        "tu", "tutaj", "gdzie", "który", "która", "które", "którzy", "ten", "ta", "te",
        "bardzo", "jeszcze", "można", "być", "są", "był", "była", "było", "byli", "będzie",
        "mają", "miał", "miała", "miało", "mieli", "więc", "aż", "ci", "mu", "go", "nas",
        "was", "nich", "nam", "wam", "im", "sobą", "sobie", "czym", "kim", "jaki", "jaka",
        "jakie", "my", "wy", "oni", "one", "nasz", "wasz", "swój", "swoja", "swoje", "swoich"
    },
    "fr": {
        "le", "la", "les", "des", "du", "de", "un", "une", "et", "dans", "pour", "avec",
        "sur", "au", "aux", "qui", "que", "est", "son", "sa", "ses", "en", "pas", "ce",
        "cette", "ces", "mais", "ou", "où", "par", "nous", "vous", "ils", "elles", "tout",
        "plus", "leur", "leurs", "comme", "ne", "ont", "sont", "être", "avoir", "fait",
        "très", "bien", "sans", "sous", "même", "aussi"
    },
    "de": {
        "der", "die", "das", "und", "in", "den", "von", "zu", "dem", "mit", "sich", "des",
        "auf", "für", "ist", "im", "nicht", "ein", "eine", "einer", "einem", "einen", "als",
        "auch", "es", "an", "werden", "aus", "er", "hat", "dass", "sie", "nach", "wird",
        "bei", "noch", "wie", "oder", "über", "so", "nur", "aber", "vor", "durch", "man"
    },
    "es": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "en", "y", "a",
        "que", "por", "con", "para", "como", "es", "su", "sus", "al", "lo", "del", "más",
        "no", "se", "pero", "este", "esta", "estos", "estas", "entre", "cuando", "todo",
        "todos", "son", "sobre", "ya", "si", "bien", "sin", "muy", "hay", "me", "te"
    },
    "en": {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not",
        "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from",
        "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would",
        "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which",
        "go", "me", "when", "make", "can", "like", "time", "no", "just", "him", "know",
        "take", "people", "into", "year", "your", "good", "some", "could", "them", "see",
        "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
        "also", "back", "after", "use", "two", "how", "our", "work", "first", "well",
        "way", "even", "new", "want", "because", "any", "these", "give", "day", "most", "us"
    }
}


def detect_text_language(text: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Auto-detects the probable language (en, pl, de, fr, es) for a text passage.
    Returns: (detected_code, confidence_score, scores_dict).
    """
    if not text or not text.strip():
        return "en", 1.0, {"en": 1.0, "pl": 0.0, "de": 0.0, "fr": 0.0, "es": 0.0}

    tokens = re.findall(r"\b\w+\b", text.lower())
    scores: Dict[str, float] = {code: 0.0 for code in ("pl", "de", "fr", "es", "en")}

    for char in text:
        if char in ALL_KNOWN_DIACRITICS:
            scores["en"] -= 4.0
            for code, diacritics in LANGUAGE_DIACRITICS.items():
                if char in diacritics:
                    scores[code] += 3.0
                else:
                    scores[code] -= 1.5

    for token in tokens:
        for code, stopwords in LANGUAGE_STOPWORDS.items():
            if token in stopwords:
                scores[code] += 2.0

    # Ensure scores are non-negative
    for code in scores:
        scores[code] = max(0.0, scores[code])

    total_score = sum(scores.values())
    if total_score <= 0.0:
        return "en", 1.0, {c: (1.0 if c == "en" else 0.0) for c in scores}

    # Normalize scores
    norm_scores = {code: round(score / total_score, 4) for code, score in scores.items()}
    best_lang = max(norm_scores, key=lambda k: norm_scores[k])
    confidence = norm_scores[best_lang]

    return best_lang, confidence, norm_scores


def detect_page_language(nodes: List[DOMNode]) -> Tuple[str, float, Dict[str, float]]:
    """
    Auto-detects the dominant language across all nodes on a specific page.
    """
    combined_text = " ".join(
        node.content.get("raw_text", "")
        for node in nodes
        if node.content and node.content.get("raw_text")
    )
    return detect_text_language(combined_text)


def detect_document_languages(dom: DocumentDOM) -> Dict[int, str]:
    """
    Maps each page number in a DocumentDOM to its detected language code.
    """
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    page_languages: Dict[int, str] = {}
    for page_no, nodes in pages_nodes.items():
        lang, _, _ = detect_page_language(nodes)
        page_languages[page_no] = lang

    return page_languages


def compute_language_score(
    text: str, language: str = "en", diacritic_hit: Optional[float] = None
) -> float:
    """
    Tier 2 Language & Dictionary Verification:
    Evaluates text fidelity against specified language norms, detecting common OCR
    diacritic substitution errors and foreign diacritic conflicts.
    """
    lang = language.lower().strip()
    if not text or lang == "en":
        return 1.0

    config = get_language_config(lang)
    if config:
        return config.compute_score(text, diacritic_hit=diacritic_hit)

    return 1.0

