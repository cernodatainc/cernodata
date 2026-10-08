/**
 * src/visualization/viewer/js/violations.js
 *
 * Quality violation inspector, category bundling, violation card rendering,
 * category-level false-positive acceptance, and automated fix application.
 */

/**
 * Updates suppression and acceptance state on a violation object and its matching
 * node-level violation entry in domData.
 *
 * @param {Object} v - Violation object to update.
 * @param {boolean} shouldSuppress - Whether the violation should be suppressed.
 */
function setViolationSuppressed(v, shouldSuppress) {
    if (!v) return;
    const suppStr = shouldSuppress ? "true" : "false";
    v.suppressed = suppStr;
    v.accepted = Boolean(shouldSuppress);

    if (domData && domData.nodes) {
        const node = domData.nodes.find(n => n.node_id === v.node_id);
        if (node && node.violations) {
            const nv = node.violations.find(item =>
                (v.violation_id && item.violation_id === v.violation_id) ||
                item.rule_type === v.rule_type
            );
            if (nv) {
                nv.suppressed = suppStr;
                nv.accepted = Boolean(shouldSuppress);
            }
        }
    }
}

/**
 * Renders the categorized list of quality violations for the current page or entire document.
 */
function renderViolationsList() {
    const container = document.getElementById('violListContainer');
    if (!container) return;

    const viols = getViolationsList();
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
        container.innerHTML = renderViolationsEmptyComponent(currentPage, viols.length);
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
        bundleEl.innerHTML = renderViolationBundleComponent(
            cat,
            { totalCount: catViols.length, activeCount: catActiveCount, suppressedCount: catSuppressedCount },
            pageLabel,
            hasFixable
        );

        const itemsContainer = bundleEl.querySelector(`#bundle-items-${cat}`);
        catViols.forEach(v => {
            const card = document.createElement('div');
            const isFixed = !!v.is_fixed;
            const isSupp = isSuppressed(v);
            card.className = `viol-card ${isFixed ? 'fixed' : ''} ${isSupp ? 'suppressed' : ''}`;
            const vPage = getViolationPage(v);
            card.onclick = () => selectNode(v.node_id, vPage);
            const canFix = !!(v.suggested_correction || v.suggestion);

            card.innerHTML = renderViolationCardComponent(v, {
                cat,
                vPage,
                isFixed,
                isSupp,
                canFix
            });
            itemsContainer.appendChild(card);
        });

        container.appendChild(bundleEl);
    });
}

/**
 * Suppresses all violations in the given category on target page (or all pages)
 * as accepted false positives.
 *
 * @param {string} category - Violation category name ('symbols', 'diacritic').
 * @param {number|null} [targetPage=null] - Specific 1-indexed page or null for active context.
 */
function acceptCategoryOnPage(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    let count = 0;

    const viols = getViolationsList();
    viols.forEach(v => {
        const vCat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        const vPage = getViolationPage(v);
        if (vCat === category && (page === null || vPage === page)) {
            setViolationSuppressed(v, true);
            count++;
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

/**
 * Restores previously suppressed violations in a category back to active flagged state.
 *
 * @param {string} category - Violation category name ('symbols', 'diacritic').
 * @param {number|null} [targetPage=null] - Specific 1-indexed page or null for active context.
 */
function restoreCategoryOnPage(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    let count = 0;

    const viols = getViolationsList();
    viols.forEach(v => {
        const vCat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        const vPage = getViolationPage(v);
        if (vCat === category && (page === null || vPage === page)) {
            setViolationSuppressed(v, false);
            count++;
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

/**
 * Toggles suppression state of an individual violation by ID.
 *
 * @param {Event|null} evt - Triggering click event.
 * @param {string} violationId - Unique violation identifier.
 * @param {boolean} [shouldSuppress=true] - Target suppression state.
 */
function toggleSuppressSingleViolation(evt, violationId, shouldSuppress = true) {
    if (evt && evt.stopPropagation) {
        evt.stopPropagation();
    }

    const viols = getViolationsList();
    const v = viols.find(item => item.violation_id === violationId);
    if (!v) return;

    setViolationSuppressed(v, shouldSuppress);

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

/**
 * Batch-applies all automated fixes for fixable violations within a category.
 *
 * @param {string} category - Violation category name.
 * @param {number|null} [targetPage=null] - Specific 1-indexed page or null for active context.
 */
function applyAllFixesForCategory(category, targetPage = null) {
    const page = targetPage !== null ? targetPage : (showAllViolations ? null : currentPage);
    const viols = getViolationsList();
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

/**
 * Applies a single suggested fix to a DOM node and flags the violation as resolved.
 *
 * @param {Event|null} evt - Triggering event.
 * @param {string} idOrNodeId - Violation ID or Node ID.
 * @param {string|null} [snippet=null] - Detected snippet string to replace.
 * @param {string|null} [fix=null] - Replacement correction string.
 */
function applySingleFix(evt, idOrNodeId, snippet = null, fix = null) {
    if (evt && evt.stopPropagation) {
        evt.stopPropagation();
    }

    let targetViol = null;
    let targetNodeId = idOrNodeId;
    let targetSnippet = snippet;
    let targetFix = fix;

    const viols = getViolationsList();
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
        const viols = getViolationsList();
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
