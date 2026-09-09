"""
src/quality/languages/definitions.py

Loads language configuration models from languages.json into LanguageConfig dataclasses.
Provides registry management and language retrieval routines.
"""

import os
import json
from typing import Dict, Optional, Any
from src.quality.languages.models import LanguageConfig

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configurations")
_LEGACY_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "languages.json")


def _build_language_config(data: Dict[str, Any]) -> LanguageConfig:
    return LanguageConfig(
        code=data["code"],
        name=data["name"],
        valid_diacritics=set(data.get("valid_diacritics", "")),
        common_substitutions=data.get("common_substitutions", {}),
        anomalous_chars=data.get("anomalous_chars", {}),
        allowed_anomalous_tokens=set(data.get("allowed_anomalous_tokens", [])),
        conflicting_diacritic_replacements=data.get("conflicting_diacritic_replacements", {}),
        common_word_corrections=data.get("common_word_corrections", {}),
        stopwords=set(data.get("stopwords", [])),
        min_words_for_diacritic_check=data.get("min_words_for_diacritic_check", 12)
    )


def load_all_language_configs(config_dir: Optional[str] = None) -> Dict[str, LanguageConfig]:
    """Loads and instantiates all LanguageConfig instances from per-language directories in configurations/."""
    base_dir = config_dir or _CONFIG_DIR
    configs: Dict[str, LanguageConfig] = {}

    if os.path.isdir(base_dir):
        for entry in os.listdir(base_dir):
            entry_path = os.path.join(base_dir, entry)
            if os.path.isdir(entry_path):
                cfg_file = os.path.join(entry_path, "config.json")
                if os.path.isfile(cfg_file):
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cfg = _build_language_config(data)
                    configs[cfg.code.lower().strip()] = cfg

    # Fallback to legacy languages.json if configurations directory was empty or missing
    if not configs and os.path.isfile(_LEGACY_CONFIG_PATH):
        with open(_LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        configs = {code: _build_language_config(cfg_dict) for code, cfg_dict in raw.items()}

    return configs


LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = load_all_language_configs()

POLISH_CONFIG: LanguageConfig = LANGUAGE_CONFIGS["pl"]
GERMAN_CONFIG: LanguageConfig = LANGUAGE_CONFIGS["de"]
FRENCH_CONFIG: LanguageConfig = LANGUAGE_CONFIGS["fr"]
SPANISH_CONFIG: LanguageConfig = LANGUAGE_CONFIGS["es"]
ENGLISH_CONFIG: LanguageConfig = LANGUAGE_CONFIGS["en"]


def get_language_config(language: str) -> Optional[LanguageConfig]:
    """Retrieves language configuration for the given language code."""
    if not language:
        return None
    return LANGUAGE_CONFIGS.get(language.lower().strip())


def register_language_config(config: LanguageConfig) -> None:
    """Registers or overrides a language configuration."""
    LANGUAGE_CONFIGS[config.code.lower().strip()] = config
