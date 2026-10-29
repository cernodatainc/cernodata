/**
 * src/visualization/landing/explorer.js
 * Scoped workspace file explorer and run mapping repository interface.
 * Allows exclusive exploration of directories (showing files), files (showing runs),
 * or individual runs (showing page-by-page breakdown).
 */

window.explorerData = null;
let currentExplorerScope = 'file';
let currentExplorerFolder = '';
let currentExplorerDoc = '';
let currentExplorerRun = '';
let explorerSearchQuery = '';
const expandedFolders = new Set();
const expandedRuns = new Set();

/** Retrieves file and run mappings from /api/file_run_mappings and renders explorer. */
async function loadFileRunMappings() {
    try {
        const resp = await fetch('/api/file_run_mappings');
        if (!resp.ok) return;
        const data = await resp.json();
        window.explorerData = data;
        const allMappings = data.all_mappings || [];
        const fileSets = data.file_sets || [];

        if (currentExplorerDoc && !allMappings.some(m => m.file_path === currentExplorerDoc)) {
            currentExplorerDoc = data.active_file || (allMappings[0] ? allMappings[0].file_path : '');
        } else if (!currentExplorerDoc) {
            currentExplorerDoc = data.active_file || (allMappings[0] ? allMappings[0].file_path : '');
        }

        const activeDocEntry = allMappings.find(m => m.file_path === currentExplorerDoc);
        if (activeDocEntry) {
            currentExplorerFolder = activeDocEntry.file_set || 'workspace';
            if (activeDocEntry.runs && activeDocEntry.runs.length > 0) {
                const hasRun = activeDocEntry.runs.some(r => r.run_id === currentExplorerRun);
                if (!hasRun) {
                    currentExplorerRun = activeDocEntry.latest_run
                        ? (activeDocEntry.latest_run.run_id || activeDocEntry.latest_run.output_dir)
                        : (activeDocEntry.runs[0].run_id || activeDocEntry.runs[0].output_dir);
                }
            } else {
                currentExplorerRun = '';
            }
        } else {
            currentExplorerRun = data.active_run || '';
            if (fileSets.length > 0 && !currentExplorerFolder) currentExplorerFolder = fileSets[0].file_set;
        }

        if (expandedFolders.size === 0 && data.file_sets) {
            data.file_sets.forEach(fs => expandedFolders.add(fs.file_set));
        }
        renderExplorerUI();
    } catch (e) {
        console.log('[WARN] Failed to load file run mappings:', e);
    }
}

/** Finds the currently selected run metadata object from explorer dataset. */
function getSelectedRunObject() {
    if (!window.explorerData || !currentExplorerRun) return null;
    const allMappings = window.explorerData.all_mappings || [];
    if (currentExplorerDoc) {
        const activeDoc = allMappings.find(m => m.file_path === currentExplorerDoc);
        if (activeDoc && activeDoc.runs) {
            const found = activeDoc.runs.find(r => r.run_id === currentExplorerRun)
                || activeDoc.runs.find(r => r.output_dir === currentExplorerRun);
            if (found) return { doc: activeDoc, run: found };
        }
    }
    for (const doc of allMappings) {
        if (doc.runs) {
            const found = doc.runs.find(r => r.run_id === currentExplorerRun)
                || doc.runs.find(r => r.output_dir === currentExplorerRun);
            if (found) return { doc, run: found };
        }
    }
    return null;
}

/** Renders both hierarchical tree explorer pane and active main explorer view. */
function renderExplorerUI() {
    const data = window.explorerData;
    if (!data) return;

    const docBreadcrumb = document.getElementById('explorerActiveDocText');
    const runBreadcrumb = document.getElementById('explorerActiveRunText');
    const hiddenDocInput = document.getElementById('inpPdfPath');
    const docCountBadge = document.getElementById('explorerDocCount');

    if (currentExplorerScope === 'directory') {
        if (docBreadcrumb) docBreadcrumb.textContent = `[DIR] ${currentExplorerFolder || 'workspace'}`;
        if (runBreadcrumb) runBreadcrumb.textContent = '(directory scope)';
    } else if (currentExplorerScope === 'run') {
        if (docBreadcrumb) docBreadcrumb.textContent = currentExplorerDoc || 'Document';
        if (runBreadcrumb) runBreadcrumb.textContent = currentExplorerRun || 'Active Run';
    } else {
        if (docBreadcrumb) docBreadcrumb.textContent = currentExplorerDoc || 'None selected';
        if (runBreadcrumb) runBreadcrumb.textContent = currentExplorerRun ? `[RUN] ${currentExplorerRun}` : '(select run)';
    }

    if (hiddenDocInput && currentExplorerDoc) hiddenDocInput.value = currentExplorerDoc;
    if (docCountBadge) docCountBadge.textContent = `${data.total_documents} files · ${data.total_runs} runs`;

    renderExplorerTree();
    renderExplorerMainView();
}

/** Renders hierarchical tree on the left. Exactly one row is highlighted for active scope. */
function renderExplorerTree() {
    const container = document.getElementById('explorerTreeContainer');
    if (!container || !window.explorerData) return;

    const query = explorerSearchQuery.toLowerCase().trim();
    const fileSets = window.explorerData.file_sets || [];
    if (fileSets.length === 0) {
        container.innerHTML = '<div class="explorer-empty-msg">No documents discovered.</div>';
        return;
    }

    let html = '<div class="explorer-tree">';
    fileSets.forEach(fs => {
        const matchingDocs = fs.documents.filter(doc => {
            if (!query) return true;
            if (doc.file_name.toLowerCase().includes(query) || doc.file_path.toLowerCase().includes(query) || fs.file_set.toLowerCase().includes(query)) return true;
            return doc.runs.some(r => r.preset.toLowerCase().includes(query) || r.run_id.toLowerCase().includes(query));
        });
        if (matchingDocs.length === 0) return;

        const isExpanded = expandedFolders.has(fs.file_set);
        const folderArrow = isExpanded ? '▾' : '▸';
        const folderClass = (currentExplorerScope === 'directory' && fs.file_set === currentExplorerFolder) ? ' selected' : '';

        html += `<div class="tree-node tree-folder-node"><div class="tree-row folder-row${folderClass}" onclick="selectExplorerFolder('${escapeHtml(fs.file_set)}')">`
            + `<span class="tree-toggle-arrow" onclick="event.stopPropagation(); toggleExplorerFolder('${escapeHtml(fs.file_set)}')">${folderArrow}</span>`
            + `<span class="tree-icon folder-icon">[DIR]</span><span class="tree-label folder-label">${escapeHtml(fs.file_set)}</span>`
            + `<span class="tree-node-badge">${matchingDocs.length}</span></div>`;

        if (isExpanded) {
            html += '<div class="tree-children">';
            matchingDocs.forEach(doc => {
                const docClass = (currentExplorerScope === 'file' && doc.file_path === currentExplorerDoc) ? ' selected' : '';
                const runCount = doc.runs_count || 0;

                html += `<div class="tree-node tree-file-node"><div class="tree-row file-row${docClass}" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">`
                    + `<span class="tree-icon file-icon">[PDF]</span><span class="tree-label file-label" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_name)}</span>`
                    + `<span class="tree-runs-count-badge" title="${runCount} past runs">${runCount} runs</span></div>`;

                if (doc.runs && doc.runs.length > 0) {
                    html += '<div class="tree-runs-list">';
                    doc.runs.forEach(r => {
                        const isRunSelected = (currentExplorerScope === 'run' && r.run_id === currentExplorerRun);
                        const runClass = isRunSelected ? ' active-run-node selected' : '';
                        const statusClass = (r.status === 'ACCEPT') ? 'status-pass' : 'status-warn';
                        const scoreDisplay = Number(r.overall_confidence).toFixed(2);
                        const hasPages = Boolean(r.total_pages && r.total_pages > 0);
                        const isRunExpanded = expandedRuns.has(r.run_id);
                        const runArrow = hasPages ? (isRunExpanded ? '▾' : '▸') : '';

                        html += `<div class="tree-row run-row${runClass}" onclick="selectExplorerRun('${escapeHtml(r.run_id)}', '${escapeHtml(r.output_dir)}', '${escapeHtml(doc.file_path)}')">`
                            + (hasPages ? `<span class="tree-toggle-arrow run-pages-toggle" onclick="event.stopPropagation(); toggleExplorerRunPages('${escapeHtml(r.run_id)}')">${runArrow}</span>` : '<span class="tree-arrow-spacer"></span>')
                            + `<span class="tree-icon run-icon">[RUN]</span><span class="run-preset-tag">${escapeHtml(r.preset)}</span>`
                            + `<span class="run-score-badge ${statusClass}">${scoreDisplay}</span><span class="run-name-label" title="${escapeHtml(r.run_id)}">${escapeHtml(r.run_id)}</span></div>`;

                        if (hasPages && isRunExpanded) {
                            html += '<div class="tree-pages-list">';
                            for (let p = 1; p <= r.total_pages; p++) {
                                const pStr = String(p);
                                const conf = (r.per_page_confidence && r.per_page_confidence[pStr] !== undefined)
                                    ? Number(r.per_page_confidence[pStr]) : r.overall_confidence;
                                const viols = (r.per_page_violations && r.per_page_violations[pStr] !== undefined)
                                    ? r.per_page_violations[pStr] : 0;
                                const pStatus = (conf >= 0.85) ? 'status-pass' : 'status-warn';

                                html += `<div class="tree-page-row" onclick="event.stopPropagation(); chooseRunAndPage('${escapeHtml(r.run_id)}', ${p})" title="Open page ${p} in viewer">`
                                    + `<span class="tree-icon page-icon">[P${p}]</span><span class="run-score-badge ${pStatus}">${Number(conf).toFixed(2)}</span>`
                                    + `<span class="page-viols-badge">${viols}v</span></div>`;
                            }
                            html += '</div>';
                        }
                    });
                    html += '</div>';
                } else {
                    html += `<div class="tree-empty-runs-prompt" onclick="event.stopPropagation(); selectDocAndOpenPlanning('${escapeHtml(doc.file_path)}')">`
                        + `<span class="tree-prompt-plus">+</span><span class="tree-prompt-label">Parsing planning</span></div>`;
                }
                html += '</div>';
            });
            html += '</div>';
        }
        html += '</div>';
    });

    html += '</div>';
    container.innerHTML = html;
}

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

        rowsHtml += `<tr onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">`
            + `<td><span class="file-name-cell" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_name)}</span></td>`
            + `<td><span class="file-path-sub">${escapeHtml(doc.file_path)}</span></td><td><span class="tree-runs-count-badge">${runCount} runs</span></td>`
            + `<td>${presetBadge}</td><td>${scoreBadge}</td><td>${statusBadge}</td>`
            + `<td class="action-cell"><button class="btn btn-secondary btn-xs" onclick="event.stopPropagation(); selectExplorerDoc('${escapeHtml(doc.file_path)}')">Explore runs</button></td></tr>`;
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

    if (titleEl) titleEl.textContent = `File runs: ${docName}`;
    if (tableHead) tableHead.innerHTML = '<tr><th>Run ID</th><th>Preset</th><th>Score</th><th>Viols</th><th>Status</th><th>Time</th><th>Action</th></tr>';
    if (!tbody) return;

    const runs = (doc && doc.runs) ? doc.runs : [];
    const filteredRuns = runs.filter(r => !query || r.run_id.toLowerCase().includes(query) || r.preset.toLowerCase().includes(query) || r.status.toLowerCase().includes(query));

    let rowsHtml = '';
    if (filteredRuns.length === 0) {
        rowsHtml += '<tr><td colspan="7" class="table-empty-message">No parsing runs recorded for this file yet. Select a preset below to run it.</td></tr>';
    } else {
        filteredRuns.forEach(run => {
            const isSelectedRun = (currentExplorerScope === 'run' && run.run_id === currentExplorerRun);
            const rowClass = isSelectedRun ? 'explorer-row-selected' : '';
            const statusBadgeClass = (run.status === 'ACCEPT') ? 'badge-accept' : 'badge-warn';
            const scoreFormatted = Number(run.overall_confidence).toFixed(4);

            rowsHtml += `<tr class="${rowClass}" onclick="selectExplorerRun('${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(docPath)}')">`
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
    if (presetEl) presetEl.value = chosenPreset;

    if (typeof triggerRunPipeline === 'function') {
        await triggerRunPipeline(false);
    }
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

/** Loads the chosen run into active session and navigates to the page in the viewer. */
async function chooseRunAndPage(runId, pageNo) {
    const targetPage = parseInt(pageNo, 10) || 1;
    if (typeof choosePreviousRun === 'function') await choosePreviousRun(runId, targetPage, false);
    if (typeof switchNavTab === 'function') switchNavTab('results');
    if (typeof reloadViewerIframe === 'function') reloadViewerIframe(targetPage, runId);
}

/** Selects an explorer directory and shifts main window scope to directory files. */
function selectExplorerFolder(folder) {
    currentExplorerScope = 'directory';
    currentExplorerFolder = folder;
    if (!expandedFolders.has(folder)) expandedFolders.add(folder);
    renderExplorerUI();
}

/** Selects an input document from tree or table, updating input state. */
function selectExplorerDoc(docPath) {
    currentExplorerScope = 'file';
    currentExplorerDoc = docPath;
    const inp = document.getElementById('inpPdfPath');
    if (inp) inp.value = docPath;
    if (typeof selectDocPath === 'function') selectDocPath(docPath);

    const allMappings = (window.explorerData && window.explorerData.all_mappings) || [];
    const docEntry = allMappings.find(m => m.file_path === docPath);
    if (docEntry) {
        currentExplorerFolder = docEntry.file_set;
        if (docEntry.runs && docEntry.runs.length > 0) {
            const hasCurrentRun = docEntry.runs.some(r => r.run_id === currentExplorerRun);
            if (!hasCurrentRun) {
                currentExplorerRun = docEntry.latest_run
                    ? (docEntry.latest_run.run_id || docEntry.latest_run.output_dir)
                    : (docEntry.runs[0].run_id || docEntry.runs[0].output_dir);
            }
        } else {
            currentExplorerRun = '';
        }
    } else {
        currentExplorerRun = '';
    }
    renderExplorerUI();
}

/** Selects an input document and switches directly to Planning tab. */
function selectDocAndOpenPlanning(docPath) {
    selectExplorerDoc(docPath);
    if (typeof switchNavTab === 'function') switchNavTab('plan');
}

/** Selects a specific historical run, shifting main window scope to run pages breakdown. */
async function selectExplorerRun(runId, outputDir, docPath) {
    currentExplorerScope = 'run';
    currentExplorerRun = runId;
    if (docPath) {
        currentExplorerDoc = docPath;
        const allMappings = (window.explorerData && window.explorerData.all_mappings) || [];
        const docEntry = allMappings.find(m => m.file_path === docPath);
        if (docEntry) currentExplorerFolder = docEntry.file_set;
        const inp = document.getElementById('inpPdfPath');
        if (inp) inp.value = docPath;
    }
    renderExplorerUI();
    if (typeof choosePreviousRun === 'function') {
        await choosePreviousRun(runId || outputDir, 1, false);
    }
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

/** Toggles expanding and collapsing of folder nodes in the tree. */
function toggleExplorerFolder(folder) {
    if (expandedFolders.has(folder)) expandedFolders.delete(folder);
    else expandedFolders.add(folder);
    renderExplorerTree();
}

/** Toggles expanding and collapsing of per-page items under a specific run in the tree. */
function toggleExplorerRunPages(runId) {
    if (expandedRuns.has(runId)) expandedRuns.delete(runId);
    else expandedRuns.add(runId);
    renderExplorerTree();
}

/** Live search input handler filtering both tree and table items. */
function onExplorerSearchChanged(query) {
    explorerSearchQuery = query;
    renderExplorerTree();
    renderExplorerMainView();
}

/** Refreshes explorer data from backend. */
function refreshExplorerData() {
    loadFileRunMappings();
}
