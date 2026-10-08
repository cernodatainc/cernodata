/**
 * src/visualization/viewer/js/violations_components.js
 *
 * Reusable UI presentation components and HTML templates for quality violations,
 * category bundles, status badges, and violation action cards.
 */

/**
 * Renders HTML markup for empty quality violations state.
 *
 * @param {number} currentPage - Currently active page index.
 * @param {number} totalViolsCount - Total violation count across entire document.
 * @returns {string} HTML markup.
 */
function renderViolationsEmptyComponent(currentPage, totalViolsCount) {
    if (totalViolsCount === 0) {
        return '<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600;">[OK] Zero quality violations detected for current language/preset.</div>';
    }
    return `<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600; padding: 10px;">
        [OK] Zero quality violations on Page ${currentPage}.<br>
        <span style="font-size:10px; color: var(--text-muted); font-weight:400;">(Shift-click "Violations" tab to show all ${totalViolsCount} violation(s) across all pages)</span>
    </div>`;
}

/**
 * Renders HTML markup for the violation card status indicator badge.
 *
 * @param {boolean} isFixed - Whether the violation fix has been applied.
 * @param {boolean} isSupp - Whether the violation is marked as accepted false positive.
 * @param {string} [severity='WARNING'] - Violation severity level.
 * @returns {string} HTML markup.
 */
function renderViolationStatusBadgeComponent(isFixed, isSupp, severity = 'WARNING') {
    if (isFixed) {
        return '<span style="font-size: 10px; font-weight:700; color: #10B981;">[FIXED]</span>';
    } else if (isSupp) {
        return '<span style="font-size: 10px; font-weight:700; color: #34D399;">[ACCEPTED (FALSE POSITIVE)]</span>';
    }
    return `<span style="font-size: 10px; font-weight:700; color: #F87171;">${escapeHtml(severity || 'WARNING')}</span>`;
}

/**
 * Renders HTML markup for category bundle action buttons (Accept All / Restore, Fix All).
 *
 * @param {string} cat - Category name.
 * @param {number} activeCount - Count of currently active violations in category.
 * @param {string} pageLabel - Formatted label for active page scope (e.g. 'Page 1' or 'All Pages').
 * @param {boolean} hasFixable - Whether any violations in category have suggested fixes.
 * @returns {string} HTML markup.
 */
function renderViolationBundleActionsComponent(cat, activeCount, pageLabel, hasFixable) {
    const escapedCat = escapeHtml(cat);
    return `
        <div class="viol-bundle-actions">
            ${activeCount > 0 ? `
                <button class="btn-accept-bundle" onclick="acceptCategoryOnPage('${escapedCat}')">
                    [Accept All '${escapedCat}' on ${pageLabel}]
                </button>
            ` : `
                <button class="btn-restore-bundle" onclick="restoreCategoryOnPage('${escapedCat}')">
                    [Restore '${escapedCat}' on ${pageLabel}]
                </button>
            `}
            ${hasFixable ? `
                <button class="apply-fix-btn" style="margin-top:0;" onclick="applyAllFixesForCategory('${escapedCat}')">
                    [Fix All '${escapedCat}']
                </button>
            ` : ''}
        </div>
    `;
}

/**
 * Renders HTML markup for a category bundle container including header and action controls.
 *
 * @param {string} cat - Category name.
 * @param {Object} counts - Object containing totalCount, activeCount, and suppressedCount.
 * @param {string} pageLabel - Formatted label for active page scope (e.g. 'Page 1' or 'All Pages').
 * @param {boolean} hasFixable - Whether any violations in category have suggested fixes.
 * @returns {string} HTML markup.
 */
function renderViolationBundleComponent(cat, counts, pageLabel, hasFixable) {
    const { totalCount, activeCount, suppressedCount } = counts;
    const escapedCat = escapeHtml(cat);
    const actionsHtml = renderViolationBundleActionsComponent(cat, activeCount, pageLabel, hasFixable);

    return `
        <div class="viol-bundle-header">
            <div style="display:flex; align-items:center; gap:8px;">
                <span class="viol-bundle-title">[Category: ${escapeHtml(cat.toUpperCase())}]</span>
                <span class="badge-status" style="font-size:10px; background:#374151; color:#E5E7EB;">
                    ${totalCount} total | ${activeCount} active | ${suppressedCount} accepted
                </span>
            </div>
            ${actionsHtml}
        </div>
        <div class="viol-bundle-items" id="bundle-items-${escapedCat}"></div>
    `;
}

/**
 * Renders HTML markup for the header of an individual violation card.
 *
 * @param {Object} v - Violation data object.
 * @param {string} cat - Category name.
 * @param {number} vPage - Page number of the violation.
 * @param {boolean} isFixed - Whether the violation fix has been applied.
 * @param {boolean} isSupp - Whether the violation is marked as accepted false positive.
 * @returns {string} HTML markup.
 */
function renderViolationCardHeaderComponent(v, cat, vPage, isFixed, isSupp) {
    const statusHtml = renderViolationStatusBadgeComponent(isFixed, isSupp, v.severity);
    return `
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
    `;
}

/**
 * Renders HTML markup for the snippet and rewrite suggestion lines of a violation card.
 *
 * @param {Object} v - Violation data object.
 * @returns {string} HTML markup.
 */
function renderViolationCardSnippetComponent(v) {
    const snippetHtml = `
        <div style="font-size: 11px; font-family: monospace; color:#FDE047;">
            Snippet: '${escapeHtml(v.detected_snippet || '')}'${v.suggested_correction ? ` -> '${escapeHtml(v.suggested_correction)}'` : ''}
        </div>
    `;
    const rewriteHtml = (v.suggestion && v.suggestion !== v.suggested_correction) ? `
        <div style="font-size: 10px; font-family: monospace; color:#A7F3D0; margin-top:2px;">
            Rewrite: '${escapeHtml(v.suggestion)}'
        </div>
    ` : '';
    return snippetHtml + rewriteHtml;
}

/**
 * Renders HTML markup for the action buttons in a violation card.
 *
 * @param {Object} v - Violation data object.
 * @param {boolean} isFixed - Whether the violation fix has been applied.
 * @param {boolean} isSupp - Whether the violation is marked as accepted false positive.
 * @param {boolean} canFix - Whether suggested correction is available.
 * @returns {string} HTML markup.
 */
function renderViolationCardActionsComponent(v, isFixed, isSupp, canFix) {
    const violationId = v.violation_id || '';
    const targetId = v.violation_id || v.node_id || '';

    return `
        <div style="display:flex; align-items:center; gap:6px; margin-top:6px; flex-wrap:wrap;">
            ${isSupp ? `
                <button class="btn-restore-bundle" onclick="toggleSuppressSingleViolation(event, '${escapeHtml(violationId)}', false)">
                    [Restore] Re-flag as Active
                </button>
            ` : `
                ${!isFixed ? `
                    <button class="btn-accept-bundle" onclick="toggleSuppressSingleViolation(event, '${escapeHtml(violationId)}', true)">
                        [Accept] Accept as Legitimate
                    </button>
                ` : ''}
            `}
            ${canFix ? `
                ${isFixed ? `
                    <span class="badge-status" style="font-size:10px; background:#10B981; color:#000; padding:2px 8px; font-weight:700;">[OK] Fix Applied</span>
                ` : `
                    <button class="apply-fix-btn" style="margin-top:0;" onclick="applySingleFix(event, '${escapeHtml(targetId)}')">[Fix] Apply Suggested Fix</button>
                `}
            ` : ''}
        </div>
    `;
}

/**
 * Renders complete HTML markup for an individual quality violation card.
 *
 * @param {Object} v - Violation data object.
 * @param {Object} options - State options including cat, vPage, isFixed, isSupp, canFix.
 * @returns {string} HTML markup.
 */
function renderViolationCardComponent(v, options) {
    const { cat, vPage, isFixed, isSupp, canFix } = options;
    const headerHtml = renderViolationCardHeaderComponent(v, cat, vPage, isFixed, isSupp);
    const snippetHtml = renderViolationCardSnippetComponent(v);
    const actionsHtml = renderViolationCardActionsComponent(v, isFixed, isSupp, canFix);

    return `
        ${headerHtml}
        ${snippetHtml}
        <div class="viol-desc">${escapeHtml(v.description || '')}</div>
        ${actionsHtml}
    `;
}
