let currentTab = 'input';
let progressInterval = null;

function switchNavTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll('.hub-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));

    const btn = document.getElementById('tabBtn' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    const sec = document.getElementById('sec' + tabName.charAt(0).toUpperCase() + tabName.slice(1));

    if (btn) btn.classList.add('active');
    if (sec) sec.classList.add('active');

    if (tabName === 'results') {
        refreshResultsData();
        reloadViewerIframe();
    }
}

function selectDocPath(path) {
    document.getElementById('inpPdfPath').value = path;
}

function updateSuggestedPlan() {
    const tax = document.getElementById('planTaxonomy').value;
    const target = document.getElementById('planTarget').value;
    const lat = document.getElementById('planLatency').value;

    let primary = 'docling_fast';
    let fallback = 'docling_deep';

    if (tax === 'scanned_archive' || tax === 'form_heavy' || lat === 'maximum_accuracy') {
        primary = 'docling_deep';
        fallback = 'pypdfium_rapidocr';
    } else if (lat === 'fast_low_cost') {
        primary = 'docling_fast';
        fallback = 'pypdfium_rapidocr';
    }

    document.getElementById('planPrimaryBadge').textContent = primary;
    document.getElementById('planFallbackBadge').textContent = fallback;
}

async function triggerRunPipeline(withPlan = false) {
    const pdfPath = document.getElementById('inpPdfPath').value.trim();
    const language = document.getElementById('inpLanguage').value;
    const threshold = parseFloat(document.getElementById('inpThreshold').value);
    const preset = document.getElementById('inpPreset').value;
    const alignSkew = document.getElementById('inpAlignSkew').checked;
    const visualize = document.getElementById('inpVisualize').checked;

    if (!pdfPath) {
        alert("Please provide an input document path.");
        return;
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
        with_plan: withPlan
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
            // ignore polling errors
        }
    }, 400);
}

function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

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

    // Pre-load results
    refreshResultsData();
    reloadViewerIframe();

    // Auto-switch to results so user immediately inspects and works with the parsed output
    setTimeout(() => {
        switchNavTab('results');
    }, 1200);
}

function updateProgressStatus(status, message) {
    document.getElementById('progressStatusBadge').textContent = status;
    document.getElementById('progressStatusBadge').className = status === 'ERROR' ? 'badge badge-error' : 'badge badge-running';
    document.getElementById('progressCurrentStepText').textContent = message;
}

function appendLog(line) {
    const consoleEl = document.getElementById('progressLogConsole');
    const now = new Date().toISOString().substring(11, 19);
    consoleEl.textContent += `\n[${now}] ${line}`;
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

async function triggerRerunWithPreset(presetName) {
    const pdfPath = document.getElementById('inpPdfPath').value.trim() || 'src/e2e/Document 8.pdf';
    const language = document.getElementById('inpLanguage').value || 'pl';
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
        onPipelineCompleted(result);
    } catch (e) {
        appendLog(`[ERROR] Network error during rerun: ${e.message}`);
        updateProgressStatus('ERROR', e.message);
        stopProgressPolling();
    }
}

let activeRunOutputDir = 'output';
let availableRuns = [];

async function loadPreviousRunsList() {
    try {
        const resp = await fetch('/api/previous_runs');
        if (!resp.ok) return;
        const data = await resp.json();
        availableRuns = data.runs || [];
        activeRunOutputDir = data.active_run || 'output';

        updateRunSelectorsUI();
    } catch (e) {
        console.log('[WARN] Failed to load previous runs:', e);
    }
}

function updateRunSelectorsUI() {
    const globalSel = document.getElementById('globalRunSelect');
    const planSel = document.getElementById('planPreviousRunSelect');
    const resultsSel = document.getElementById('resultsRunSelect');
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
    if (resultsSel) resultsSel.innerHTML = optionsHtml;

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

function loadSelectedRun() {
    const sel = document.getElementById('globalRunSelect');
    if (sel && sel.value) {
        choosePreviousRun(sel.value);
    }
}

async function choosePreviousRun(outputDir) {
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
                document.getElementById('thresholdDisplay').textContent = Number(decision.target_confidence_threshold).toFixed(2);
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
        updateSuggestedPlan();

        const planNotice = document.getElementById('planLoadedNotice');
        if (planNotice) {
            planNotice.style.display = 'block';
            planNotice.textContent = `[INFO] Configuration synchronized from previous run: '${outputDir}' (${(plan && plan.taxonomy) || 'N/A'}, primary: ${(plan && plan.primary_preset) || decision.chosen_preset || 'N/A'}).`;
        }

        // 3. Update Progress tab
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
        renderResultsTable(data.results || { attempts: run.attempts, decision: decision, violations: data.violations });
        reloadViewerIframe();
    } catch (e) {
        console.log('[ERROR] Failed to switch previous run:', e);
    }
}

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

async function refreshResultsData() {
    try {
        const resp = await fetch('/api/results');
        if (!resp.ok) return;
        const data = await resp.json();
        renderResultsTable(data);
    } catch (e) {
        console.log('[INFO] Failed to fetch results:', e);
    }
}

function renderResultsTable(data) {
    const tbody = document.getElementById('resultsTableBody');
    if (!tbody) return;

    const attempts = (data && data.attempts && data.attempts.length > 0)
        ? data.attempts
        : (data && data.decision ? [{
            step: 1,
            preset: data.decision.chosen_preset || 'docling_fast',
            overall_confidence: data.decision.overall_confidence,
            per_page_confidence: data.decision.per_page_confidence,
            violations_count: (data.violations || []).length,
            status: data.decision.status || 'ACCEPT',
            action: (data.decision.decision_tree ? data.decision.decision_tree.action : 'ACCEPT_PARSE')
        }] : []);

    if (attempts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-message">No pipeline run executed yet.</td></tr>';
        return;
    }

    tbody.innerHTML = attempts.map(att => {
        const conf = (att.overall_confidence !== undefined && att.overall_confidence !== null)
            ? Number(att.overall_confidence).toFixed(4)
            : '1.0000';
        const perPageStr = att.per_page_confidence
            ? Object.entries(att.per_page_confidence).map(([p, s]) => `P${p}: ${Number(s).toFixed(2)}`).join(', ')
            : '-';
        const isAccept = (att.status === 'ACCEPT' || att.is_accepted);
        const badgeClass = isAccept ? 'badge-success' : (att.status === 'FALLBACK' ? 'badge-running' : 'badge-error');
        const scoreClass = isAccept ? 'cell-score-pass' : 'cell-score-fail';

        return `
            <tr>
                <td><strong>Step ${att.step || 1}</strong></td>
                <td><span class="preset-badge">${escapeHtml(att.preset || 'docling_fast')}</span></td>
                <td class="${scoreClass}">${conf}</td>
                <td class="cell-per-page">${escapeHtml(perPageStr)}</td>
                <td>${att.violations_count || 0}</td>
                <td><span class="badge ${badgeClass}">${escapeHtml(att.status || 'ACCEPT')}</span></td>
                <td class="cell-action">${escapeHtml(att.action || 'EXECUTE')}</td>
            </tr>
        `;
    }).join('');
}

function reloadViewerIframe() {
    const frame = document.getElementById('viewerFrame');
    if (frame) {
        frame.src = '/viewer?' + Date.now();
    }
}

function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Initial setup
window.addEventListener("DOMContentLoaded", () => {
    updateSuggestedPlan();
    loadAvailableDocuments();
    loadPreviousRunsList();
    refreshResultsData();
});
