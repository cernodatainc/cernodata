/**
 * src/visualization/data_shape/runs.js
 *
 * Previous run selection, artifact summary display, and wizard field
 * hydration from existing pipeline runs.
 */

let availablePreviousRuns = [];

/**
 * Populates the previous runs selection dropdown with discovered workspace runs.
 *
 * @param {Array<Object>} runs - List of discovered previous run objects.
 */
function populatePreviousRunsDropdown(runs) {
    availablePreviousRuns = runs || [];
    const select = document.getElementById("prevRunSelect");
    if (!select) return;
    select.innerHTML = '<option value="">-- Choose output of a previous run --</option>' +
        availablePreviousRuns.map(r => `<option value="${escapeHtml(r.dir_path)}">${escapeHtml(r.label || r.dir_path)}</option>`).join('');
}

/**
 * Updates summary box and visual flow viewer link when a run is chosen from dropdown.
 *
 * @param {string} dirPath - Selected run directory path.
 */
function onPreviousRunSelected(dirPath) {
    const run = availablePreviousRuns.find(r => r.dir_path === dirPath);
    const summaryEl = document.getElementById("prevRunSummary");
    const btnViewer = document.getElementById("btnInspectViewer");

    if (btnViewer) {
        btnViewer.href = dirPath ? `/viewer.html?output_dir=${encodeURIComponent(dirPath)}` : '/viewer.html';
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

/**
 * Loads configuration and document parameters from the selected previous run into the wizard.
 */
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
            const docEl = document.getElementById("docPath");
            if (docEl) docEl.value = run.document_path;
            const inpPdf = document.getElementById("inpPdfPath");
            if (inpPdf) inpPdf.value = run.document_path;
        }
        if (decision.language) {
            const langCheck = document.getElementById("enableLangHint");
            if (langCheck) langCheck.checked = true;
            toggleLanguageHint();
            const langCode = document.getElementById("langCode");
            if (langCode) langCode.value = decision.language;
            const inpLang = document.getElementById("inpLanguage");
            if (inpLang) inpLang.value = decision.language;
        }
        if (decision.target_confidence_threshold) {
            updateThreshold(decision.target_confidence_threshold);
            const slider = document.getElementById("thresholdSlider");
            if (slider) slider.value = decision.target_confidence_threshold;
            const inpThresh = document.getElementById("inpThreshold");
            if (inpThresh) inpThresh.value = decision.target_confidence_threshold;
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
            const overrideSel = document.getElementById("overrideSelect");
            if (overrideSel) overrideSel.value = decision.chosen_preset;
            onOverrideChanged();
            const inpPreset = document.getElementById("inpPreset");
            if (inpPreset) inpPreset.value = decision.chosen_preset;
        } else {
            recalculate();
        }

        showBanner(`[SUCCESS] Wizard configured from previous run '${dirPath}' (Score: ${decision.overall_confidence || 1.0}, Preset: ${decision.chosen_preset || 'N/A'}).`, "success");
    } catch (e) {
        showBanner(`Error loading run: ${e.message}`, "error");
    }
}
