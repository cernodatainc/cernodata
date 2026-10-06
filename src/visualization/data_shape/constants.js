/**
 * src/visualization/data_shape/constants.js
 *
 * Preset weight matrices, document taxonomy categories, target objectives,
 * and security constraint options for the data shape wizard.
 */

/**
 * Compatibility and performance weight matrix mapping preset options to document profiles.
 * Derived from cernodata planner configuration specifications.
 */
const PRESET_WEIGHTS = {
    "pypdfium_rapidocr": {
        "rapid_approximate": 0.85,
        "general_text": 0.80,
        "financial_report": 0.70,
        "multicolumn_article": 0.75,
        "scanned_form": 0.65,
        "tabular_ledger": 0.65,
        "mixed_text_image": 0.60,
        "air_gapped_local": 0.90,
        "high_precision_structure": 0.60,
        "hosted_vision_api": 0.50
    },
    "docling_fast": {
        "rapid_approximate": 0.80,
        "financial_report": 0.60,
        "scanned_form": 0.30,
        "air_gapped_local": 0.90,
        "hosted_vision_api": 0.50,
        "multicolumn_article": 0.70,
        "tabular_ledger": 0.60,
        "mixed_text_image": 0.50,
        "general_text": 0.85,
        "high_precision_structure": 0.50
    },
    "docling_deep": {
        "high_precision_structure": 0.85,
        "financial_report": 0.85,
        "tabular_ledger": 0.90,
        "multicolumn_article": 0.85,
        "scanned_form": 0.75,
        "mixed_text_image": 0.70,
        "general_text": 0.80,
        "air_gapped_local": 0.85,
        "hosted_vision_api": 0.70,
        "rapid_approximate": 0.40
    },
    "vision_llm_direct": {
        "scanned_form": 0.95,
        "mixed_text_image": 0.90,
        "high_precision_structure": 0.90,
        "financial_report": 0.70,
        "tabular_ledger": 0.65,
        "multicolumn_article": 0.75,
        "general_text": 0.60,
        "rapid_approximate": 0.30,
        "air_gapped_local": 0.30,
        "hosted_vision_api": 0.95
    }
};

/**
 * Document taxonomy profile choices displayed in Step 1.
 */
const TAXONOMY_OPTIONS = [
    ["financial_report", "Dense numbers, tables, multi-page financial statements"],
    ["multicolumn_article", "Academic or corporate papers with 2+ text columns"],
    ["scanned_form", "Low-DPI scanned documents, hand-signed forms, low contrast"],
    ["tabular_ledger", "Spreadsheet-like grid structures"],
    ["mixed_text_image", "Marketing materials, slide decks, embedded graphics"],
    ["general_text", "Standard single or multi-page prose documents"]
];

/**
 * Processing objective priorities displayed in Step 2.
 */
const TARGET_OPTIONS = [
    ["rapid_approximate", "Fast throughput, acceptable minor structural drift"],
    ["high_precision_structure", "Maximum layout fidelity, exact bounding box extraction"]
];

/**
 * Deployment and data security constraints displayed in Step 3.
 */
const SECURITY_OPTIONS = [
    ["air_gapped_local", "Zero external network calls (strictly local models)"],
    ["hosted_vision_api", "Cloud multimodal APIs allowed (hosted vision models)"]
];
