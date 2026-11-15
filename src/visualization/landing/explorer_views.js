/**
 * src/visualization/landing/explorer_views.js
 *
 * Primary explorer main pane views and interactive run execution controllers:
 * - Directory view: files in the active folder with runs summary and quick actions
 * - File runs view: historical parsing runs for active document and unrun preset executor
 * - Run pages view: page-by-page quality score and violations inspection cards
 */

/** Renders the primary view in the right pane based on currentExplorerScope. */
function renderExplorerMainView() {
    const tableContainer = document.getElementById('explorerTableContainer');
    const breakdownContainer = document.getElementById('explorerPageBreakdown');
    const titleEl = document.getElementById('explorerTableTitle');
    const tableHead = document.getElementById('explorerTableHead');
    const tbody = document.getElementById('explorerTableBody');
    if (!tableContainer || !breakdownContainer || !window.explorerData) return;

    if (currentExplorerScope === 'directory') {
        tableContainer.style.display = 'block';
        breakdownContainer.style.display = 'none';
        renderDirectoryFilesView(titleEl, tableHead, tbody);
    } else if (currentExplorerScope === 'run') {
        tableContainer.style.display = 'none';
        breakdownContainer.style.display = 'block';
        renderRunPagesView(titleEl, breakdownContainer);
    } else {
        tableContainer.style.display = 'block';
        breakdownContainer.style.display = 'none';
        renderFileRunsView(titleEl, tableHead, tbody);
    }
}

/** Renders directory view showing files in the selected folder. */
function renderDirectoryFilesView(titleEl, tableHead, tbody) {
    const fileSets = window.explorerData.file_sets || [];
    const activeSet = fileSets.find(fs => fs.file_set === currentExplorerFolder) || fileSets[0];
    const folderName = activeSet ? activeSet.file_set : (currentExplorerFolder || 'workspace');
    const query = explorerSearchQuery.toLowerCase().trim();

    if (titleEl) titleEl.textContent = `Directory: ${folderName}`;
    if (tableHead) tableHead.innerHTML = '<tr><th>Document</th><th>File Path</th><th>Runs</th><th>Latest Preset</th><th>Latest Score</th><th>Status</th><th>Action</th></tr>';
    if (!tbody) return;

    const docs = activeSet ? activeSet.documents : [];
    const filteredDocs = docs.filter(d => !query || d.file_name.toLowerCase().includes(query) || d.file_path.toLowerCase().includes(query));

    if (filteredDocs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-message">No documents found in this directory.</td></tr>';
        return;
    }

    let rowsHtml = '';
    filteredDocs.forEach(doc => {
        const runCount = doc.runs_count || 0;
        const latest = doc.latest_run;
        const presetBadge = latest ? `<span class="preset-badge">${escapeHtml(latest.preset)}</span>` : '<span class="table-muted-cell">-</span>';
        const scoreBadge = latest ? `<span class="score-num">${Number(latest.overall_confidence).toFixed(4)}</span>` : '<span class="table-muted-cell">-</span>';
        const statusBadge = latest
            ? `<span class="badge ${latest.status === 'ACCEPT' ? 'badge-accept' : 'badge-warn'}">${escapeHtml(latest.status)}</span>`
            : '<span class="table-muted-cell">Unparsed</span>';

        rowsHtml += `<tr data-doc-path="${escapeHtml(doc.file_path)}" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')"`
            + ` oncontextmenu="handleExplorerFileContextMenu(event, '${escapeHtml(doc.file_path)}')">`
            + `<td><span class="file-name-cell" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_name)}</span></td>`
            + `<td><span class="file-path-sub">${escapeHtml(doc.file_path)}</span></td>`
            + `<td><span class="tree-runs-count-badge">${runCount} runs</span></td>`
            + `<td>${presetBadge}</td><td>${scoreBadge}</td><td>${statusBadge}</td>`
            + `<td class="action-cell">`
            + `<button class="btn btn-secondary btn-xs" onclick="event.stopPropagation(); selectExplorerDoc('${escapeHtml(doc.file_path)}')">Explore runs</button> `
            + `<button class="btn btn-subtle btn-xs" onclick="event.stopPropagation(); forgetExplorerFile('${escapeHtml(doc.file_path)}')" title="Forget file">Forget</button>`
            + `</td></tr>`;
    });
    tbody.innerHTML = rowsHtml;
}

/** Renders file view showing historical parsing runs and unrun preset execution line. */
function renderFileRunsView(titleEl, tableHead, tbody) {
    const allMappings = window.explorerData.all_mappings || [];
    const doc = allMappings.find(m => m.file_path === currentExplorerDoc) || allMappings[0];
    const docName = doc ? doc.file_name : (currentExplorerDoc || 'None');
    const docPath = doc ? doc.file_path : currentExplorerDoc;
    const query = explorerSearchQuery.toLowerCase().trim();

    if (titleEl) {
        titleEl.textContent = `File runs: ${docName}`;
        titleEl.setAttribute('data-doc-path', docPath || '');
        titleEl.oncontextmenu = (e) => handleExplorerFileContextMenu(e, docPath);
    }
    if (tableHead) tableHead.innerHTML = '<tr><th>Run ID</th><th>Preset</th><th>Score</th><th>Viols</th><th>Status</th><th>Time</th><th>Action</th></tr>';
    if (!tbody) return;

    const runs = (doc && doc.runs) ? doc.runs : [];
    const filteredRuns = runs.filter(r => !query || r.run_id.toLowerCase().includes(query) || r.preset.toLowerCase().includes(query) || r.status.toLowerCase().includes(query));
    const hasActiveRun = Boolean(typeof doesActiveRunMatchDoc === 'function' && doesActiveRunMatchDoc(doc));

    let rowsHtml = '';
    if (hasActiveRun) {
        const active = window.activeParsingRun;
        const pct = Number.isFinite(Number(active.progress)) ? Number(active.progress) : 0;
        const isError = active.status === 'error';
        const isDone = active.status === 'completed';
        const badgeCls = isError ? 'badge-error' : (isDone ? 'badge-success' : 'badge-running');
        const statusLabel = isError ? 'ERROR' : (isDone ? 'COMPLETED' : 'PARSING');
        const isSelectedRun = (currentExplorerScope === 'run' && active.run_id === currentExplorerRun);
        const rowClass = 'explorer-row-active-run' + (isSelectedRun ? ' explorer-row-selected' : '');

        rowsHtml += `<tr class="${rowClass}" data-run-id="${escapeHtml(active.run_id)}" data-doc-path="${escapeHtml(docPath)}"`
            + ` onclick="selectExplorerRun('${escapeHtml(active.run_id)}', '', '${escapeHtml(docPath)}')">`
            + `<td><span class="run-id-cell">In progress</span></td>`
            + `<td><span class="preset-badge">${escapeHtml(active.preset)}</span></td>`
            + `<td><div class="explorer-inline-progress"><div class="explorer-inline-progress-track">`
            + `<div class="explorer-inline-progress-fill" id="explorerTableActiveRunFill" style="width: ${pct}%;"></div>`
            + `</div><span class="score-num" id="explorerTableActiveRunPct">${pct}%</span></div></td>`
            + `<td><span class="table-muted-cell">-</span></td>`
            + `<td><span class="badge ${badgeCls}" id="explorerTableActiveRunStatus">${statusLabel}</span></td>`
            + `<td><span class="run-time-sub" id="explorerTableActiveRunStep">${escapeHtml(active.current_step || '')}</span></td>`
            + `<td class="action-cell"><button class="btn btn-secondary btn-xs" onclick="event.stopPropagation(); selectExplorerRun('${escapeHtml(active.run_id)}', '', '${escapeHtml(docPath)}')">View progress</button></td></tr>`;
    }

    if (filteredRuns.length === 0 && !hasActiveRun) {
        rowsHtml += '<tr><td colspan="7" class="table-empty-message">No parsing runs recorded for this file yet. Select a preset below to run it.</td></tr>';
    } else {
        filteredRuns.forEach(run => {
            const isSelectedRun = (currentExplorerScope === 'run' && run.run_id === currentExplorerRun);
            const rowClass = isSelectedRun ? 'explorer-row-selected' : '';
            const statusBadgeClass = (run.status === 'ACCEPT') ? 'badge-accept' : 'badge-warn';
            const scoreFormatted = Number(run.overall_confidence).toFixed(4);

            rowsHtml += `<tr class="${rowClass}" data-run-id="${escapeHtml(run.run_id)}" data-doc-path="${escapeHtml(docPath)}"`
                + ` onclick="selectExplorerRun('${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(docPath)}')" `
                + ` oncontextmenu="handleExplorerRunContextMenu(event, '${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(docPath)}')">`
                + `<td><span class="run-id-cell">${escapeHtml(run.run_id)}</span></td><td><span class="preset-badge">${escapeHtml(run.preset)}</span></td>`
                + `<td><span class="score-num">${scoreFormatted}</span></td><td><span class="viol-count">${run.violations_count || 0}</span></td>`
                + `<td><span class="badge ${statusBadgeClass}">${escapeHtml(run.status)}</span></td><td><span class="run-time-sub">${escapeHtml(run.timestamp || '-')}</span></td>`
                + `<td class="action-cell"><button class="btn btn-secondary btn-xs" onclick="event.stopPropagation(); selectExplorerRun('${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(docPath)}')">Inspect pages</button> `
                + `<button class="btn btn-subtle btn-xs btn-remove-run" onclick="event.stopPropagation(); removeExplorerRun('${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(docPath)}')" title="Remove run">Remove</button></td></tr>`;
        });
    }

    const allPresets = getAvailablePresetOptions();
    const executedPresets = new Set(runs.map(r => r.preset));
    const unrunPresets = allPresets.filter(p => !executedPresets.has(p.id));

    if (unrunPresets.length > 0) {
        const optionsHtml = unrunPresets.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`).join('');
        rowsHtml += `<tr class="explorer-add-preset-row"><td colspan="7"><div class="explorer-add-preset-line">`
            + `<button class="explorer-plus-btn" title="Run unexecuted preset" onclick="startSelectedPresetFromExplorer('${escapeHtml(docPath)}')">+</button>`
            + `<span class="explorer-add-preset-label">Execute unrun preset:</span>`
            + `<select class="form-select explorer-preset-select" id="explorerPresetSelect">${optionsHtml}</select>`
            + `<button class="btn btn-primary btn-xs" onclick="startSelectedPresetFromExplorer('${escapeHtml(docPath)}')">Run preset</button>`
            + `</div></td></tr>`;
    } else {
        rowsHtml += `<tr class="explorer-add-preset-row"><td colspan="7"><div class="explorer-add-preset-line">`
            + `<span class="explorer-add-preset-muted">All available presets have been executed for this document.</span>`
            + `</div></td></tr>`;
    }

    tbody.innerHTML = rowsHtml;
}

/** Returns available preset options from DOM or default fallback catalog. */
function getAvailablePresetOptions() {
    const sel = document.getElementById('inpPreset');
    if (sel && sel.options && sel.options.length > 0) {
        return Array.from(sel.options).map(opt => ({ id: opt.value, label: opt.textContent.trim() }));
    }
    return [
        { id: 'docling_fast', label: 'docling_fast (Hybrid Parser)' },
        { id: 'docling_deep', label: 'docling_deep (Deep Visual OCR & Tables)' },
        { id: 'pypdfium_rapidocr', label: 'pypdfium_rapidocr (RapidOCR Standalone)' },
    ];
}

/** Starts execution of selected unrun preset for document from explorer file view. */
async function startSelectedPresetFromExplorer(docPath) {
    if (!docPath) return;
    const sel = document.getElementById('explorerPresetSelect');
    const chosenPreset = sel ? sel.value : 'docling_fast';

    const inp = document.getElementById('inpPdfPath');
    if (inp) inp.value = docPath;
    const docPathEl = document.getElementById('docPath');
    if (docPathEl) docPathEl.value = docPath;
    const presetEl = document.getElementById('inpPreset');
    if (presetEl) { presetEl.value = chosenPreset; if (typeof onInpPresetChanged === 'function') onInpPresetChanged(); }
    if (typeof triggerRunPipeline === 'function') await triggerRunPipeline(false);
}

/** Renders run view showing page-by-page quality breakdown. */
function renderRunPagesView(titleEl, container) {
    if (!container) return;
    const selected = getSelectedRunObject();
    if (!selected || !selected.run) {
        if (titleEl) titleEl.textContent = 'Run pages';
        container.innerHTML = '<div class="page-breakdown-empty"><span class="page-breakdown-empty-text">No active run selected. Select a run from the tree to inspect pages.</span></div>';
        return;
    }

    const { doc, run } = selected;
    if (run.is_active_progress) {
        renderEmbeddedParsingProgressView(titleEl, container, doc, run);
        return;
    }

    const totalP = run.total_pages || 1;
    const statusClass = (run.status === 'ACCEPT') ? 'badge-accept' : 'badge-warn';
    const scoreFormatted = Number(run.overall_confidence).toFixed(4);

    if (titleEl) titleEl.textContent = `Run pages: ${run.run_id} (${doc.file_name})`;

    let cardsHtml = '';
    for (let p = 1; p <= totalP; p++) {
        const pStr = String(p);
        const pConf = (run.per_page_confidence && run.per_page_confidence[pStr] !== undefined)
            ? Number(run.per_page_confidence[pStr]) : run.overall_confidence;
        const pViols = (run.per_page_violations && run.per_page_violations[pStr] !== undefined)
            ? run.per_page_violations[pStr] : 0;
        const scoreCls = (pConf >= 0.85) ? 'status-pass' : 'status-warn';
        const violCls = (pViols > 0) ? 'has-viols' : '';

        cardsHtml += `<div class="page-breakdown-card" onclick="chooseRunAndPage('${escapeHtml(run.run_id)}', ${p})" title="Open page ${p} in viewer">`
            + `<div class="page-card-header"><span class="page-card-title">Page ${p}</span><span class="page-card-score ${scoreCls}">${Number(pConf).toFixed(4)}</span></div>`
            + `<div class="page-card-body"><span class="page-card-viols ${violCls}">${pViols} viols</span><button class="btn btn-xs btn-secondary page-card-btn">View page</button></div></div>`;
    }

    container.innerHTML = `<div class="page-breakdown-header"><div class="page-breakdown-title">`
        + `<button class="btn btn-secondary btn-xs" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">Back to file runs</button>`
        + `<span class="breakdown-run-id">${escapeHtml(run.run_id)}</span>`
        + `<span class="breakdown-doc-sub">(${escapeHtml(doc.file_name)} · ${escapeHtml(run.preset)})</span></div>`
        + `<div class="page-breakdown-meta"><span class="score-num breakdown-score-text">Score: ${scoreFormatted}</span>`
        + `<span class="badge ${statusClass}">${escapeHtml(run.status)}</span>`
        + `<span class="breakdown-viols-sub">${run.violations_count || 0} total viols</span></div></div>`
        + `<div class="page-cards-grid">${cardsHtml}</div>`;
}

/** Renders live parsing progress embedded inside the explorer run view. */
function renderEmbeddedParsingProgressView(titleEl, container, doc, run) {
    const pct = Number.isFinite(Number(run.progress)) ? Number(run.progress) : 0;
    const isError = run.status === 'error';
    const isDone = run.status === 'completed';
    const badgeCls = isError ? 'badge-error' : (isDone ? 'badge-success' : 'badge-running');
    const statusLabel = isError ? 'ERROR' : (isDone ? 'COMPLETED' : 'PARSING');
    const spinnerCls = (isError || isDone) ? 'progress-spinner hidden' : 'progress-spinner';
    const stepIdx = run.step_index || 1;
    const stepTitles = [
        'Document validation & slicing',
        'Layout & OCR parsing',
        'Text skew alignment',
        'Quality checks',
        'Decision tree & fallback',
    ];

    if (titleEl) titleEl.textContent = `Parsing progress: ${doc.file_name} (${run.preset})`;

    const stepsHtml = stepTitles.map((label, idx) => {
        const num = idx + 1;
        let cls = 'step-card';
        if (isDone || num < stepIdx) cls = 'step-card done';
        else if (num === stepIdx) cls = 'step-card active';
        return `<div class="${cls}" id="explorerStepCard${num}">`
            + `<div class="step-card-num">Step ${num}</div>`
            + `<div class="step-card-title">${escapeHtml(label)}</div>`
            + `</div>`;
    }).join('');

    const logsText = (Array.isArray(run.logs) && run.logs.length > 0)
        ? run.logs.join('\n')
        : '--- Starting pipeline execution ---';

    container.innerHTML = `<div class="page-breakdown-header">`
        + `<div class="page-breakdown-title">`
        + `<button class="btn btn-secondary btn-xs" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">Back to file runs</button>`
        + `<span class="breakdown-run-id">Parsing: ${escapeHtml(doc.file_name)}</span>`
        + `<span class="breakdown-doc-sub">(${escapeHtml(run.preset)})</span>`
        + `</div>`
        + `<div class="page-breakdown-meta">`
        + `<span id="explorerProgressSpinner" class="${spinnerCls}"></span>`
        + `<span class="badge ${badgeCls}" id="explorerProgressStatusBadge">${statusLabel}</span>`
        + `<span id="explorerProgressPercentText" class="progress-pct-text">${pct}%</span>`
        + `</div>`
        + `</div>`
        + `<div class="explorer-progress-panel">`
        + `<div class="progress-header-row">`
        + `<div class="progress-step-container">`
        + `<span id="explorerProgressCurrentStepText" class="progress-step-text">${escapeHtml(run.current_step || 'Starting ingestion...')}</span>`
        + `</div>`
        + `</div>`
        + `<div class="progress-track"><div class="progress-fill" id="explorerProgressFillBar" style="width: ${pct}%;"></div></div>`
        + `<div class="pipeline-steps explorer-progress-steps">${stepsHtml}</div>`
        + `<div class="terminal-box explorer-progress-terminal" id="explorerProgressLogConsole">${escapeHtml(logsText)}</div>`
        + `<div id="explorerProgressCompletionBanner" class="progress-completion-banner" style="display: ${isDone ? 'flex' : 'none'};">`
        + `<div><div class="progress-completion-title">Pipeline run completed</div>`
        + `<div class="progress-completion-summary" id="explorerProgressSummaryText">${escapeHtml(run.summary || '')}</div></div>`
        + `<div class="progress-completion-actions"><button class="btn btn-primary btn-xs" onclick="switchNavTab('results')">View results</button></div>`
        + `</div>`
        + `</div>`;
}

/** Loads the chosen run into active session and navigates to the page in the viewer. */
async function chooseRunAndPage(runId, pageNo) {
    const targetPage = parseInt(pageNo, 10) || 1;
    if (typeof choosePreviousRun === 'function') await choosePreviousRun(runId, targetPage, false);
    if (typeof switchNavTab === 'function') switchNavTab('results');
    if (typeof reloadViewerIframe === 'function') reloadViewerIframe(targetPage, runId);
}

/** Removes a specific parsing run from repository and refreshes explorer data. */
async function removeExplorerRun(runId, outputDir, docPath) {
    try {
        await fetch('/api/remove_run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: runId, output_dir: outputDir, document_path: docPath }),
        });
        if (currentExplorerRun === runId || currentExplorerRun === outputDir) {
            currentExplorerRun = '';
            currentExplorerScope = 'file';
        }
        await loadFileRunMappings();
    } catch (e) {
        console.log('[WARN] Failed to remove run:', e);
    }
}
