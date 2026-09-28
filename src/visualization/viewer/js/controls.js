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

    const attempts = decisionData.attempts || [];
    if (attempts && attempts.length > 1) {
        const att1 = attempts[0];
        const att2 = attempts[1];
        const isAtt1Pass = !!att1.is_accepted;
        const isAtt2Pass = !!att2.is_accepted;
        container.innerHTML = `
            <button class="step-btn ${activePresetIndex === 0 ? 'active' : ''}" id="btnPreset1" onclick="switchPreset(0)">
                <span>Step 1: ${escapeHtml(att1.preset || 'docling_fast')}</span>
                <span class="badge-status ${isAtt1Pass ? 'pass' : 'fail'}" id="statusPreset1">${isAtt1Pass ? 'ACCEPT' : 'FALLBACK'}</span>
            </button>
            <button class="step-btn ${activePresetIndex === 1 ? 'active' : ''}" id="btnPreset2" onclick="switchPreset(1)">
                <span>Step 2: ${escapeHtml(att2.preset || 'docling_deep')}</span>
                <span class="badge-status ${isAtt2Pass ? 'pass' : 'fail'}" id="statusPreset2">${isAtt2Pass ? 'ACCEPT' : 'FAIL'}</span>
            </button>
        `;
        return;
    }

    const isAcc = (decisionData.is_accepted !== undefined) ? decisionData.is_accepted : true;
    const chosenPreset = decisionData.chosen_preset || (planData ? planData.primary_preset : 'docling_fast') || 'docling_fast';
    let preset2Name = 'docling_deep';
    if (planData && planData.fallback_queue && planData.fallback_queue.length > 0) {
        const fb = planData.fallback_queue[0];
        preset2Name = (typeof fb === 'object' && fb.preset) ? fb.preset : fb;
    }

    container.innerHTML = `
        <button class="step-btn ${activePresetIndex === 0 ? 'active' : ''}" id="btnPreset1" onclick="switchPreset(0)">
            <span>Step 1: ${escapeHtml(chosenPreset)}</span>
            <span class="badge-status ${isAcc ? 'pass' : 'fail'}" id="statusPreset1">${isAcc ? 'ACCEPT' : 'REJECT'}</span>
        </button>
        <button class="step-btn fallback ${activePresetIndex === 1 ? 'active' : ''}" id="btnPreset2" onclick="switchPreset(1)">
            <span>Step 2: ${escapeHtml(preset2Name)}</span>
            <span class="badge-status" id="statusPreset2" style="background:#4B5563; color:#FFF;">Candidate</span>
        </button>
    `;
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

function switchPage(pageNum) {
    if (pageNum < 1 || pageNum > totalPages) return;
    currentPage = pageNum;

    const pageImg = document.getElementById('pageImg');
    if (pageImg && pageImages[currentPage - 1]) {
        pageImg.src = pageImages[currentPage - 1];
    }

    const svg = document.getElementById('svgOverlay');
    if (svg && pageDimensions[currentPage - 1]) {
        const dim = pageDimensions[currentPage - 1];
        svg.setAttribute('viewBox', `0 0 ${dim.width} ${dim.height}`);
    }

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
    }
    if (btn) btn.classList.add('active');

    const targetContent = document.getElementById(tabId);
    if (targetContent) targetContent.classList.add('active');
}
