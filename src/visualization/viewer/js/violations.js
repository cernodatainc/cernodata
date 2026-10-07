/**
 * src/visualization/viewer/js/violations.js
 *
 * Quality violation inspector, category bundling, violation card rendering,
 * category-level false-positive acceptance, and automated fix application.
 */

function renderViolationsList() {
    const container = document.getElementById('violListContainer');
    if (!container) return;

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    const violationsToDisplay = showAllViolations
        ? viols
        : viols.filter(v => getViolationPage(v) === currentPage);

    const activeCount = violationsToDisplay.filter(v => !v.is_fixed && !isSuppressed(v)).length;
    const countEl = document.getElementById('violCount');
    if (countEl) countEl.textContent = activeCount;

    const labelEl = document.getElementById('violTabLabel');
    if (labelEl) {
        labelEl.textContent = showAllViolations ? 'Violations [ALL]' : 'Violations';
    }

    if (violationsToDisplay.length === 0) {
        if (viols.length === 0) {
            container.innerHTML = '<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600;">[OK] Zero quality violations detected for current language/preset.</div>';
        } else {
            container.innerHTML = `<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600; padding: 10px;">
                [OK] Zero quality violations on Page ${currentPage}.<br>
                <span style="font-size:10px; color: var(--text-muted); font-weight:400;">(Shift-click "Violations" tab to show all ${viols.length} violation(s) across all pages)</span>
            </div>`;
        }
        return;
    }

    // Group violations into category bundles
    const categories = {};
    violationsToDisplay.forEach(v => {
        const cat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        if (!categories[cat]) {
            categories[cat] = [];
        }
        categories[cat].push(v);
    });

    container.innerHTML = '';

    const catKeys = Object.keys(categories).sort();
    catKeys.forEach(cat => {
        const catViols = categories[cat];
        const catActiveCount = catViols.filter(v => !v.is_fixed && !isSuppressed(v)).length;
        const catSuppressedCount = catViols.filter(v => isSuppressed(v)).length;
        const catFixedCount = catViols.filter(v => !!v.is_fixed).length;
        const hasFixable = catViols.some(v => !v.is_fixed && (v.suggested_correction || v.suggestion));

        const bundleEl = document.createElement('div');
        bundleEl.className = 'viol-bundle';

        const pageLabel = showAllViolations ? 'All Pages' : `Page ${currentPage}`;
        bundleEl.innerHTML = `
            <div class="viol-bundle-header">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="viol-bundle-title">[Category: ${escapeHtml(cat.toUpperCase())}]</span>
                    <span class="badge-status" style="font-size:10px; background:#374151; color:#E5E7EB;">
                        ${catViols.length} total | ${catActiveCount} active | ${catSuppressedCount} accepted
                    </span>
                </div>
                <div class="viol-bundle-actions">
                    ${catActiveCount > 0 ? `
                        <button class="btn-accept-bundle" onclick="acceptCategoryOnPage('${escapeHtml(cat)}')">
                            [Accept All '${escapeHtml(cat)}' on ${pageLabel}]
                        </button>
                    ` : `
                        <button class="btn-restore-bundle" onclick="restoreCategoryOnPage('${escapeHtml(cat)}')">
                            [Restore '${escapeHtml(cat)}' on ${pageLabel}]
                        </button>
                    `}
                    ${hasFixable ? `
                        <button class="apply-fix-btn" style="margin-top:0;" onclick="applyAllFixesForCategory('${escapeHtml(cat)}')">
                            [Fix All '${escapeHtml(cat)}']
                        </button>
                    ` : ''}
                </div>
            </div>
            <div class="viol-bundle-items" id="bundle-items-${escapeHtml(cat)}"></div>
        `;

        const itemsContainer = bundleEl.querySelector(`#bundle-items-${cat}`);
        catViols.forEach(v => {
            const card = document.createElement('div');
            const isFixed = !!v.is_fixed;
            const isSupp = isSuppressed(v);
            card.className = `viol-card ${isFixed ? 'fixed' : ''} ${isSupp ? 'suppressed' : ''}`;
            const vPage = getViolationPage(v);
            card.onclick = () => selectNode(v.node_id, vPage);
            const canFix = !!(v.suggested_correction || v.suggestion);

            let statusHtml = '';
            if (isFixed) {
                statusHtml = '<span style="font-size: 10px; font-weight:700; color: #10B981;">[FIXED]</span>';
            } else if (isSupp) {
                statusHtml = '<span style="font-size: 10px; font-weight:700; color: #34D399;">[ACCEPTED (FALSE POSITIVE)]</span>';
            } else {
                statusHtml = `<span style="font-size: 10px; font-weight:700; color: #F87171;">${escapeHtml(v.severity || 'WARNING')}</span>`;
            }

            card.innerHTML = `
                <div class="viol-header">
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span class="viol-title">[!] ${escapeHtml(v.rule_type || v.type)}</span>
                        <span class="badge-status" style="font-size:9px; background:#4B5563; color:#E5E7EB;">${escapeHtml(cat)}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <span class="badge-status lang" style="font-size:9px; padding:1px 5px;">P${vPage}</span>
                        ${statusHtml}
                    </div>
                </div>
                <div style="font-size: 11px; font-family: monospace; color:#FDE047;">
                    Snippet: '${escapeHtml(v.detected_snippet || '')}'${v.suggested_correction ? ` -> '${escapeHtml(v.suggested_correction)}'` : ''}
                </div>
                ${v.suggestion && v.suggestion !== v.suggested_correction ? `
                    <div style="font-size: 10px; font-family: monospace; color:#A7F3D0; margin-top:2px;">
                        Rewrite: '${escapeHtml(v.suggestion)}'
                    </div>
                ` : ''}
                <div class="viol-desc">${escapeHtml(v.description || '')}</div>
                <div style="display:flex; align-items:center; gap:6px; margin-top:6px; flex-wrap:wrap;">
                    ${isSupp ? `
                        <button class="btn-restore-bundle" onclick="toggleSuppressSingleViolation(event, '${v.violation_id}', false)">
                            [Restore] Re-flag as Active
                        </button>
                    ` : `
                        ${!isFixed ? `
                            <button class="btn-accept-bundle" onclick="toggleSuppressSingleViolation(event, '${v.violation_id}', true)">
                                [Accept] Accept as Legitimate
                            </button>
                        ` : ''}
                    `}
                    ${canFix ? `
                        ${isFixed ? `
                            <span class="badge-status" style="font-size:10px; background:#10B981; color:#000; padding:2px 8px; font-weight:700;">[OK] Fix Applied</span>
                        ` : `
                            <button class="apply-fix-btn" style="margin-top:0;" onclick="applySingleFix(event, '${v.violation_id || v.node_id}')">[Fix] Apply Suggested Fix</button>
                        `}
                    ` : ''}
                </div>
            `;
            itemsContainer.appendChild(card);
        });

        container.appendChild(bundleEl);
    });
}

function acceptCategoryOnPage(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    let count = 0;

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    viols.forEach(v => {
        const vCat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        const vPage = getViolationPage(v);
        if (vCat === category && (page === null || vPage === page)) {
            v.suppressed = "true";
            v.accepted = true;
            count++;

            if (domData && domData.nodes) {
                const node = domData.nodes.find(n => n.node_id === v.node_id);
                if (node && node.violations) {
                    const nv = node.violations.find(item => item.violation_id === v.violation_id || item.rule_type === v.rule_type);
                    if (nv) {
                        nv.suppressed = "true";
                        nv.accepted = true;
                    }
                }
            }
        }
    });

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }
    if (typeof saveAnnotations === 'function') {
        saveAnnotations(true);
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    renderViolationsList();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        const pageDesc = page === null ? 'all pages' : `Page ${page}`;
        const scoreStr = (decisionData && decisionData.overall_confidence !== undefined) ? Number(decisionData.overall_confidence).toFixed(4) : '';
        banner.textContent = `[OK] Accepted ${count} '${category}' violation(s) on ${pageDesc} as legitimate false positives. Updated score: ${scoreStr} (${(decisionData && decisionData.status) || 'ACCEPT'}).`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

function restoreCategoryOnPage(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    let count = 0;

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    viols.forEach(v => {
        const vCat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        const vPage = getViolationPage(v);
        if (vCat === category && (page === null || vPage === page)) {
            v.suppressed = "false";
            v.accepted = false;
            count++;

            if (domData && domData.nodes) {
                const node = domData.nodes.find(n => n.node_id === v.node_id);
                if (node && node.violations) {
                    const nv = node.violations.find(item => item.violation_id === v.violation_id || item.rule_type === v.rule_type);
                    if (nv) {
                        nv.suppressed = "false";
                        nv.accepted = false;
                    }
                }
            }
        }
    });

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }
    if (typeof saveAnnotations === 'function') {
        saveAnnotations(true);
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    renderViolationsList();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        const pageDesc = page === null ? 'all pages' : `Page ${page}`;
        const scoreStr = (decisionData && decisionData.overall_confidence !== undefined) ? Number(decisionData.overall_confidence).toFixed(4) : '';
        banner.textContent = `[OK] Restored ${count} '${category}' violation(s) on ${pageDesc} to active state. Updated score: ${scoreStr} (${(decisionData && decisionData.status) || 'ACCEPT'}).`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

function toggleSuppressSingleViolation(evt, violationId, shouldSuppress = true) {
    if (evt && evt.stopPropagation) {
        evt.stopPropagation();
    }

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    const v = viols.find(item => item.violation_id === violationId);
    if (!v) return;

    v.suppressed = shouldSuppress ? "true" : "false";
    v.accepted = !!shouldSuppress;

    if (domData && domData.nodes) {
        const node = domData.nodes.find(n => n.node_id === v.node_id);
        if (node && node.violations) {
            const nv = node.violations.find(item => item.violation_id === violationId || item.rule_type === v.rule_type);
            if (nv) {
                nv.suppressed = shouldSuppress ? "true" : "false";
                nv.accepted = !!shouldSuppress;
            }
        }
    }

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }
    if (typeof saveAnnotations === 'function') {
        saveAnnotations(true);
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    renderViolationsList();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        const scoreStr = (decisionData && decisionData.overall_confidence !== undefined) ? Number(decisionData.overall_confidence).toFixed(4) : '';
        banner.textContent = shouldSuppress
            ? `[OK] Accepted violation '${violationId}' as legitimate false positive. Updated score: ${scoreStr} (${(decisionData && decisionData.status) || 'ACCEPT'}).`
            : `[OK] Re-flagged violation '${violationId}' as active. Updated score: ${scoreStr} (${(decisionData && decisionData.status) || 'ACCEPT'}).`;
        setTimeout(() => { banner.style.display = 'none'; }, 3000);
    }
}

function applyAllFixesForCategory(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    const targets = viols.filter(v => {
        const vCat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        const vPage = getViolationPage(v);
        return vCat === category && (page === null || vPage === page) && !v.is_fixed && (v.suggested_correction || v.suggestion);
    });

    targets.forEach(v => {
        applySingleFix(null, v.violation_id);
    });

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        banner.textContent = `[OK] Applied ${targets.length} fix(es) for '${category}'. Click '[SAVE] Save Annotations' to persist.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

function applySingleFix(evt, idOrNodeId, snippet = null, fix = null) {
    if (evt && evt.stopPropagation) {
        evt.stopPropagation();
    }

    let targetViol = null;
    let targetNodeId = idOrNodeId;
    let targetSnippet = snippet;
    let targetFix = fix;

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    if (typeof idOrNodeId === 'string') {
        const found = viols.find(v => v.violation_id === idOrNodeId);
        if (found) {
            targetViol = found;
            targetNodeId = found.node_id;
            targetSnippet = snippet || found.detected_snippet;
            targetFix = (fix !== null && fix !== undefined) ? fix : (found.suggested_correction || found.suggestion);
        }
    }

    if (!targetViol && targetNodeId) {
        targetViol = viols.find(v => v.node_id === targetNodeId && (!targetSnippet || v.detected_snippet === targetSnippet));
        if (targetViol) {
            if (!targetSnippet) targetSnippet = targetViol.detected_snippet;
            if (targetFix === null || targetFix === undefined) targetFix = (targetViol.suggested_correction || targetViol.suggestion);
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
        const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
        viols.forEach(v => {
            if (v.node_id === targetNodeId && v.detected_snippet === targetSnippet) {
                v.is_fixed = true;
            }
        });
    }

    if (node.violations) {
        node.violations.forEach(nv => {
            if (nv.node_id === targetNodeId || (targetViol && nv.violation_id === targetViol.violation_id)) {
                nv.is_fixed = true;
            }
        });
    }

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }
    if (typeof saveAnnotations === 'function') {
        saveAnnotations(true);
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    renderViolationsList();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        const scoreStr = (decisionData && decisionData.overall_confidence !== undefined) ? Number(decisionData.overall_confidence).toFixed(4) : '';
        banner.textContent = `[OK] Applied violation fix for '${targetNodeId}': '${targetSnippet || ''}' -> '${targetFix || ''}'. Updated score: ${scoreStr} (${(decisionData && decisionData.status) || 'ACCEPT'}).`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}
