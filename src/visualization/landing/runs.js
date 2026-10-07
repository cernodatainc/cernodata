/**
 * src/visualization/landing/runs.js
 *
 * Workspace run output discovery, active run selection, run loading,
 * and candidate document population across dashboard tabs.
 */

window.runResultsCache = window.runResultsCache || {};
let activeRunOutputDir = 'output';
let availableRuns = [];

/**
 * Prefetches all run results and cached bounding box artifacts into the browser.
 * Run artifacts are sufficiently lightweight that caching them completely eliminates
 * roundtrip latency and repeated layout parsing on user selection.
 *
 * @param {Array<Object>} runs - List of discovered previous runs.
 */
async function prefetchAllRunResults(runs) {
    if (!runs || !Array.isArray(runs)) return;
    const fetchPromises = runs.map(async (r) => {
        const runKey = r.dir_path || r.run_id;
        if (!runKey || window.runResultsCache[runKey]) return;
        try {
            const resp = await fetch(`/api/viewer_data?output_dir=${encodeURIComponent(runKey)}`);
            if (resp.ok) {
                const viewerData = await resp.json();
                window.runResultsCache[runKey] = viewerData;
                if (r.run_id) window.runResultsCache[r.run_id] = viewerData;
                if (r.dir_path) window.runResultsCache[r.dir_path] = viewerData;
            }
        } catch (err) {
            console.log('[INFO] Prefetch skipped for run:', runKey, err);
        }
    });
    await Promise.allSettled(fetchPromises);
}

/**
 * Queries /api/previous_runs to retrieve list of completed pipeline output runs.
 */
async function loadPreviousRunsList() {
    try {
        const resp = await fetch('/api/previous_runs');
        if (!resp.ok) return;
        const data = await resp.json();
        availableRuns = data.runs || [];
        activeRunOutputDir = data.active_run || 'output';

        updateRunSelectorsUI();
        prefetchAllRunResults(availableRuns);
    } catch (e) {
        console.log('[WARN] Failed to load previous runs:', e);
    }
}

/**
 * Synchronizes dropdown options, chip buttons, and active run badges across tabs.
 */
function updateRunSelectorsUI() {
    const globalSel = document.getElementById('globalRunSelect');
    const planSel = document.getElementById('planPreviousRunSelect');
    const chipsCont = document.getElementById('previousRunsChipsContainer');
    const activeBadge = document.getElementById('activeRunBadge');

    if (activeBadge) {
        activeBadge.textContent = activeRunOutputDir;
    }

    const optionsHtml = '<option value="">-- Choose output of a previous run --</option>' +
        availableRuns.map(r => {
            const selected = (r.dir_path === activeRunOutputDir) ? ' selected' : '';
            return `<option value="${escapeHtml(r.dir_path)}"${selected}>${escapeHtml(r.label || r.dir_path)}</option>`;
        }).join('');

    if (globalSel) globalSel.innerHTML = optionsHtml;
    if (planSel) {
        planSel.innerHTML = '<option value="">-- Load Plan from Previous Run --</option>' +
            availableRuns.map(r => `<option value="${escapeHtml(r.dir_path)}">${escapeHtml(r.label || r.dir_path)}</option>`).join('');
    }

    if (chipsCont) {
        if (availableRuns.length === 0) {
            chipsCont.innerHTML = '<span class="file-chips-label">No previous runs found.</span>';
        } else {
            chipsCont.innerHTML = availableRuns.map(r => {
                const activeClass = (r.dir_path === activeRunOutputDir) ? ' chip-btn-active' : '';
                return `<button class="chip-btn${activeClass}" onclick="choosePreviousRun('${escapeHtml(r.dir_path)}')">${escapeHtml(r.document_name)} (${escapeHtml(r.dir_path)})</button>`;
            }).join('');
        }
    }
}

/**
 * Loads the output directory currently selected in the top navigation dropdown.
 */
function loadSelectedRun() {
    const sel = document.getElementById('globalRunSelect');
    if (sel && sel.value) {
        choosePreviousRun(sel.value);
    }
}

/**
 * Loads artifacts from an output directory into the server session and synchronizes all tabs.
 *
 * @param {string} outputDir - Target output directory path to load.
 * @param {number} [targetPage=1] - Target page to bring up in the viewer.
 * @param {boolean} [shouldReloadViewer=true] - Whether to reload the viewer iframe immediately.
 */
async function choosePreviousRun(outputDir, targetPage = 1, shouldReloadViewer = true) {
    if (!outputDir) return;
    try {
        const resp = await fetch('/api/load_run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ output_dir: outputDir })
        });
        if (!resp.ok) {
            alert('Failed to load previous run from: ' + outputDir);
            return;
        }
        const data = await resp.json();
        activeRunOutputDir = data.output_dir || outputDir;
        updateRunSelectorsUI();

        const run = data.run || {};
        const plan = (run && run.plan) ? run.plan : (data.plan || {});
        const decision = (run && run.decision) ? run.decision : (data.decision || {});

        // 1. Update Input Selection Tab
        if (run.document_path) {
            const inpDoc = document.getElementById('inpPdfPath');
            if (inpDoc) inpDoc.value = run.document_path;
        }
        if (decision.language) {
            const langSel = document.getElementById('inpLanguage');
            if (langSel) langSel.value = decision.language;
        }
        if (decision.chosen_preset) {
            const presetSel = document.getElementById('inpPreset');
            if (presetSel) {
                for (let opt of presetSel.options) {
                    if (opt.value === decision.chosen_preset) {
                        presetSel.value = decision.chosen_preset;
                        break;
                    }
                }
            }
        }
        if (decision.target_confidence_threshold) {
            const inpThresh = document.getElementById('inpThreshold');
            if (inpThresh) {
                inpThresh.value = decision.target_confidence_threshold;
                const threshDisp = document.getElementById('thresholdDisplay');
                if (threshDisp) threshDisp.textContent = Number(decision.target_confidence_threshold).toFixed(2);
            }
        }

        // 2. Update Planning Tab
        if (plan && plan.taxonomy && document.getElementById('planTaxonomy')) {
            document.getElementById('planTaxonomy').value = plan.taxonomy;
        }
        if (plan && plan.target && document.getElementById('planTarget')) {
            document.getElementById('planTarget').value = plan.target;
        }
        if (plan && plan.hardware && document.getElementById('planHardware')) {
            document.getElementById('planHardware').value = plan.hardware;
        }
        if (typeof updateSuggestedPlan === 'function') updateSuggestedPlan();

        const planNotice = document.getElementById('planLoadedNotice');
        if (planNotice) {
            planNotice.style.display = 'block';
            planNotice.textContent = `[INFO] Configuration synchronized from previous run: '${outputDir}' (${(plan && plan.taxonomy) || 'N/A'}, primary: ${(plan && plan.primary_preset) || decision.chosen_preset || 'N/A'}).`;
        }

        // 3. Update Progress Tab
        const consoleEl = document.getElementById('progressLogConsole');
        if (consoleEl) {
            const conf = decision.overall_confidence !== undefined ? Number(decision.overall_confidence).toFixed(4) : '1.0000';
            consoleEl.textContent = `--- [LOADED PREVIOUS RUN OUTPUT] ---\nDirectory: ${outputDir}\nDocument: ${run.document_path || 'N/A'}\nChosen Preset: ${decision.chosen_preset || 'N/A'}\nStatus: ${decision.status || 'ACCEPT'}\nConfidence: ${conf}\nQuality Violations: ${run.violations_count || 0}`;
        }
        document.getElementById('progressFillBar').style.width = '100%';
        document.getElementById('progressPercentText').textContent = '100%';
        document.getElementById('progressCurrentStepText').textContent = `Loaded previous run: ${outputDir}`;
        document.getElementById('progressStatusBadge').textContent = 'LOADED';
        document.getElementById('progressStatusBadge').className = 'badge badge-success';
        document.getElementById('navBadgeProgress').textContent = 'Loaded';

        // 4. Update Preset Results Tab
        if (typeof renderResultsTable === 'function') {
            renderResultsTable(data.results || { attempts: run.attempts, decision: decision, violations: data.violations });
        }
        if (typeof loadRunsGrid === 'function') {
            loadRunsGrid(run.document_name);
        }
        if (shouldReloadViewer && typeof reloadViewerIframe === 'function') {
            reloadViewerIframe(targetPage, outputDir);
        }
    } catch (e) {
        console.log('[ERROR] Failed to switch previous run:', e);
    }
}

/**
 * Queries /api/documents to discover candidate PDF files in the repository.
 */
async function loadAvailableDocuments() {
    try {
        const resp = await fetch('/api/documents');
        if (!resp.ok) return;
        const data = await resp.json();
        const docs = data.documents || [];
        const select = document.getElementById('docSelectDropdown');
        const container = document.getElementById('docChipsContainer');
        if (select && docs.length > 0) {
            select.innerHTML = '<option value="">-- Choose Discovered Document --</option>' +
                docs.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
        }
        if (container && docs.length > 0) {
            container.innerHTML = '<span class="file-chips-label">Discovered files:</span>' +
                docs.map(d => `<button class="chip-btn" onclick="selectDocPath('${escapeHtml(d)}')">${escapeHtml(d)}</button>`).join('');
        }
    } catch (e) {
        console.log('[WARN] Failed to load documents list:', e);
    }
}
