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
        renderDownstreamRecommendationAndConnectorCard(data);
        renderOutputTestSuiteResultsCard(data);
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
 * Reloads the embedded visual viewer iframe with output_dir and target page coordinates.
 * If the run results are cached in memory and the viewer is active, directly hydrates
 * the viewer to avoid network roundtrips and DOM layout re-parsing.
 *
 * @param {number|null} [pageNum=null] - Target page number to navigate to (1-indexed).
 */
function reloadViewerIframe(pageNum = null, targetRun = null) {
    const frame = document.getElementById('viewerFrame');
    if (!frame) return;

    const page = pageNum || (frame.contentWindow && frame.contentWindow.currentPage) || 1;
    const runDir = targetRun || (typeof activeRunOutputDir !== 'undefined' && activeRunOutputDir) || 'output';
    let stepQuery = '';
    if (runDir.includes(':step_')) {
        const parts = runDir.split(':step_');
        if (parts[1]) {
            stepQuery = `&step=${encodeURIComponent(parts[1])}`;
        }
    }
    const cached = window.runResultsCache && (window.runResultsCache[runDir] || window.runResultsCache[runDir.replace(/\\/g, '/')]);

    if (frame.contentWindow && typeof frame.contentWindow.hydrateViewer === 'function' && cached) {
        try {
            frame.contentWindow.hydrateViewer(cached, page);
            if (typeof frame.contentWindow.switchPage === 'function') {
                frame.contentWindow.switchPage(page);
            }
            return;
        } catch (e) {
            console.log('[WARN] Direct frame hydration failed, falling back to URL navigation:', e);
        }
    }

    frame.src = `/viewer.html?output_dir=${encodeURIComponent(runDir)}&page=${page}${stepQuery}&t=${Date.now()}`;
}

/**
 * No-op UI hook for rendering the visual Downstream Setup Advisor & Watched-Folder Connector card.
 *
 * @param {Object} data - Results payload returned by /api/results.
 */
function renderDownstreamRecommendationAndConnectorCard(data) {
    // TODO(TASK-306): Render the 'Recommended Downstream Setup & Connect Output' card in the Preset Results tab
    // with one-click export buttons and watched-folder / webhook auto-forwarding controls (TASK-301).
    void data;
}

/**
 * Fills the output expectations template dropdown from GET /api/test_templates.
 */
async function loadTestTemplates() {
    const select = document.getElementById('tsTemplate');
    if (!select) return;
    try {
        const resp = await fetch('/api/test_templates');
        if (!resp.ok) return;
        const data = await resp.json();
        (data.templates || []).forEach(name => select.add(new Option(name.replace(/_/g, ' '), name)));
    } catch (e) {
        console.log('[INFO] Failed to load test templates:', e);
    }
}

/**
 * Reads the output expectations card into a POST /api/test_suite_check payload.
 *
 * @returns {Object} Payload with template, required_headers, min_table_columns, and questions.
 */
function readOutputTestSuiteForm() {
    const value = id => (document.getElementById(id) || {}).value || '';
    const questions = value('tsQuestions').split('\n')
        .map(line => line.split('=>'))
        .filter(parts => parts.length > 1 && parts[0].trim() && parts.slice(1).join('=>').trim())
        .map(parts => ({ question: parts[0].trim(), expected_answer: parts.slice(1).join('=>').trim() }));
    return {
        template: value('tsTemplate') || null,
        required_headers: value('tsHeaders').split(',').map(h => h.trim()).filter(Boolean),
        min_table_columns: parseInt(value('tsMinColumns'), 10) || null,
        questions: questions
    };
}

/**
 * Checks the last parsed document against the output expectations card.
 *
 * @param {boolean} onlyIfDefined - Skip silently when the card is empty (used after pipeline runs).
 */
async function runOutputTestSuiteCheck(onlyIfDefined) {
    const payload = readOutputTestSuiteForm();
    const isEmpty = !payload.template && !payload.required_headers.length
        && !payload.min_table_columns && !payload.questions.length;
    if (isEmpty && onlyIfDefined) return;
    try {
        const resp = await fetch('/api/test_suite_check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        renderOutputTestSuiteResultsCard(resp.ok ? data : { error: data.error || resp.statusText });
    } catch (e) {
        renderOutputTestSuiteResultsCard({ error: e.message });
    }
}

/**
 * Renders Pass/Fail badges for output expectations and test questions.
 *
 * @param {Object} data - Payload from /api/test_suite_check; other payloads without results are ignored.
 */
function renderOutputTestSuiteResultsCard(data) {
    const box = document.getElementById('testSuiteResults');
    if (!box || !data || !(data.results || data.error)) return;
    if (data.error) {
        box.innerHTML = `<div class="test-suite-detail">${escapeHtml(data.error)}</div>`;
        return;
    }
    const passed = data.results.filter(r => r.passed).length;
    const rows = data.results.map(r => `<div class="test-suite-result">`
        + `<span class="badge ${r.passed ? 'badge-success' : 'badge-error'}">${r.passed ? 'PASS' : 'FAIL'}</span> `
        + `${escapeHtml(r.label)}`
        + (r.detail ? `<div class="test-suite-detail">${escapeHtml(r.detail)}</div>` : '')
        + `</div>`).join('');
    box.innerHTML = `<div class="test-suite-summary">${passed}/${data.results.length} passed on `
        + `${escapeHtml(data.document || 'last run')}</div>${rows}`;
}
