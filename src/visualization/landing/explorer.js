/**
 * src/visualization/landing/explorer.js
 *
 * Workspace file explorer state controller and hierarchical tree navigation.
 * Allows exclusive exploration across directories, documents, and parsing runs.
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

        if (!currentExplorerDoc || !allMappings.some(m => m.file_path === currentExplorerDoc)) {
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
    if (typeof renderExplorerMainView === 'function') renderExplorerMainView();
    if (typeof updateNextStepHints === 'function') updateNextStepHints();
}

/** Renders hierarchical tree on the left. Exactly one row is highlighted for active scope. */
function renderExplorerTree() {
    const container = document.getElementById('explorerTreeContainer');
    if (!container || !window.explorerData) return;

    const query = explorerSearchQuery.toLowerCase().trim();
    const fileSets = window.explorerData.file_sets || [];
    if (fileSets.length === 0) {
        container.innerHTML = '<div class="explorer-empty-msg">No documents discovered. <button class="btn btn-primary btn-xs" onclick="triggerAddFileDiscovery()">+ Add files</button></div>';
        return;
    }

    let html = '<div class="explorer-tree" role="tree" tabindex="0">';
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

                html += `<div class="tree-node tree-file-node"><div class="tree-row file-row${docClass}" data-doc-path="${escapeHtml(doc.file_path)}"`
                    + ` onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')" oncontextmenu="handleExplorerFileContextMenu(event, '${escapeHtml(doc.file_path)}')">`
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

                        html += `<div class="tree-row run-row${runClass}" data-run-id="${escapeHtml(r.run_id)}" data-doc-path="${escapeHtml(doc.file_path)}"`
                            + ` onclick="selectExplorerRun('${escapeHtml(r.run_id)}', '${escapeHtml(r.output_dir)}', '${escapeHtml(doc.file_path)}')"`
                            + ` oncontextmenu="handleExplorerRunContextMenu(event, '${escapeHtml(r.run_id)}', '${escapeHtml(r.output_dir)}', '${escapeHtml(doc.file_path)}')">`
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

    html += '<div class="tree-node tree-add-doc-node"><div class="tree-row tree-add-doc-row" onclick="triggerAddFileDiscovery()" title="Open file explorer to add new documents">'
        + '<span class="tree-prompt-plus">+</span><span class="tree-label add-label">Add documents...</span></div></div>';
    html += '</div>';
    container.innerHTML = html;
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
        const runs = docEntry.runs || [];
        if (runs.length > 0 && !runs.some(r => r.run_id === currentExplorerRun)) {
            currentExplorerRun = docEntry.latest_run
                ? (docEntry.latest_run.run_id || docEntry.latest_run.output_dir)
                : (runs[0].run_id || runs[0].output_dir);
        } else if (runs.length === 0) {
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
    if (typeof renderExplorerMainView === 'function') renderExplorerMainView();
    if (typeof updateNextStepHints === 'function') updateNextStepHints();
}

/** Refreshes explorer data from backend. */
function refreshExplorerData() {
    loadFileRunMappings();
}
