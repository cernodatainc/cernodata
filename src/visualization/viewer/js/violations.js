/**
 * src/visualization/viewer/js/violations.js
 *
 * Quality violation inspector, violation card rendering, and automated fix application.
 */

function renderViolationsList() {
    const container = document.getElementById('violListContainer');
    if (!container) return;

    const violationsToDisplay = showAllViolations
        ? violationsData
        : violationsData.filter(v => getViolationPage(v) === currentPage);

    const unfixedCount = violationsToDisplay.filter(v => !v.is_fixed).length;
    const countEl = document.getElementById('violCount');
    if (countEl) countEl.textContent = unfixedCount;

    const labelEl = document.getElementById('violTabLabel');
    if (labelEl) {
        labelEl.textContent = showAllViolations ? 'Violations [ALL]' : 'Violations';
    }

    if (violationsToDisplay.length === 0) {
        if (violationsData.length === 0) {
            container.innerHTML = '<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600;">[OK] Zero quality violations detected for current language/preset.</div>';
        } else {
            container.innerHTML = `<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600; padding: 10px;">
                [OK] Zero quality violations on Page ${currentPage}.<br>
                <span style="font-size:10px; color: var(--text-muted); font-weight:400;">(Shift-click "Violations" tab to show all ${violationsData.length} violation(s) across all pages)</span>
            </div>`;
        }
        return;
    }

    container.innerHTML = '';
    violationsToDisplay.forEach(v => {
        const card = document.createElement('div');
        const isFixed = !!v.is_fixed;
        card.className = `viol-card ${isFixed ? 'fixed' : ''}`;
        const vPage = getViolationPage(v);
        card.onclick = () => selectNode(v.node_id, vPage);
        const canFix = !!v.suggested_correction;
        card.innerHTML = `
            <div class="viol-header">
                <span class="viol-title">[!] ${escapeHtml(v.rule_type)}</span>
                <div style="display:flex; align-items:center; gap:4px;">
                    <span class="badge-status lang" style="font-size:9px; padding:1px 5px;">P${vPage}</span>
                    <span style="font-size: 10px; font-weight:700; color: ${isFixed ? '#10B981' : '#F87171'};">${isFixed ? '[FIXED]' : escapeHtml(v.severity || 'WARNING')}</span>
                </div>
            </div>
            <div style="font-size: 11px; font-family: monospace;">Snippet: '${escapeHtml(v.detected_snippet)}'${v.suggested_correction ? ` -> '${escapeHtml(v.suggested_correction)}'` : ''}</div>
            <div class="viol-desc">${escapeHtml(v.description || '')}</div>
            ${canFix ? `
                ${isFixed ? `
                    <div style="margin-top:6px;"><span class="badge-status" style="font-size:10px; background:#10B981; color:#000; padding:2px 8px; font-weight:700;">[OK] Fix Applied</span></div>
                ` : `
                    <button class="apply-fix-btn" onclick="applySingleFix(event, '${v.violation_id || v.node_id}')">[Fix] Apply Suggested Fix</button>
                `}
            ` : ''}
        `;
        container.appendChild(card);
    });
}

function applySingleFix(evt, idOrNodeId, snippet = null, fix = null) {
    if (evt && evt.stopPropagation) {
        evt.stopPropagation();
    }

    let targetViol = null;
    let targetNodeId = idOrNodeId;
    let targetSnippet = snippet;
    let targetFix = fix;

    if (typeof idOrNodeId === 'string') {
        const found = violationsData.find(v => v.violation_id === idOrNodeId);
        if (found) {
            targetViol = found;
            targetNodeId = found.node_id;
            targetSnippet = snippet || found.detected_snippet;
            targetFix = (fix !== null && fix !== undefined) ? fix : found.suggested_correction;
        }
    }

    if (!targetViol && targetNodeId) {
        targetViol = violationsData.find(v => v.node_id === targetNodeId && (!targetSnippet || v.detected_snippet === targetSnippet));
        if (targetViol) {
            if (!targetSnippet) targetSnippet = targetViol.detected_snippet;
            if (targetFix === null || targetFix === undefined) targetFix = targetViol.suggested_correction;
        }
    }

    const node = domData.nodes.find(n => n.node_id === targetNodeId);
    if (!node) return;

    if (!node.content) {
        node.content = {};
    }

    if (targetSnippet && targetFix !== undefined && targetFix !== null) {
        const currentText = node.content.raw_text || '';
        node.content.raw_text = currentText.split(targetSnippet).join(targetFix);

        if (node.user_correction_note) {
            node.user_correction_note = node.user_correction_note.split(targetSnippet).join(targetFix);
        } else {
            node.user_correction_note = node.content.raw_text;
        }
    }

    node.is_fixed = true;

    if (targetViol) {
        targetViol.is_fixed = true;
    }

    if (targetSnippet) {
        violationsData.forEach(v => {
            if (v.node_id === targetNodeId && v.detected_snippet === targetSnippet) {
                v.is_fixed = true;
            }
        });
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    renderViolationsList();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        banner.textContent = `[OK] Applied violation fix for '${targetNodeId}': '${targetSnippet || ''}' -> '${targetFix || ''}'. Click '[SAVE] Save Annotations' to persist.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}
