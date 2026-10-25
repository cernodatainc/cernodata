/**
 * src/visualization/landing/explorer.js
 *
 * Quasi file explorer and run mapping repository interface.
 * Displays discovered document files, file sets, and associated historical parsing runs
 * in a hierarchical tree and coherent mappings comparison table.
 */

window.explorerData = null;
let currentExplorerDoc = '';
let currentExplorerRun = '';
let filterTableBySelectedDoc = true;
let explorerSearchQuery = '';
const expandedFolders = new Set();

/**
 * Retrieves file and run mappings from /api/file_run_mappings and renders the explorer.
 */
async function loadFileRunMappings() {
    try {
        const resp = await fetch('/api/file_run_mappings');
        if (!resp.ok) return;
        const data = await resp.json();
        window.explorerData = data;

        if (!currentExplorerDoc && data.active_file) {
            currentExplorerDoc = data.active_file;
        }
        if (!currentExplorerRun && data.active_run) {
            currentExplorerRun = data.active_run;
        }

        // Expand all folders by default on initial load
        if (expandedFolders.size === 0 && data.file_sets) {
            data.file_sets.forEach(fs => expandedFolders.add(fs.file_set));
        }

        renderExplorerUI();
    } catch (e) {
        console.log('[WARN] Failed to load file run mappings:', e);
    }
}

/**
 * Renders both the hierarchical tree explorer pane and the runs mapping table.
 */
function renderExplorerUI() {
    const data = window.explorerData;
    if (!data) return;

    // Synchronize active breadcrumbs and hidden inputs
    const docBreadcrumb = document.getElementById('explorerActiveDocText');
    const runBreadcrumb = document.getElementById('explorerActiveRunText');
    const hiddenDocInput = document.getElementById('inpPdfPath');
    const docCountBadge = document.getElementById('explorerDocCount');

    if (docBreadcrumb) docBreadcrumb.textContent = currentExplorerDoc || 'None selected';
    if (runBreadcrumb) runBreadcrumb.textContent = currentExplorerRun || 'output';
    if (hiddenDocInput && currentExplorerDoc) hiddenDocInput.value = currentExplorerDoc;
    if (docCountBadge) docCountBadge.textContent = `${data.total_documents} files · ${data.total_runs} runs`;

    renderExplorerTree();
    renderRunMappingsTable();
}

/**
 * Renders the hierarchical folder and document tree on the left explorer pane.
 */
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
            if (doc.file_name.toLowerCase().includes(query)) return true;
            if (doc.file_path.toLowerCase().includes(query)) return true;
            if (fs.file_set.toLowerCase().includes(query)) return true;
            return doc.runs.some(r => r.preset.toLowerCase().includes(query) || r.run_id.toLowerCase().includes(query));
        });

        if (matchingDocs.length === 0) return;

        const isExpanded = expandedFolders.has(fs.file_set);
        const folderArrow = isExpanded ? '▾' : '▸';

        html += `
            <div class="tree-node tree-folder-node">
                <div class="tree-row folder-row" onclick="toggleExplorerFolder('${escapeHtml(fs.file_set)}')">
                    <span class="tree-toggle-arrow">${folderArrow}</span>
                    <span class="tree-icon folder-icon">[DIR]</span>
                    <span class="tree-label folder-label">${escapeHtml(fs.file_set)}</span>
                    <span class="tree-node-badge">${matchingDocs.length}</span>
                </div>
        `;

        if (isExpanded) {
            html += '<div class="tree-children">';
            matchingDocs.forEach(doc => {
                const isDocSelected = (doc.file_path === currentExplorerDoc);
                const docClass = isDocSelected ? ' selected' : '';
                const runCount = doc.runs_count || 0;

                html += `
                    <div class="tree-node tree-file-node">
                        <div class="tree-row file-row${docClass}" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">
                            <span class="tree-icon file-icon">[PDF]</span>
                            <span class="tree-label file-label" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_name)}</span>
                            <span class="tree-runs-count-badge" title="${runCount} past runs">${runCount} runs</span>
                        </div>
                `;

                if (doc.runs && doc.runs.length > 0) {
                    html += '<div class="tree-runs-list">';
                    doc.runs.forEach(r => {
                        const isRunSelected = (r.run_id === currentExplorerRun || r.output_dir === currentExplorerRun);
                        const runClass = isRunSelected ? ' active-run-node' : '';
                        const statusClass = (r.status === 'ACCEPT') ? 'status-pass' : 'status-warn';
                        const scoreDisplay = Number(r.overall_confidence).toFixed(2);

                        html += `
                            <div class="tree-row run-row${runClass}" onclick="selectExplorerRun('${escapeHtml(r.run_id)}', '${escapeHtml(r.output_dir)}', '${escapeHtml(doc.file_path)}')">
                                <span class="tree-icon run-icon">[RUN]</span>
                                <span class="run-preset-tag">${escapeHtml(r.preset)}</span>
                                <span class="run-score-badge ${statusClass}">${scoreDisplay}</span>
                                <span class="run-name-label" title="${escapeHtml(r.run_id)}">${escapeHtml(r.run_id)}</span>
                            </div>
                        `;
                    });
                    html += '</div>';
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

/**
 * Renders the coherent runs mapping table on the right explorer pane.
 */
function renderRunMappingsTable() {
    const tbody = document.getElementById('explorerTableBody');
    const titleEl = document.getElementById('explorerTableTitle');
    if (!tbody || !window.explorerData) return;

    const query = explorerSearchQuery.toLowerCase().trim();
    const allMappings = window.explorerData.all_mappings || [];

    let targetDocs = allMappings;
    if (filterTableBySelectedDoc && currentExplorerDoc) {
        targetDocs = allMappings.filter(m => m.file_path === currentExplorerDoc);
        if (titleEl) {
            const activeName = (targetDocs[0] && targetDocs[0].file_name) || currentExplorerDoc;
            titleEl.textContent = `Parsing runs for: ${activeName}`;
        }
    } else {
        if (titleEl) titleEl.textContent = 'All workspace document run mappings';
    }

    const rows = [];
    targetDocs.forEach(doc => {
        if (doc.runs && doc.runs.length > 0) {
            doc.runs.forEach(r => {
                if (query) {
                    const matchDoc = doc.file_name.toLowerCase().includes(query) || doc.file_path.toLowerCase().includes(query);
                    const matchRun = r.preset.toLowerCase().includes(query) || r.run_id.toLowerCase().includes(query) || r.status.toLowerCase().includes(query);
                    if (!matchDoc && !matchRun) return;
                }
                rows.push({ doc, run: r });
            });
        } else if (!filterTableBySelectedDoc) {
            if (!query || doc.file_name.toLowerCase().includes(query)) {
                rows.push({ doc, run: null });
            }
        }
    });

    if (rows.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="table-empty-message">
                    ${filterTableBySelectedDoc ? 'No past runs recorded for this document yet. Click "Start parsing" below to run.' : 'No run mappings matching filter.'}
                </td>
            </tr>
        `;
        return;
    }

    let rowsHtml = '';
    rows.forEach(({ doc, run }) => {
        const isSelectedDoc = (doc.file_path === currentExplorerDoc);
        const isSelectedRun = run && (run.run_id === currentExplorerRun || run.output_dir === currentExplorerRun);
        const rowClass = isSelectedRun ? 'explorer-row-selected' : '';

        if (!run) {
            rowsHtml += `
                <tr class="${rowClass}">
                    <td>
                        <span class="file-name-cell">${escapeHtml(doc.file_name)}</span>
                        <span class="file-set-tag">${escapeHtml(doc.file_set)}</span>
                    </td>
                    <td colspan="5" class="table-muted-cell">Not parsed yet</td>
                    <td>
                        <button class="btn btn-secondary btn-xs" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">Select</button>
                    </td>
                </tr>
            `;
            return;
        }

        const statusBadgeClass = (run.status === 'ACCEPT') ? 'badge-accept' : 'badge-warn';
        const scoreFormatted = Number(run.overall_confidence).toFixed(4);

        rowsHtml += `
            <tr class="${rowClass}">
                <td>
                    <span class="file-name-cell" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_name)}</span>
                    <span class="file-set-tag">${escapeHtml(doc.file_set)}</span>
                </td>
                <td>
                    <span class="run-id-cell">${escapeHtml(run.run_id)}</span>
                    ${run.timestamp ? `<span class="run-time-sub">${escapeHtml(run.timestamp)}</span>` : ''}
                </td>
                <td>
                    <span class="preset-badge">${escapeHtml(run.preset)}</span>
                </td>
                <td>
                    <span class="score-num">${scoreFormatted}</span>
                </td>
                <td>
                    <span class="viol-count">${run.violations_count || 0}</span>
                </td>
                <td>
                    <span class="badge ${statusBadgeClass}">${escapeHtml(run.status)}</span>
                </td>
                <td class="action-cell">
                    <button class="btn btn-secondary btn-xs" onclick="selectExplorerRun('${escapeHtml(run.run_id)}', '${escapeHtml(run.output_dir)}', '${escapeHtml(doc.file_path)}')">Load run</button>
                    <button class="btn btn-subtle btn-xs" onclick="selectExplorerDoc('${escapeHtml(doc.file_path)}')">Select doc</button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

/**
 * Selects an input document from the tree or table, updating input state.
 *
 * @param {string} docPath - Normalized document filesystem path.
 */
function selectExplorerDoc(docPath) {
    currentExplorerDoc = docPath;
    const inp = document.getElementById('inpPdfPath');
    if (inp) inp.value = docPath;

    if (typeof selectDocPath === 'function') {
        selectDocPath(docPath);
    }
    renderExplorerUI();
}

/**
 * Selects a specific historical run, updates document selection, and loads results.
 *
 * @param {string} runId - Identifier of parsing run.
 * @param {string} outputDir - Output directory path.
 * @param {string} docPath - Associated document path.
 */
async function selectExplorerRun(runId, outputDir, docPath) {
    currentExplorerRun = runId;
    if (docPath) {
        currentExplorerDoc = docPath;
        const inp = document.getElementById('inpPdfPath');
        if (inp) inp.value = docPath;
    }

    renderExplorerUI();

    if (typeof choosePreviousRun === 'function') {
        await choosePreviousRun(outputDir || runId);
    }
}

/**
 * Toggles expanding and collapsing of folder nodes in the tree.
 *
 * @param {string} folder - Folder name.
 */
function toggleExplorerFolder(folder) {
    if (expandedFolders.has(folder)) {
        expandedFolders.delete(folder);
    } else {
        expandedFolders.add(folder);
    }
    renderExplorerTree();
}

/**
 * Toggles whether the right table shows runs for the selected document or all documents.
 *
 * @param {boolean} showSelectedOnly - Whether to filter table to selected document.
 */
function toggleExplorerTableScope(showSelectedOnly) {
    filterTableBySelectedDoc = showSelectedOnly;
    const btnActive = document.getElementById('btnFilterActiveDoc');
    const btnAll = document.getElementById('btnFilterAllDocs');

    if (btnActive) btnActive.className = showSelectedOnly ? 'btn-text-toggle active' : 'btn-text-toggle';
    if (btnAll) btnAll.className = showSelectedOnly ? 'btn-text-toggle' : 'btn-text-toggle active';

    renderRunMappingsTable();
}

/**
 * Live search input handler filtering both tree and table items.
 *
 * @param {string} query - Filter query text.
 */
function onExplorerSearchChanged(query) {
    explorerSearchQuery = query;
    renderExplorerTree();
    renderRunMappingsTable();
}

/**
 * Refreshes explorer data from backend.
 */
function refreshExplorerData() {
    loadFileRunMappings();
}
