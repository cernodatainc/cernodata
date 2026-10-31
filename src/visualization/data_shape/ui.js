/**
 * src/visualization/data_shape/ui.js
 *
 * Questionnaire grid rendering, preset ranking card generation,
 * threshold slider bindings, and user feedback banners.
 */

/**
 * Toggles disabled state and visual opacity of language code selection.
 */
function toggleLanguageHint() {
    const enabled = document.getElementById("enableLangHint").checked;
    const select = document.getElementById("langCode");
    select.disabled = !enabled;
    select.classList.toggle("lang-select-disabled", !enabled);
    select.style.opacity = enabled ? "1" : "0.5";
}

/**
 * Renders selectable option card tiles into the specified grid container.
 *
 * @param {string} containerId - DOM element ID for container.
 * @param {Array<[string, string]>} options - Array of [key, description] pairs.
 * @param {string} selectedValue - Currently active option key.
 * @param {Function} onSelectCallback - Handler called when an option card is clicked.
 */
function renderOptionGrid(containerId, options, selectedValue, onSelectCallback) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";
    options.forEach(([key, desc]) => {
        const card = document.createElement("div");
        card.className = "option-card" + (key === selectedValue ? " selected" : "");
        card.onclick = () => {
            onSelectCallback(key);
            renderOptionGrid(containerId, options, key, onSelectCallback);
            if (typeof recalculate === 'function') recalculate();
        };

        card.innerHTML = `
            <div class="card-header">
                <div class="card-title-group">
                    <div class="card-title">${escapeHtml(key)}</div>
                    <div class="help-btn" tabindex="0" title="${escapeHtml(desc)}">
                        <span class="help-icon">?</span>
                    </div>
                </div>
                <div class="radio-indicator"></div>
            </div>
        `;
        container.appendChild(card);
    });
}

/**
 * Updates floating numeric display when confidence threshold slider moves.
 *
 * @param {string|number} val - Target threshold numeric value.
 */
function updateThreshold(val) {
    const formatted = parseFloat(val).toFixed(2);
    const disp1 = document.getElementById("complexThresholdDisplay");
    const disp2 = document.getElementById("thresholdDisplay");
    if (disp1) disp1.textContent = formatted;
    if (disp2) disp2.textContent = formatted;

    const s1 = document.getElementById("inpThreshold");
    const s2 = document.getElementById("thresholdSlider");
    if (s1 && s1.value !== String(val)) s1.value = val;
    if (s2 && s2.value !== String(val)) s2.value = val;
}

/**
 * Handler for user selection changes in the primary preset override dropdown.
 */
function onOverrideChanged() {
    const overrideSel = document.getElementById("overrideSelect");
    if (!overrideSel) return;
    const val = overrideSel.value;
    overridePrimary = (val === "auto") ? null : val;

    const inpPreset = document.getElementById("inpPreset");
    if (inpPreset && val !== "auto") {
        for (let opt of inpPreset.options) {
            if (opt.value === val) {
                inpPreset.value = val;
                break;
            }
        }
    }
    renderPresetsList();
}

/**
 * Handler for changes in the ingestion preset selector to synchronize override state.
 */
function onInpPresetChanged() {
    const inpPreset = document.getElementById("inpPreset");
    if (!inpPreset) return;
    const val = inpPreset.value;

    const overrideSel = document.getElementById("overrideSelect");
    if (overrideSel) {
        overrideSel.value = val;
        overridePrimary = (val === "auto") ? null : val;
    }
    renderPresetsList();
}

/**
 * Renders the ranked preset cards in the right-hand preview sidebar.
 */
function renderPresetsList() {
    const container = document.getElementById("presetsList");
    if (!container) return;
    container.innerHTML = "";

    let displayOrder = [...suggestedOrder];
    if (overridePrimary && overridePrimary !== suggestedOrder[0]) {
        displayOrder = [overridePrimary, ...suggestedOrder.filter(p => p !== overridePrimary)];
    }

    const primBadge = document.getElementById("planPrimaryBadge");
    const fbBadge = document.getElementById("planFallbackBadge");
    if (primBadge && displayOrder.length > 0) {
        primBadge.textContent = displayOrder[0];
    }
    if (fbBadge && displayOrder.length > 1) {
        fbBadge.textContent = displayOrder[1];
    }

    displayOrder.forEach((preset, idx) => {
        const isPrimary = (idx === 0);
        const score = currentScores[preset] || 0.5;
        const pct = Math.round(score * 100);

        const item = document.createElement("div");
        item.className = "preset-item " + (isPrimary ? "primary" : "fallback");

        const tagText = isPrimary ? "Primary Candidate" : `Fallback ${idx}`;
        const tagClass = isPrimary ? "primary-tag" : "fallback-tag";

        item.innerHTML = `
            <div class="preset-row">
                <div class="preset-name">${escapeHtml(preset)}</div>
                <div class="preset-tag ${tagClass}">${tagText}</div>
            </div>
            <div class="score-bar-bg">
                <div class="score-bar-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="score-num">Suitability: ${score.toFixed(3)} (${pct}%)</div>
        `;
        container.appendChild(item);
    });
}

/**
 * Displays status or error feedback message banner.
 *
 * @param {string} text - Banner text to display.
 * @param {string} type - Banner category ('success' or 'error').
 */
function showBanner(text, type) {
    const banner = document.getElementById("statusBanner");
    if (!banner) return;
    banner.textContent = text;
    banner.className = "status-banner " + type;
}

/**
 * Escapes unsafe HTML characters.
 *
 * @param {string} str - Raw string.
 * @returns {string} Sanitized string.
 */
function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * No-op UI hook for rendering the interactive Dataset Topic Balance questionnaire card in the Wizard.
 *
 * @param {Object|null} skewReport - Topic distribution skew summary from /api/calculate_scores.
 */
function renderCorpusBalanceQuestionnaireCard(skewReport) {
    // TODO(TASK-606): Render the visual topic proportion bars (e.g. Topic A vs. Topic B) and 3-option
    // plain-English intent selector (Keep as-is vs. Balance equally vs. Auto-deduplicate & cap) in the Wizard UI.
    void skewReport;
}
