/**
 * src/visualization/landing/execution.js
 *
 * Pipeline execution triggering, asynchronous progress polling,
 * execution console logging, and preset rerun actions.
 */

let progressInterval = null;

/**
 * Triggers end-to-end document extraction pipeline execution via POST /api/run.
 *
 * @param {boolean} [withPlan=false] - Whether to include planner questionnaire parameters.
 */
async function triggerRunPipeline(withPlan = false) {
    const pdfPath = document.getElementById('inpPdfPath').value.trim();
    const language = document.getElementById('inpLanguage').value;
    const threshold = parseFloat(document.getElementById('inpThreshold').value);
    const preset = document.getElementById('inpPreset').value;
    const alignSkew = document.getElementById('inpAlignSkew').checked;
    const visualize = document.getElementById('inpVisualize').checked;
    const forceRerun = document.getElementById('inpForceRerun') ? document.getElementById('inpForceRerun').checked : false;

    if (!pdfPath) {
        alert("Please provide an input document path.");
        return;
    }

    // Check if a previous run is already available for this document and preset
    if (!withPlan && !forceRerun && typeof availableRuns !== 'undefined') {
        const targetDocName = pdfPath.split(/[/\\]/).pop().toLowerCase();
        const existingRun = availableRuns.find(r => {
            const docName = (r.document_name || r.document_path || '').split(/[/\\]/).pop().toLowerCase();
            const rPreset = (r.chosen_preset || '').toLowerCase();
            return docName === targetDocName && rPreset === preset.toLowerCase();
        });
        if (existingRun) {
            appendLog(`[INFO] Found previous run for '${targetDocName}' with preset '${preset}' in '${existingRun.dir_path}'. Loading existing result without rerun.`);
            await choosePreviousRun(existingRun.dir_path);
            switchNavTab('results');
            return;
        }
    }

    switchNavTab('progress');
    resetProgressUI();

    appendLog(`[START] Initiating pipeline run for '${pdfPath}' (Preset: ${preset}, Lang: ${language})...`);

    const payload = {
        pdf_path: pdfPath,
        language: language,
        target_threshold: threshold,
        preset: preset,
        align_skew: alignSkew,
        visualize: visualize,
        with_plan: withPlan,
        force_rerun: forceRerun
    };

    if (withPlan) {
        payload.plan_config = {
            taxonomy: document.getElementById('planTaxonomy').value,
            target_use_case: document.getElementById('planTarget').value,
            latency: document.getElementById('planLatency').value,
            hardware: document.getElementById('planHardware').value
        };
    }

    startProgressPolling();

    try {
        const resp = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            appendLog(`[ERROR] Pipeline run failed: ${errData.error || resp.statusText}`);
            updateProgressStatus('ERROR', 'Pipeline execution error.');
            stopProgressPolling();
            return;
        }

        const result = await resp.json();
        onPipelineCompleted(result);
    } catch (e) {
        appendLog(`[ERROR] Network or server communication error: ${e.message}`);
        updateProgressStatus('ERROR', e.message);
        stopProgressPolling();
    }
}

/**
 * Resets the progress bar, step cards, and milestone badges to initial state.
 */
function resetProgressUI() {
    document.getElementById('progressFillBar').style.width = '10%';
    document.getElementById('progressPercentText').textContent = '10%';
    document.getElementById('progressCurrentStepText').textContent = 'Starting ingestion...';
    document.getElementById('progressStatusBadge').textContent = 'PARSING';
    document.getElementById('progressStatusBadge').className = 'badge badge-running';
    document.getElementById('navBadgeProgress').textContent = 'Running';
    document.getElementById('progressCompletionBanner').style.display = 'none';

    for (let i = 1; i <= 5; i++) {
        const card = document.getElementById('stepCard' + i);
        if (card) {
            card.className = 'step-card' + (i === 1 ? ' active' : '');
        }
    }
}

/**
 * Starts periodic background polling of /api/progress endpoint.
 */
function startProgressPolling() {
    stopProgressPolling();
    progressInterval = setInterval(async () => {
        try {
            const resp = await fetch('/api/progress');
            if (resp.ok) {
                const data = await resp.json();
                if (data) {
                    if (data.progress !== undefined) {
                        document.getElementById('progressFillBar').style.width = data.progress + '%';
                        document.getElementById('progressPercentText').textContent = data.progress + '%';
                    }
                    if (data.current_step) {
                        document.getElementById('progressCurrentStepText').textContent = data.current_step;
                    }
                    if (data.logs && Array.isArray(data.logs)) {
                        const consoleEl = document.getElementById('progressLogConsole');
                        consoleEl.textContent = data.logs.join('\n');
                        consoleEl.scrollTop = consoleEl.scrollHeight;
                    }
                    if (data.step_index) {
                        for (let i = 1; i <= 5; i++) {
                            const card = document.getElementById('stepCard' + i);
                            if (card) {
                                if (i < data.step_index) card.className = 'step-card done';
                                else if (i === data.step_index) card.className = 'step-card active';
                                else card.className = 'step-card';
                            }
                        }
                    }
                }
            }
        } catch (e) {
            // Ignore transient network errors during rapid polling
        }
    }, 400);
}

/**
 * Stops active progress polling timer.
 */
function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

/**
 * Handles completed pipeline execution response and transitions UI to results view.
 *
 * @param {Object} result - Execution result payload returned by backend.
 */
function onPipelineCompleted(result) {
    stopProgressPolling();
    document.getElementById('progressFillBar').style.width = '100%';
    document.getElementById('progressPercentText').textContent = '100%';
    document.getElementById('progressCurrentStepText').textContent = 'Ingestion and verification finished.';
    document.getElementById('progressStatusBadge').textContent = 'COMPLETED';
    document.getElementById('progressStatusBadge').className = 'badge badge-success';
    document.getElementById('navBadgeProgress').textContent = 'Done';

    for (let i = 1; i <= 5; i++) {
        const card = document.getElementById('stepCard' + i);
        if (card) card.className = 'step-card done';
    }

    const dec = result.decision || {};
    const viols = result.violations || [];
    const summaryStr = `Status: ${dec.status || 'ACCEPT'} | Confidence: ${Number(dec.overall_confidence || 1.0).toFixed(4)} | Preset: ${dec.chosen_preset || 'docling_fast'} | Violations: ${viols.length}`;
    document.getElementById('progressSummaryText').textContent = summaryStr;
    document.getElementById('progressCompletionBanner').style.display = 'flex';

    appendLog(`[COMPLETE] ${summaryStr}`);

    if (typeof refreshResultsData === 'function') refreshResultsData();
    if (typeof reloadViewerIframe === 'function') reloadViewerIframe();

    setTimeout(() => {
        switchNavTab('results');
    }, 1200);
}

/**
 * Updates progress status badge label and styling.
 *
 * @param {string} status - Status code string ('PARSING', 'COMPLETED', 'ERROR').
 * @param {string} message - Descriptive status message.
 */
function updateProgressStatus(status, message) {
    const badge = document.getElementById('progressStatusBadge');
    if (badge) {
        badge.textContent = status;
        badge.className = status === 'ERROR' ? 'badge badge-error' : 'badge badge-running';
    }
    const stepText = document.getElementById('progressCurrentStepText');
    if (stepText) stepText.textContent = message;
}

/**
 * Appends a timestamped message line to the console output container.
 *
 * @param {string} line - Log message line.
 */
function appendLog(line) {
    const consoleEl = document.getElementById('progressLogConsole');
    if (!consoleEl) return;
    const now = new Date().toISOString().substring(11, 19);
    consoleEl.textContent += `\n[${now}] ${line}`;
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

/**
 * Triggers alternative preset rerun for currently selected document.
 * Checks in-memory and disk caches before executing remote pipeline.
 *
 * @param {string} presetName - Alternative preset identifier.
 */
async function triggerRerunWithPreset(presetName) {
    const pdfPath = document.getElementById('inpPdfPath').value.trim() || 'src/e2e/Document 8.pdf';
    const language = document.getElementById('inpLanguage').value || 'pl';

    // Check if an existing run is already available for this document and preset
    if (typeof availableRuns !== 'undefined') {
        const targetDocName = pdfPath.split(/[/\\]/).pop().toLowerCase();
        const existingRun = availableRuns.find(r => {
            const docName = (r.document_name || r.document_path || '').split(/[/\\]/).pop().toLowerCase();
            const rPreset = (r.chosen_preset || '').toLowerCase();
            return docName === targetDocName && rPreset === presetName.toLowerCase();
        });

        if (existingRun) {
            appendLog(`[INFO] Found previous run for '${targetDocName}' with preset '${presetName}' in '${existingRun.dir_path}'. Loading existing result without rerun.`);
            await choosePreviousRun(existingRun.dir_path);
            switchNavTab('results');
            return;
        }
    }

    appendLog(`[RERUN] Triggering live rerun with preset '${presetName}' for '${pdfPath}'...`);
    switchNavTab('progress');
    resetProgressUI();
    startProgressPolling();

    try {
        const resp = await fetch('/api/rerun', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName, pdf_path: pdfPath, language: language })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            appendLog(`[ERROR] Rerun failed: ${err.error || resp.statusText}`);
            updateProgressStatus('ERROR', 'Rerun failure');
            stopProgressPolling();
            return;
        }
        const result = await resp.json();
        if (result.cached) {
            appendLog(`[CACHE HIT] Loaded previous result for preset '${presetName}' without re-executing pipeline.`);
        }
        onPipelineCompleted(result);
    } catch (e) {
        appendLog(`[ERROR] Network error during rerun: ${e.message}`);
        updateProgressStatus('ERROR', e.message);
        stopProgressPolling();
    }
}
