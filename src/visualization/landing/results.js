/**
 * src/visualization/landing/results.js
 *
 * Preset comparison result table rendering, milestone score display,
 * and embedded interactive viewer iframe reloads.
 */

/**
 * Fetches latest preset comparison results from /api/results and renders table.
 */
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

/**
 * Renders the preset attempts and quality violations comparison table.
 *
 * @param {Object} data - Results payload containing attempts array and decision mapping.
 */
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

/**
 * Reloads the embedded visual viewer iframe with a cache-busting timestamp.
 */
function reloadViewerIframe() {
    const frame = document.getElementById('viewerFrame');
    if (frame) {
        frame.src = '/viewer?' + Date.now();
    }
}
