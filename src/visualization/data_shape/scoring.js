/**
 * src/visualization/data_shape/scoring.js
 *
 * Scoring algorithm, ranking calculation, and state management
 * for the interactive preset planner wizard.
 */

let selectedTaxonomy = "general_text";
let selectedTarget = "high_precision_structure";
let selectedSecurity = "air_gapped_local";
let currentScores = {};
let suggestedOrder = [];
let overridePrimary = null;

/**
 * Computes mean suitability score in [0.0, 1.0] for each pipeline preset
 * based on selected questionnaire dimensions.
 *
 * @param {string} taxonomy - Document taxonomy key.
 * @param {string} target - Extraction target objective key.
 * @param {string} security - Security constraint key.
 * @returns {Object.<string, number>} Map of preset identifiers to suitability scores.
 */
function calculateSuitabilityScores(taxonomy, target, security) {
    const answers = [taxonomy, target, security];
    const scores = {};

    for (const [presetId, weightMap] of Object.entries(PRESET_WEIGHTS)) {
        let sum = 0;
        for (const ans of answers) {
            sum += (weightMap[ans] !== undefined) ? weightMap[ans] : 0.50;
        }
        scores[presetId] = Math.round((sum / answers.length) * 1000) / 1000;
    }
    return scores;
}

/**
 * Re-evaluates suitability scores across all presets and updates the ranking display.
 */
function recalculate() {
    currentScores = calculateSuitabilityScores(selectedTaxonomy, selectedTarget, selectedSecurity);
    suggestedOrder = Object.keys(currentScores).sort((a, b) => currentScores[b] - currentScores[a]);
    if (typeof renderPresetsList === 'function') {
        renderPresetsList();
    }
}
