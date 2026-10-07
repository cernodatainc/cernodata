/**
 * src/visualization/viewer/js/controls.js
 *
 * Navigation, zoom, layer visibility, tab switching, and timeline controls.
 */

function toggleShowAllDom(force = null) {
    showAllDomNodes = (force !== null) ? Boolean(force) : !showAllDomNodes;
    renderDOMTree();
    return showAllDomNodes;
}

function toggleShowAllViolations(force = null) {
    showAllViolations = (force !== null) ? Boolean(force) : !showAllViolations;
    renderViolationsList();
    return showAllViolations;
}

function renderTimelineButtons() {
    const container = document.getElementById('timelineContainer');
    if (!container) return;
    container.innerHTML = '';
    container.style.display = 'none';
}

function initPageControls() {
    const pageSelect = document.getElementById('pageSelect');
    if (pageSelect) {
        pageSelect.innerHTML = '';
        for (let i = 1; i <= totalPages; i++) {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = `Page ${i}`;
            if (i === currentPage) opt.selected = true;
            pageSelect.appendChild(opt);
        }
    }
    const currNum = document.getElementById('currentPageNum');
    if (currNum) currNum.textContent = String(currentPage);
    const totNum = document.getElementById('totalPagesNum');
    if (totNum) totNum.textContent = String(totalPages);
    updateNavButtonsState();
}

function updateNavButtonsState() {
    const btnPrev = document.getElementById('btnPrevPage');
    if (btnPrev) btnPrev.disabled = (currentPage <= 1);
    const btnNext = document.getElementById('btnNextPage');
    if (btnNext) btnNext.disabled = (currentPage >= totalPages);
}

function onPageSelectChanged(pageNum) {
    switchPage(pageNum);
}

function prevPage() {
    if (currentPage > 1) {
        switchPage(currentPage - 1);
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        switchPage(currentPage + 1);
    }
}

function updateSvgViewBox() {
    const svg = document.getElementById('svgOverlay');
    if (!svg) return;
    const dim = pageDimensions && pageDimensions[currentPage - 1];
    if (dim && dim.width > 0 && dim.height > 0) {
        svg.setAttribute('viewBox', `0 0 ${dim.width} ${dim.height}`);
        return;
    }
    const pageImg = document.getElementById('pageImg');
    if (pageImg && pageImg.naturalWidth > 0 && pageImg.naturalHeight > 0) {
        const w = roundCoord(pageImg.naturalWidth * 72 / 150);
        const h = roundCoord(pageImg.naturalHeight * 72 / 150);
        svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    }
}

function switchPage(pageNum) {
    if (pageNum < 1 || pageNum > totalPages) return;
    currentPage = pageNum;

    const pageImg = document.getElementById('pageImg');
    if (pageImg && pageImages[currentPage - 1]) {
        pageImg.src = pageImages[currentPage - 1];
    }

    updateSvgViewBox();

    const pageSelect = document.getElementById('pageSelect');
    if (pageSelect) pageSelect.value = String(currentPage);
    const currNum = document.getElementById('currentPageNum');
    if (currNum) currNum.textContent = String(currentPage);
    updateNavButtonsState();

    const actTitle = document.getElementById('pageActionTitle');
    if (actTitle) actTitle.textContent = `Page ${currentPage} Controls:`;

    updatePageScoreBadge();

    renderSVGOverlays();
    renderDOMTree();
    renderViolationsList();
    renderSelectedEditor();
}

function updatePageScoreBadge() {
    const attempts = decisionData.attempts || [];
    const currentAttempt = (attempts.length > 1) ? (attempts[activePresetIndex] || attempts[attempts.length - 1]) : null;

    let pageScore = null;
    if (currentAttempt && currentAttempt.per_page_confidence) {
        pageScore = currentAttempt.per_page_confidence[String(currentPage)] || currentAttempt.per_page_confidence[currentPage];
    } else if (decisionData.per_page_confidence) {
        pageScore = decisionData.per_page_confidence[String(currentPage)] || decisionData.per_page_confidence[currentPage];
    }
    if (pageScore === undefined || pageScore === null) {
        pageScore = (currentAttempt && currentAttempt.overall_confidence !== undefined)
            ? currentAttempt.overall_confidence
            : decisionData.overall_confidence;
    }

    const titleEl = document.getElementById('scoreTitle');
    if (titleEl) {
        titleEl.textContent = `Page ${currentPage} Confidence Score: ${pageScore !== undefined && pageScore !== null ? Number(pageScore).toFixed(4) : '1.0000'}`;
    }

    const detBadge = document.getElementById('detectedLangBadge');
    if (detBadge) {
        const detMap = decisionData.detected_languages || detectedLanguagesMap || {};
        const det = detMap[String(currentPage)] || detMap[currentPage] || decisionData.primary_detected_language || 'pl';
        detBadge.textContent = `P${currentPage}: ${det} (Active: ${activeLanguage})`;
    }
}

function adjustZoom(delta) {
    currentZoom = Math.min(2.5, Math.max(0.5, currentZoom + delta));
    applyZoom();
}

function resetZoom() {
    currentZoom = 1.0;
    applyZoom();
}

function fitWidthZoom() {
    const pane = document.getElementById('visualPane');
    const availableW = pane.clientWidth - 40;
    currentZoom = Math.min(2.0, Math.max(0.6, availableW / 880));
    applyZoom();
}

function applyZoom() {
    const container = document.getElementById('canvasContainer');
    container.style.transform = `scale(${currentZoom})`;
    document.getElementById('zoomDisplay').textContent = `${Math.round(currentZoom * 100)}%`;
}

function updateLayers() {
    renderSVGOverlays();
    const showScore = document.getElementById('toggleScore').checked;
    document.getElementById('scoreBadge').style.display = showScore ? 'block' : 'none';
}

function toggleAllCorrections() {
    appliedCorrections = document.getElementById('toggleCorrections').checked;
    renderDOMTree();
    renderSVGOverlays();
}

function showTab(evt, tabId) {
    if (tabId === 'domTab') {
        if (evt && evt.shiftKey) {
            toggleShowAllDom();
        } else {
            toggleShowAllDom(false);
        }
    } else if (tabId === 'violTab') {
        if (evt && evt.shiftKey) {
            toggleShowAllViolations();
        } else {
            toggleShowAllViolations(false);
        }
    }

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    let btn = (evt && evt.currentTarget) ? evt.currentTarget : null;
    if (!btn || !btn.classList || !btn.classList.contains('tab-btn')) {
        if (tabId === 'domTab') btn = document.getElementById('tabBtnDom');
        else if (tabId === 'violTab') btn = document.getElementById('tabBtnViol');
        else if (tabId === 'logTab') btn = document.getElementById('tabBtnLog');
        else if (tabId === 'planTab') btn = document.getElementById('tabBtnPlan');
        else if (tabId === 'runsTab') btn = document.getElementById('tabBtnRuns');
    }
    if (btn) btn.classList.add('active');

    const targetContent = document.getElementById(tabId);
    if (targetContent) targetContent.classList.add('active');

    if (tabId === 'runsTab') {
        loadViewerRunsGrid();
    }
}

async function loadViewerRunsGrid() {
    const cont = document.getElementById('viewerRunsGridContainer');
    if (!cont) return;

    try {
        const docName = (domData && domData.source_filename) || pdfSourceFile || '';
        const query = docName ? `?document=${encodeURIComponent(docName)}` : '';
        const resp = await fetch(`/api/runs_grid${query}`);
        if (resp.ok) {
            const data = await resp.json();
            renderViewerRunsGrid(data);
            return;
        }
    } catch (e) {
        console.log('[INFO] Backend /api/runs_grid not reachable from viewer:', e);
    }

    // Fallback if offline
    renderViewerRunsGridFallback();
}

function updateViewerRunsGridLiveEntry(updateMsg) {
    if (!updateMsg) return;
    const cont = document.getElementById('viewerRunsGridContainer');
    if (!cont) return;
    renderViewerRunsGridFallback();
}

function renderViewerRunsGrid(gridData) {
    const cont = document.getElementById('viewerRunsGridContainer');
    if (!cont) return;

    const pages = gridData.pages || [1];
    const runs = gridData.runs || [];
    const selFile = gridData.selected_file || '';

    if (runs.length === 0) {
        cont.innerHTML = `<div class="empty-state">No previous parsing runs recorded for ${escapeHtml(selFile || 'this document')}.</div>`;
        return;
    }

    const pageHeaders = pages.map(p => `<th>P${p}</th>`).join('');

    const rowsHtml = runs.map(r => {
        const overall = (r.overall_confidence !== undefined && r.overall_confidence !== null)
            ? Number(r.overall_confidence).toFixed(4)
            : '1.0000';
        const isAccept = (r.status === 'ACCEPT');
        const overallCls = isAccept ? 'cell-score-pass' : 'cell-score-fail';

        const pageCells = pages.map(p => {
            const pData = (r.pages_data && r.pages_data[String(p)]) || null;
            if (!pData || pData.confidence === null || pData.confidence === undefined) {
                return `<td><span class="cell-score-none">-</span></td>`;
            }
            const conf = Number(pData.confidence).toFixed(2);
            const scoreCls = pData.is_passed ? 'cell-score-pass' : 'cell-score-fail';
            return `
                <td class="grid-page-cell" onclick="switchPage(${p})" title="Jump to Page ${p} (Score: ${conf})">
                    <span class="${scoreCls}">${conf}</span>
                </td>
            `;
        }).join('');

        return `
            <tr>
                <td title="Run: ${escapeHtml(r.run_id)}">
                    <div style="font-family:monospace;font-weight:600;color:#60A5FA;">${escapeHtml(r.run_id)}</div>
                    <span class="preset-badge" style="font-size:10px;">${escapeHtml(r.preset)}</span>
                </td>
                ${pageCells}
                <td class="${overallCls}">${overall}</td>
                <td><span class="badge-status ${isAccept ? 'pass' : 'fail'}" style="font-size:10px;">${escapeHtml(r.status)}</span></td>
            </tr>
        `;
    }).join('');

    cont.innerHTML = `
        <div style="overflow-x:auto; margin-top:8px;">
            <table class="comparison-table" style="width:100%; font-size:11px;">
                <thead>
                    <tr>
                        <th>Run Identifier</th>
                        ${pageHeaders}
                        <th>Overall</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        </div>
    `;
}

function renderViewerRunsGridFallback() {
    const cont = document.getElementById('viewerRunsGridContainer');
    if (!cont) return;

    const attempts = (decisionData && decisionData.attempts) ? decisionData.attempts : [{
        preset: decisionData.chosen_preset || 'docling_fast',
        overall_confidence: decisionData.overall_confidence || 1.0,
        per_page_confidence: decisionData.per_page_confidence || {},
        status: decisionData.status || 'ACCEPT',
    }];

    const pages = Array.from({ length: totalPages }, (_, i) => i + 1);
    const pageHeaders = pages.map(p => `<th>P${p}</th>`).join('');

    const rowsHtml = attempts.map((att, idx) => {
        const overall = Number(att.overall_confidence || 1.0).toFixed(4);
        const isAccept = (att.status === 'ACCEPT' || att.is_accepted);
        const overallCls = isAccept ? 'cell-score-pass' : 'cell-score-fail';

        const pageCells = pages.map(p => {
            const conf = att.per_page_confidence
                ? (att.per_page_confidence[String(p)] ?? att.per_page_confidence[p])
                : null;
            if (conf === null || conf === undefined) {
                return `<td><span class="cell-score-none">-</span></td>`;
            }
            const scoreCls = Number(conf) >= 0.85 ? 'cell-score-pass' : 'cell-score-fail';
            return `
                <td class="grid-page-cell" onclick="switchPage(${p})" title="Jump to Page ${p}">
                    <span class="${scoreCls}">${Number(conf).toFixed(2)}</span>
                </td>
            `;
        }).join('');

        return `
            <tr>
                <td>
                    <div style="font-family:monospace;font-weight:600;color:#60A5FA;">Attempt ${idx + 1}</div>
                    <span class="preset-badge" style="font-size:10px;">${escapeHtml(att.preset || 'docling_fast')}</span>
                </td>
                ${pageCells}
                <td class="${overallCls}">${overall}</td>
                <td><span class="badge-status ${isAccept ? 'pass' : 'fail'}" style="font-size:10px;">${escapeHtml(att.status || 'ACCEPT')}</span></td>
            </tr>
        `;
    }).join('');

    cont.innerHTML = `
        <div style="overflow-x:auto; margin-top:8px;">
            <table class="comparison-table" style="width:100%; font-size:11px;">
                <thead>
                    <tr>
                        <th>Run Identifier</th>
                        ${pageHeaders}
                        <th>Overall</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        </div>
    `;
}
