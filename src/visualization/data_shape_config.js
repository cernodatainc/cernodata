// Preset weight matrices loaded from cernodata planner configuration
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

const TAXONOMY_OPTIONS = [
    ["financial_report", "Dense numbers, tables, multi-page financial statements"],
    ["multicolumn_article", "Academic or corporate papers with 2+ text columns"],
    ["scanned_form", "Low-DPI scanned documents, hand-signed forms, low contrast"],
    ["tabular_ledger", "Spreadsheet-like grid structures"],
    ["mixed_text_image", "Marketing materials, slide decks, embedded graphics"],
    ["general_text", "Standard single or multi-page prose documents"]
];

const TARGET_OPTIONS = [
    ["rapid_approximate", "Fast throughput, acceptable minor structural drift"],
    ["high_precision_structure", "Maximum layout fidelity, exact bounding box extraction"]
];

const SECURITY_OPTIONS = [
    ["air_gapped_local", "Zero external network calls (strictly local models)"],
    ["hosted_vision_api", "Cloud multimodal APIs allowed (hosted vision models)"]
];

// State
let selectedTaxonomy = "general_text";
let selectedTarget = "high_precision_structure";
let selectedSecurity = "air_gapped_local";
let currentScores = {};
let suggestedOrder = [];
let overridePrimary = null;

function toggleLanguageHint() {
    const enabled = document.getElementById("enableLangHint").checked;
    const select = document.getElementById("langCode");
    select.disabled = !enabled;
    select.classList.toggle("lang-select-disabled", !enabled);
    select.style.opacity = enabled ? "1" : "0.5";
}

function renderOptionGrid(containerId, options, selectedValue, onSelectCallback) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    options.forEach(([key, desc]) => {
        const card = document.createElement("div");
        card.className = "option-card" + (key === selectedValue ? " selected" : "");
        card.onclick = () => {
            onSelectCallback(key);
            renderOptionGrid(containerId, options, key, onSelectCallback);
            recalculate();
        };

        card.innerHTML = `
            <div class="card-header">
                <div class="card-title">${key}</div>
                <div class="radio-indicator"></div>
            </div>
            <div class="card-desc">${desc}</div>
        `;
        container.appendChild(card);
    });
}

function updateThreshold(val) {
    document.getElementById("thresholdDisplay").textContent = parseFloat(val).toFixed(2);
}

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

function recalculate() {
    currentScores = calculateSuitabilityScores(selectedTaxonomy, selectedTarget, selectedSecurity);
    suggestedOrder = Object.keys(currentScores).sort((a, b) => currentScores[b] - currentScores[a]);
    renderPresetsList();
}

function onOverrideChanged() {
    const val = document.getElementById("overrideSelect").value;
    overridePrimary = (val === "auto") ? null : val;
    renderPresetsList();
}

function renderPresetsList() {
    const container = document.getElementById("presetsList");
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
                <div class="preset-name">${preset}</div>
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

async function submitPlan() {
    const docPath = document.getElementById("docPath").value.trim();
    const enableHint = document.getElementById("enableLangHint").checked;
    const language = enableHint ? document.getElementById("langCode").value : null;
    const threshold = parseFloat(document.getElementById("thresholdSlider").value);

    if (!docPath) {
        showBanner("Please specify a document file path before proceeding.", "error");
        document.getElementById("docPath").focus();
        return;
    }

    let effectiveOrder = [...suggestedOrder];
    if (overridePrimary && overridePrimary !== suggestedOrder[0]) {
        effectiveOrder = [overridePrimary, ...suggestedOrder.filter(p => p !== overridePrimary)];
    }

    const payload = {
        document_path: docPath,
        taxonomy: selectedTaxonomy,
        target: selectedTarget,
        security: selectedSecurity,
        language: language,
        target_threshold: threshold,
        override_primary: overridePrimary,
        override_order: effectiveOrder,
        scores: currentScores
    };

    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    submitBtn.textContent = "[SUBMITTING] Sending configuration...";

    try {
        const response = await fetch("/api/submit_plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showBanner("[SUCCESS] Data shape plan configured successfully. Starting pipeline execution...", "success");
            submitBtn.textContent = "[COMPLETED] Plan Active";
        } else {
            const err = await response.json().catch(() => ({}));
            showBanner("[ERROR] " + (err.error || "Failed to submit plan to server."), "error");
            submitBtn.disabled = false;
            submitBtn.textContent = "[SUBMIT PLAN] Start Pipeline Execution";
        }
    } catch (e) {
        // If offline or standalone file opened directly in browser without local server
        showBanner("[STANDALONE] Server connection offline. Generated plan JSON copied to console.", "success");
        console.log("DocumentPlan JSON:", JSON.stringify(payload, null, 2));
        submitBtn.disabled = false;
        submitBtn.textContent = "[SUBMIT PLAN] Start Pipeline Execution";
    }
}

let availablePreviousRuns = [];

function populatePreviousRunsDropdown(runs) {
    availablePreviousRuns = runs || [];
    const select = document.getElementById("prevRunSelect");
    if (!select) return;
    select.innerHTML = '<option value="">-- Choose output of a previous run --</option>' +
        availablePreviousRuns.map(r => `<option value="${escapeHtml(r.dir_path)}">${escapeHtml(r.label || r.dir_path)}</option>`).join('');
}

function onPreviousRunSelected(dirPath) {
    const run = availablePreviousRuns.find(r => r.dir_path === dirPath);
    const summaryEl = document.getElementById("prevRunSummary");
    const btnViewer = document.getElementById("btnInspectViewer");

    if (btnViewer) {
        btnViewer.href = dirPath ? `/viewer?output_dir=${encodeURIComponent(dirPath)}` : '/viewer';
    }

    if (!run) {
        if (summaryEl) summaryEl.style.display = "none";
        return;
    }

    if (summaryEl) {
        summaryEl.style.display = "block";
        const confStr = run.overall_confidence !== undefined ? Number(run.overall_confidence).toFixed(4) : "1.0000";
        summaryEl.innerHTML = `<strong>Selected Run:</strong> ${escapeHtml(run.dir_path)}<br>` +
            `<strong>Document:</strong> ${escapeHtml(run.document_name)} (${escapeHtml(run.document_path)})<br>` +
            `<strong>Chosen Preset:</strong> <code>${escapeHtml(run.chosen_preset)}</code> | ` +
            `<strong>Status:</strong> ${escapeHtml(run.status)} | ` +
            `<strong>Confidence:</strong> ${confStr} | ` +
            `<strong>Quality Violations:</strong> ${run.violations_count}`;
    }
}

async function loadSelectedPreviousRunIntoWizard() {
    const sel = document.getElementById("prevRunSelect");
    if (!sel || !sel.value) {
        showBanner("Please select a previous run from the dropdown first.", "error");
        return;
    }
    const dirPath = sel.value;
    try {
        const res = await fetch(`/api/load_run?output_dir=${encodeURIComponent(dirPath)}`);
        if (!res.ok) {
            showBanner(`Failed to load run from ${dirPath}`, "error");
            return;
        }
        const data = await res.json();
        const run = data.run || {};
        const plan = (run && run.plan) ? run.plan : (data.plan || {});
        const decision = (run && run.decision) ? run.decision : (data.decision || {});

        if (run.document_path) {
            document.getElementById("docPath").value = run.document_path;
        }
        if (decision.language) {
            document.getElementById("enableLangHint").checked = true;
            toggleLanguageHint();
            document.getElementById("langCode").value = decision.language;
        }
        if (decision.target_confidence_threshold) {
            updateThreshold(decision.target_confidence_threshold);
            document.getElementById("thresholdSlider").value = decision.target_confidence_threshold;
        }
        if (plan.taxonomy && TAXONOMY_OPTIONS.some(([k]) => k === plan.taxonomy)) {
            selectedTaxonomy = plan.taxonomy;
            renderOptionGrid("taxonomyGrid", TAXONOMY_OPTIONS, selectedTaxonomy, val => selectedTaxonomy = val);
        }
        if (plan.target && TARGET_OPTIONS.some(([k]) => k === plan.target)) {
            selectedTarget = plan.target;
            renderOptionGrid("targetGrid", TARGET_OPTIONS, selectedTarget, val => selectedTarget = val);
        }
        if (plan.security && SECURITY_OPTIONS.some(([k]) => k === plan.security)) {
            selectedSecurity = plan.security;
            renderOptionGrid("securityGrid", SECURITY_OPTIONS, selectedSecurity, val => selectedSecurity = val);
        }
        if (decision.chosen_preset) {
            document.getElementById("overrideSelect").value = decision.chosen_preset;
            onOverrideChanged();
        } else {
            recalculate();
        }

        showBanner(`[SUCCESS] Wizard configured from previous run '${dirPath}' (Score: ${decision.overall_confidence || 1.0}, Preset: ${decision.chosen_preset || 'N/A'}).`, "success");
    } catch (e) {
        showBanner(`Error loading run: ${e.message}`, "error");
    }
}

function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showBanner(text, type) {
    const banner = document.getElementById("statusBanner");
    banner.textContent = text;
    banner.className = "status-banner " + type;
}

// Initialize with default or server-provided values
window.addEventListener("DOMContentLoaded", async () => {
    // Check if backend provides prefilled defaults
    try {
        const res = await fetch("/api/config");
        if (res.ok) {
            const cfg = await res.json();
            if (cfg.default_doc) {
                document.getElementById("docPath").value = cfg.default_doc;
            }
            if (cfg.default_lang) {
                document.getElementById("enableLangHint").checked = true;
                const langSelect = document.getElementById("langCode");
                langSelect.value = cfg.default_lang;
                langSelect.disabled = false;
                langSelect.style.opacity = "1";
            }
            if (cfg.previous_runs && cfg.previous_runs.length > 0) {
                populatePreviousRunsDropdown(cfg.previous_runs);
            }
        }
    } catch (e) {
        // Standalone fallback
    }

    // Also attempt loading previous runs if not already loaded from config
    if (availablePreviousRuns.length === 0) {
        try {
            const rRes = await fetch("/api/previous_runs");
            if (rRes.ok) {
                const rData = await rRes.json();
                if (rData.runs && rData.runs.length > 0) {
                    populatePreviousRunsDropdown(rData.runs);
                }
            }
        } catch (e) {}
    }

    renderOptionGrid("taxonomyGrid", TAXONOMY_OPTIONS, selectedTaxonomy, val => selectedTaxonomy = val);
    renderOptionGrid("targetGrid", TARGET_OPTIONS, selectedTarget, val => selectedTarget = val);
    renderOptionGrid("securityGrid", SECURITY_OPTIONS, selectedSecurity, val => selectedSecurity = val);

    recalculate();
});
