/**
 * src/visualization/landing/matrix_grid.js
 *
 * Runs comparison matrix grid fetching, document selection,
 * cell score rendering, and interactive page navigation.
 */

let currentRunsGridDoc = '';
window.liveRunOverrides = window.liveRunOverrides || {};
window.currentGridData = null;

/**
 * Applies live in-memory execution overrides (e.g. updated confidence or violation counts)
 * to run comparison grid data.
 *
 * @param {Object} gridData - Comparison grid payload containing runs list.
 */
function applyLiveOverridesToGrid(gridData) {
    if (!gridData || !gridData.runs) return;
    const overrides = window.liveRunOverrides || {};
    gridData.runs.forEach(r => {
        const matchKey = Object.keys(overrides).find(k => {
            const ov = overrides[k];
            if (!ov) return false;
            if (ov.runId && ov.runId === r.run_id) return true;
            if (ov.outputDir && ov.preset && r.dir_path === ov.outputDir && r.preset === ov.preset) return true;
            return false;
        });

        if (matchKey) {
            const ov = overrides[matchKey];
            if (ov.overall_confidence !== undefined) {
                r.overall_confidence = ov.overall_confidence;
            }
            if (ov.status) {
                r.status = ov.status;
            }
            if (ov.violationsCount !== undefined) {
                r.violations_count = ov.violationsCount;
            }
            if (ov.perPageConfidence) {
                r.pages_data = r.pages_data || {};
                Object.keys(ov.perPageConfidence).forEach(pStr => {
                    const pNum = parseInt(pStr, 10);
                    if (!r.pages_data[pStr]) {
                        r.pages_data[pStr] = { page: pNum };
                    }
                    const conf = Number(ov.perPageConfidence[pStr]);
                    r.pages_data[pStr].confidence = conf;
                    r.pages_data[pStr].is_passed = (conf >= 0.85);
                    if (ov.perPageViolations && ov.perPageViolations[pStr] !== undefined) {
                        r.pages_data[pStr].violations_count = ov.perPageViolations[pStr];
                    }
                });
            }
        }
    });
}

/**
 * Handles incoming RUN_RESULT_UPDATED messages by updating overrides, local cache,
 * and refreshing the active runs grid view if loaded.
 *
 * @param {Object} updateMsg - Live run update event payload.
 */
function updateRunsGridLiveEntry(updateMsg) {
    if (!updateMsg) return;
    window.liveRunOverrides = window.liveRunOverrides || {};
    if (updateMsg.runId) window.liveRunOverrides[updateMsg.runId] = updateMsg;
    if (updateMsg.outputDir && updateMsg.preset) {
        window.liveRunOverrides[`${updateMsg.outputDir}:${updateMsg.preset}`] = updateMsg;
    }

    if (window.runResultsCache) {
        const cacheEntry = window.runResultsCache[updateMsg.outputDir] || window.runResultsCache[updateMsg.runId];
        if (cacheEntry && cacheEntry.decision) {
            cacheEntry.decision.overall_confidence = updateMsg.overall_confidence;
            cacheEntry.decision.status = updateMsg.status;
            cacheEntry.decision.per_page_confidence = updateMsg.perPageConfidence;
        }
    }

    if (window.currentGridData) {
        applyLiveOverridesToGrid(window.currentGridData);
        renderRunsGrid(window.currentGridData);
    }
}

if (typeof window !== 'undefined') {
    window.addEventListener('message', (evt) => {
        if (evt && evt.data && evt.data.type === 'RUN_RESULT_UPDATED') {
            updateRunsGridLiveEntry(evt.data);
        }
    });
}

/**
 * Fetches run comparison grid data from /api/runs_grid for target document.
 *
 * @param {string|null} [docName=null] - Document filename filter.
 */
async function loadRunsGrid(docName = null) {
    try {
        const query = docName ? `?document=${encodeURIComponent(docName)}` : '';
        const resp = await fetch(`/api/runs_grid${query}`);
        if (!resp.ok) return;
        const gridData = await resp.json();
        currentRunsGridDoc = gridData.selected_file || '';
        window.currentGridData = gridData;
        applyLiveOverridesToGrid(gridData);
        renderRunsGrid(gridData);
    } catch (e) {
        console.log('[WARN] Failed to load previous runs grid:', e);
    }
}

/**
 * Handles document filter change in the runs comparison grid toolbar.
 *
 * @param {string} docName - Newly selected document filename.
 */
function onRunsGridDocChanged(docName) {
    if (docName) {
        loadRunsGrid(docName);
    }
}

/**
 * Loads the chosen run into active session and instructs the viewer iframe
 * to navigate directly to the clicked page number.
 *
 * @param {string} runId - Run identifier or directory path.
 * @param {number} pageNo - Target page number (1-indexed).
 */
async function chooseRunAndPage(runId, pageNo) {
    const targetPage = parseInt(pageNo, 10) || 1;
    await choosePreviousRun(runId, targetPage, false);
    switchNavTab('results');
    reloadViewerIframe(targetPage, runId);
}

/**
 * Renders the two-dimensional comparison grid table:
 * Horizontal axis: Page numbers (1..N).
 * Vertical axis: Parsing run identifiers.
 *
 * @param {Object} gridData - Structured grid payload returned from backend.
 */
function renderRunsGrid(gridData) {
    const thead = document.getElementById('runsGridTableHead');
    const tbody = document.getElementById('runsGridTableBody');
    const docSelect = document.getElementById('runsGridDocSelect');
    if (!thead || !tbody) return;

    const files = gridData.available_files || [];
    const selectedFile = gridData.selected_file || '';
    const pages = gridData.pages || [1];
    const runs = gridData.runs || [];

    if (docSelect && files.length > 0) {
        docSelect.innerHTML = files.map(f => {
            const sel = (f === selectedFile) ? ' selected' : '';
            return `<option value="${escapeHtml(f)}"${sel}>${escapeHtml(f)}</option>`;
        }).join('');
    }

    // Horizontal axis: Page numbers
    const pageHeaders = pages.map(p => `<th>Page ${p}</th>`).join('');
    thead.innerHTML = `
        <tr>
            <th>Parsing Run Identifier</th>
            ${pageHeaders}
            <th>Overall Score</th>
            <th>Violations</th>
            <th>Status</th>
            <th>Action</th>
        </tr>
    `;

    if (runs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${pages.length + 5}" class="table-empty-message">No previous parsing runs found for ${escapeHtml(selectedFile || 'selected document')}.</td></tr>`;
        return;
    }

    // Vertical axis: Parsing run identifiers
    tbody.innerHTML = runs.map(r => {
        const overallStr = (r.overall_confidence !== undefined && r.overall_confidence !== null)
            ? Number(r.overall_confidence).toFixed(4)
            : '1.0000';
        const isAccept = (r.status === 'ACCEPT');
        const statusBadgeClass = isAccept ? 'badge-success' : 'badge-error';
        const overallScoreClass = isAccept ? 'cell-score-pass' : 'cell-score-fail';

        const pageCells = pages.map(p => {
            const pageData = (r.pages_data && r.pages_data[String(p)]) || null;
            if (!pageData || pageData.confidence === null || pageData.confidence === undefined) {
                return `<td><span class="cell-score-none">-</span></td>`;
            }
            const conf = Number(pageData.confidence).toFixed(4);
            const pass = pageData.is_passed;
            const scoreCls = pass ? 'cell-score-pass' : 'cell-score-fail';
            const viols = pageData.violations_count || 0;
            const violBadge = viols > 0
                ? `<span class="cell-viols-count">${viols} viols</span>`
                : `<span class="cell-viols-zero">0 viols</span>`;

            return `
                <td class="grid-page-cell" onclick="chooseRunAndPage('${escapeHtml(r.run_id || r.dir_path)}', ${p})" title="Load ${escapeHtml(r.run_id)} on Page ${p}">
                    <div class="page-cell-score ${scoreCls}">${conf}</div>
                    <div class="page-cell-meta">${violBadge}</div>
                </td>
            `;
        }).join('');

        return `
            <tr>
                <td>
                    <div class="grid-run-cell">
                        <span class="grid-run-id">${escapeHtml(r.run_id)}</span>
                        <div><span class="preset-badge">${escapeHtml(r.preset || 'docling_fast')}</span></div>
                    </div>
                </td>
                ${pageCells}
                <td class="${overallScoreClass}">${overallStr}</td>
                <td>${r.violations_count || 0}</td>
                <td><span class="badge ${statusBadgeClass}">${escapeHtml(r.status || 'ACCEPT')}</span></td>
                <td><button class="btn btn-sm btn-primary" onclick="choosePreviousRun('${escapeHtml(r.run_id || r.dir_path)}')">[LOAD] Load Run</button></td>
            </tr>
        `;
    }).join('');
}
