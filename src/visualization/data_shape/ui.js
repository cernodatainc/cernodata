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
    const targetPreset = overridePrimary || (suggestedOrder && suggestedOrder.length > 0 ? suggestedOrder[0] : "docling_fast");
    if (inpPreset && targetPreset) {
        for (let opt of inpPreset.options) {
            if (opt.value === targetPreset) {
                inpPreset.value = targetPreset;
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
    overridePrimary = (val === "auto") ? null : val;

    const overrideSel = document.getElementById("overrideSelect");
    if (overrideSel) {
        overrideSel.value = overridePrimary || "auto";
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

    const inpPreset = document.getElementById("inpPreset");
    if (inpPreset && displayOrder.length > 0) {
        for (let opt of inpPreset.options) {
            if (opt.value === displayOrder[0]) {
                inpPreset.value = displayOrder[0];
                break;
            }
        }
    }
    const overrideSel = document.getElementById("overrideSelect");
    if (overrideSel) {
        overrideSel.value = overridePrimary || "auto";
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
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

window._customPresetCatalog = window._customPresetCatalog || [];

/**
 * Appends or updates a custom preset option in the Run & Planner preset dropdowns.
 *
 * @param {Object} preset - Serialized CustomPresetConfig dictionary.
 */
function appendCustomPresetOption(preset) {
    if (!preset || !preset.preset_id) return;
    const presetId = String(preset.preset_id);
    const displayName = String(preset.display_name || presetId);
    const targets = [
        { id: "inpPreset", label: `${presetId} (Custom: ${displayName})` },
        { id: "overrideSelect", label: `${presetId} (Custom)` },
    ];
    for (const target of targets) {
        const sel = document.getElementById(target.id);
        if (!sel) continue;
        let opt = Array.from(sel.options).find(o => o.value === presetId);
        if (!opt) {
            opt = document.createElement("option");
            opt.value = presetId;
            sel.appendChild(opt);
        }
        opt.textContent = target.label;
    }
}

/**
 * Renders a feedback status message inside the custom preset builder modal.
 *
 * @param {string} message - Feedback text to show.
 * @param {string} kind - Style class ('success' or 'error').
 */
function _setCustomPresetStatus(message, kind) {
    const el = document.getElementById("cpTestResult");
    if (!el) return;
    if (!message) {
        el.textContent = "";
        el.className = "custom-preset-status hidden";
        return;
    }
    el.textContent = message;
    el.className = "custom-preset-status " + (kind === "success" ? "success" : "error");
}

/**
 * Populates recipe selector options, dropdown presets, and planner weights from catalog data.
 *
 * @param {Array<Object>} catalog - Combined user & community custom preset list.
 * @param {Object|null} presetWeights - Merged planner suitability weights map.
 */
function hydrateCustomPresetUi(catalog, presetWeights) {
    if (presetWeights && typeof PRESET_WEIGHTS !== "undefined") {
        Object.assign(PRESET_WEIGHTS, presetWeights);
    }
    const items = Array.isArray(catalog) ? catalog : [];
    window._customPresetCatalog = items;

    const recipeSel = document.getElementById("cpRecipeSelect");
    if (recipeSel) {
        recipeSel.innerHTML = '<option value="">-- Start from scratch or choose a recipe --</option>';
        items.forEach((item, idx) => {
            if (!item || !item.preset_id) return;
            const opt = document.createElement("option");
            opt.value = String(idx);
            const prefix = item.source === "user" ? "[Saved] " : "[Recipe] ";
            opt.textContent = prefix + (item.display_name || item.preset_id);
            recipeSel.appendChild(opt);
        });
    }

    for (const item of items) {
        if (!item || item.source !== "user") continue;
        appendCustomPresetOption(item);
        if (item.suitability_weights && typeof PRESET_WEIGHTS !== "undefined") {
            PRESET_WEIGHTS[item.preset_id] = item.suitability_weights;
        }
    }

    if (typeof recalculate === "function") {
        recalculate();
    }
}

/**
 * Loads custom presets from /api/presets if not yet cached and populates the modal UI.
 *
 * @param {Array<Object>|null} catalogOverride - Optional pre-fetched catalog array.
 */
async function setupCustomPresetBuilderModal(catalogOverride) {
    onCustomPresetBackendTypeChanged();
    if (Array.isArray(catalogOverride) && catalogOverride.length > 0) {
        hydrateCustomPresetUi(catalogOverride, null);
        return;
    }
    if (Array.isArray(window._customPresetCatalog) && window._customPresetCatalog.length > 0) {
        hydrateCustomPresetUi(window._customPresetCatalog, null);
        return;
    }
    try {
        const res = await fetch("/api/presets");
        if (!res.ok) return;
        const data = await res.json();
        const catalog = Array.isArray(data.catalog) ? data.catalog : [];
        hydrateCustomPresetUi(catalog, null);
    } catch (e) {
        // Offline standalone fallback
    }
}

if (typeof window.initCustomPresetBuilderModal !== "function") {
    window.initCustomPresetBuilderModal = setupCustomPresetBuilderModal;
}

/**
 * Opens the Custom OCR Preset Builder modal dialog.
 */
function openCustomPresetBuilderModal() {
    const modal = document.getElementById("customPresetBuilderModal");
    if (!modal) return;
    _setCustomPresetStatus("", "success");
    modal.classList.remove("hidden");
    onCustomPresetBackendTypeChanged();
    setupCustomPresetBuilderModal(null);
}

/**
 * Closes the Custom OCR Preset Builder modal dialog.
 */
function closeCustomPresetBuilderModal() {
    const modal = document.getElementById("customPresetBuilderModal");
    if (modal) modal.classList.add("hidden");
}

/**
 * Toggles CLI vs HTTP endpoint fields when the user switches backend mode.
 */
function onCustomPresetBackendTypeChanged() {
    const backendEl = document.getElementById("cpBackendType");
    const cliEl = document.getElementById("cpCliFields");
    const httpEl = document.getElementById("cpHttpFields");
    if (!backendEl || !cliEl || !httpEl) return;
    const isHttp = backendEl.value === "http_endpoint";
    cliEl.classList.toggle("hidden", isHttp);
    httpEl.classList.toggle("hidden", !isHttp);
}

/**
 * Pre-fills builder modal fields when a community recipe or saved preset is chosen.
 */
function onCustomPresetRecipeSelected() {
    const recipeSel = document.getElementById("cpRecipeSelect");
    if (!recipeSel || recipeSel.value === "") return;
    const item = window._customPresetCatalog[parseInt(recipeSel.value, 10)];
    if (!item) return;

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val !== undefined && val !== null ? String(val) : "";
    };
    setVal("cpPresetId", item.preset_id);
    setVal("cpDisplayName", item.display_name);
    setVal("cpBackendType", item.backend_type || "cli_subprocess");
    setVal("cpOutputFormat", item.output_format || "text");
    setVal("cpHardwareWeight", item.hardware_weight || "light_cpu");
    setVal("cpTimeoutSec", item.timeout_sec || 120);
    setVal("cpEndpointUrl", item.endpoint_url || "");
    setVal("cpTaxonomyHints", Array.isArray(item.taxonomy_hints) ? item.taxonomy_hints.join(", ") : "");
    setVal("cpDescription", item.description || "");

    const cmdTokens = Array.isArray(item.command_template) ? item.command_template : [];
    const cmdStr = cmdTokens
        .map(tok => /\s/.test(String(tok)) ? '"' + String(tok).replace(/"/g, '\\"') + '"' : String(tok))
        .join(" ");
    setVal("cpCommandTemplate", cmdStr);
    onCustomPresetBackendTypeChanged();
    _setCustomPresetStatus("", "success");
}

/**
 * Reads current modal inputs into a CustomPresetConfig JSON payload.
 */
function _readCustomPresetFormPayload() {
    const val = id => {
        const el = document.getElementById(id);
        return el ? String(el.value || "").trim() : "";
    };
    const backendType = val("cpBackendType") || "cli_subprocess";
    const hintsRaw = val("cpTaxonomyHints");
    const taxonomyHints = hintsRaw ? hintsRaw.split(",").map(s => s.trim()).filter(Boolean) : [];
    const timeoutVal = parseInt(val("cpTimeoutSec"), 10);

    return {
        preset_id: val("cpPresetId"),
        display_name: val("cpDisplayName") || val("cpPresetId"),
        backend_type: backendType,
        command_template: backendType === "cli_subprocess" ? val("cpCommandTemplate") : null,
        endpoint_url: backendType === "http_endpoint" ? val("cpEndpointUrl") : null,
        output_format: val("cpOutputFormat") || "text",
        hardware_weight: val("cpHardwareWeight") || "light_cpu",
        timeout_sec: Number.isFinite(timeoutVal) && timeoutVal > 0 ? timeoutVal : 120,
        taxonomy_hints: taxonomyHints,
        description: val("cpDescription"),
    };
}

/**
 * Sends a connectivity probe for the draft preset to /api/presets/test.
 */
async function testCustomPresetConnection() {
    const payload = _readCustomPresetFormPayload();
    _setCustomPresetStatus("Testing connection...", "success");
    try {
        const res = await fetch("/api/presets/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok && data.reachable) {
            _setCustomPresetStatus(data.message || "Connection test succeeded.", "success");
        } else {
            _setCustomPresetStatus(data.error || "Connection test failed.", "error");
        }
    } catch (err) {
        _setCustomPresetStatus("Network error while testing connection: " + err.message, "error");
    }
}

/**
 * Saves and registers the custom preset via POST /api/presets, refreshing planner weights and selectors.
 */
async function saveCustomPresetFromModal() {
    const payload = _readCustomPresetFormPayload();
    if (!payload.preset_id) {
        _setCustomPresetStatus("Preset ID is required.", "error");
        return;
    }
    try {
        const res = await fetch("/api/presets", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            _setCustomPresetStatus(data.error || "Failed to save custom preset.", "error");
            return;
        }
        const saved = data.preset;
        if (saved) {
            appendCustomPresetOption(saved);
            if (data.suitability_weights && typeof PRESET_WEIGHTS !== "undefined") {
                PRESET_WEIGHTS[saved.preset_id] = data.suitability_weights;
            }
            const inpPreset = document.getElementById("inpPreset");
            if (inpPreset) inpPreset.value = saved.preset_id;
        }
        if (Array.isArray(data.custom_presets)) {
            hydrateCustomPresetUi(data.custom_presets, null);
        } else if (typeof recalculate === "function") {
            recalculate();
        }
        if (typeof showBanner === "function" && saved) {
            showBanner(`Custom preset '${saved.preset_id}' registered.`, "success");
        }
        closeCustomPresetBuilderModal();
    } catch (err) {
        _setCustomPresetStatus("Failed to save custom preset: " + err.message, "error");
    }
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
