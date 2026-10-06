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
                <div class="card-title">${escapeHtml(key)}</div>
                <div class="radio-indicator"></div>
            </div>
            <div class="card-desc">${escapeHtml(desc)}</div>
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
    const el = document.getElementById("thresholdDisplay");
    if (el) el.textContent = parseFloat(val).toFixed(2);
}

/**
 * Handler for user selection changes in the primary preset override dropdown.
 */
function onOverrideChanged() {
    const val = document.getElementById("overrideSelect").value;
    overridePrimary = (val === "auto") ? null : val;
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

    displayOrder.forEach((preset, idx) => {
        const isPrimary = (idx === 0);
        const score = currentScores[preset] || 0.5;
        const pct = Math.round(score * 100);

        const item = document.createElement("div");
        item.className = "preset-item " + (isPrimary ? "primary" : "fallback");

        const tagText = isPrimary ? "[Primary Candidate]" : `[Fallback ${idx}]`;
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
