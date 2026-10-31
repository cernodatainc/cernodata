/**
 * src/visualization/viewer/js/violations_components.js
 *
 * Reusable UI presentation components and HTML templates for quality violations,
 * category bundles, status badges, and violation action cards.
 */
 
/**
 * Colour palette shared with the rest of the UI (landing.css / data_shape_config.css).
 * Tints (*Bg / *Border) are light variants of the accent colours used for badges and notices.
 */
const VIOLATIONS_PALETTE = {
    bgCard: '#FDFCFC',
    white: '#FFFFFF',
    border: '#D0CDC6',
    textPrimary: '#1F1D1A',
    textMuted: '#625E57',
    blue: '#1E4B8A',
    green: '#2E6E52',
    greenBg: '#E6EFEA',
    greenBorder: '#BFD6CA',
    yellow: '#A15C07',
    red: '#B42318',
    redBg: '#F8E6E4',
    redBorder: '#E8C3BE'
};
 
/**
 * Returns inline style string for a small status badge in the given colour variant.
 *
 * @param {string} variant - One of 'neutral', 'muted', 'green', 'red'.
 * @returns {string} Inline CSS declarations.
 */
function violationsBadgeStyle(variant) {
    const p = VIOLATIONS_PALETTE;
    const base = 'font-family:inherit; font-size:11px; font-weight:500; padding:0 6px; border-radius:4px; border:1px solid; white-space:nowrap; line-height:18px;';
    const variants = {
        neutral: `background:${p.white}; border-color:${p.border}; color:${p.textPrimary};`,
        muted: `background:${p.bgCard}; border-color:${p.border}; color:${p.textMuted};`,
        green: `background:${p.greenBg}; border-color:${p.greenBorder}; color:${p.green};`,
        red: `background:${p.redBg}; border-color:${p.redBorder}; color:${p.red};`
    };
    return base + (variants[variant] || variants.neutral);
}
 
/**
 * Renders HTML markup for empty quality violations state.
 *
 * @param {number} currentPage - Currently active page index.
 * @param {number} totalViolsCount - Total violation count across entire document.
 * @returns {string} HTML markup.
 */
function renderViolationsEmptyComponent(currentPage, totalViolsCount) {
    const p = VIOLATIONS_PALETTE;
    if (totalViolsCount === 0) {
        return `<div style="color:${p.green}; text-align:center; margin-top:20px; font-size:13px; font-weight:500; padding:10px;">No quality violations for the current language and preset.</div>`;
    }
    return `<div style="color:${p.green}; text-align:center; margin-top:20px; font-size:13px; font-weight:500; padding:10px;">
        No quality violations on page ${currentPage}.<br>
        <span style="font-size:12px; color:${p.textMuted}; font-weight:400;">Shift+click the Violations tab to show all ${totalViolsCount} violation(s) across all pages.</span>
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
    const p = VIOLATIONS_PALETTE;
    if (isFixed) {
        return `<span class="badge-status" style="${violationsBadgeStyle('green')}">Fixed</span>`;
    } else if (isSupp) {
        return `<span class="badge-status" style="${violationsBadgeStyle('green')}">Accepted (false positive)</span>`;
    }
    return `<span style="font-size:11px; font-weight:500; color:${p.red};">${escapeHtml(severity || 'WARNING')}</span>`;
}
 
/**
 * Renders HTML markup for category bundle action buttons (Accept All / Restore, Fix All).
 *
 * @param {string} cat - Category name.
 * @param {number} activeCount - Count of currently active violations in category.
 * @param {string} pageLabel - Formatted label for active page scope (e.g. 'page 1' or 'all pages').
 * @param {boolean} hasFixable - Whether any violations in category have suggested fixes.
 * @returns {string} HTML markup.
 */
function renderViolationBundleActionsComponent(cat, activeCount, pageLabel, hasFixable) {
    const escapedCat = escapeHtml(cat);
    return `
        <div class="viol-bundle-actions">
            ${activeCount > 0 ? `
                <button class="btn-accept-bundle" onclick="acceptCategoryOnPage('${escapedCat}')">
                    Accept all '${escapedCat}' on ${pageLabel}
                </button>
            ` : `
                <button class="btn-restore-bundle" onclick="restoreCategoryOnPage('${escapedCat}')">
                    Restore '${escapedCat}' on ${pageLabel}
                </button>
            `}
            ${hasFixable ? `
                <button class="apply-fix-btn" style="margin-top:0;" onclick="applyAllFixesForCategory('${escapedCat}')">
                    Fix all '${escapedCat}'
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
 * @param {string} pageLabel - Formatted label for active page scope (e.g. 'page 1' or 'all pages').
 * @param {boolean} hasFixable - Whether any violations in category have suggested fixes.
 * @returns {string} HTML markup.
 */
function renderViolationBundleComponent(cat, counts, pageLabel, hasFixable) {
    const { totalCount, activeCount, suppressedCount } = counts;
    const escapedCat = escapeHtml(cat);
    const actionsHtml = renderViolationBundleActionsComponent(cat, activeCount, pageLabel, hasFixable);
 
    return `
        <div class="viol-bundle-header">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span class="viol-bundle-title">Category: ${escapedCat}</span>
                <span class="badge-status" style="${violationsBadgeStyle('muted')}">
                    ${totalCount} total · ${activeCount} active · ${suppressedCount} accepted
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
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span class="viol-title">${escapeHtml(v.rule_type || v.type)}</span>
                <span class="badge-status" style="${violationsBadgeStyle('muted')}">${escapeHtml(cat)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
                <span class="badge-status" style="${violationsBadgeStyle('neutral')}">P${vPage}</span>
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
    const p = VIOLATIONS_PALETTE;
    const snippetHtml = `
        <div style="font-size:12px; font-family:monospace; margin-top:6px; padding:4px 8px; background:${p.bgCard}; border:1px solid ${p.border}; border-radius:4px; color:${p.textPrimary}; word-break:break-word;">
            <span style="color:${p.textMuted};">Snippet:</span> '${escapeHtml(v.detected_snippet || '')}'${v.suggested_correction ? ` <span style="color:${p.textMuted};">→</span> '${escapeHtml(v.suggested_correction)}'` : ''}
        </div>
    `;
    const rewriteHtml = (v.suggestion && v.suggestion !== v.suggested_correction) ? `
        <div style="font-size:12px; font-family:monospace; margin-top:4px; color:${p.green}; word-break:break-word;">
            <span style="color:${p.textMuted};">Rewrite:</span> '${escapeHtml(v.suggestion)}'
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
        <div style="display:flex; align-items:center; gap:6px; margin-top:8px; flex-wrap:wrap;">
            ${isSupp ? `
                <button class="btn-restore-bundle" onclick="toggleSuppressSingleViolation(event, '${escapeHtml(violationId)}', false)">
                    Re-flag as active
                </button>
            ` : `
                ${!isFixed ? `
                    <button class="btn-accept-bundle" onclick="toggleSuppressSingleViolation(event, '${escapeHtml(violationId)}', true)">
                        Accept as legitimate
                    </button>
                ` : ''}
            `}
            ${canFix ? `
                ${isFixed ? `
                    <span class="badge-status" style="${violationsBadgeStyle('green')}">Fix applied</span>
                ` : `
                    <button class="apply-fix-btn" style="margin-top:0;" onclick="applySingleFix(event, '${escapeHtml(targetId)}')">Apply suggested fix</button>
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