/**
 * src/visualization/landing/matrix_grid.js
 *
 * Runs comparison matrix grid fetching, document selection,
 * cell score rendering, and interactive page navigation.
 */

let currentRunsGridDoc = '';

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
    await choosePreviousRun(runId);
    const frame = document.getElementById('viewerFrame');
    if (frame && pageNo) {
        setTimeout(() => {
            try {
                if (frame.contentWindow && typeof frame.contentWindow.switchPage === 'function') {
                    frame.contentWindow.switchPage(pageNo);
                }
            } catch (e) {
                // Cross-origin or frame not ready
            }
        }, 500);
    }
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
                <td class="grid-page-cell" onclick="chooseRunAndPage('${escapeHtml(r.dir_path || r.run_id)}', ${p})" title="Load ${escapeHtml(r.run_id)} on Page ${p}">
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
                <td><button class="btn btn-sm btn-primary" onclick="choosePreviousRun('${escapeHtml(r.dir_path || r.run_id)}')">[LOAD] Load Run</button></td>
            </tr>
        `;
    }).join('');
}
