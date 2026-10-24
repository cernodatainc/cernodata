/**
 * src/visualization/viewer/js/inspector_components.js
 *
 * Reusable UI presentation components and HTML templates for the inspector pane,
 * DOM element tree cards, and single-node property editors.
 */

/**
 * Colour palette shared with the rest of the UI (landing.css / data_shape_config.css).
 * Tints (*Bg / *Border) are light variants of the accent colours used for badges and notices.
 */
const INSPECTOR_PALETTE = {
    bgDark: '#E4E2DD',
    bgCard: '#F7F6F3',
    bgCardHover: '#E9E7E1',
    white: '#FFFFFF',
    border: '#D0CDC6',
    textPrimary: '#1F1D1A',
    textMuted: '#625E57',
    blue: '#1E4B8A',
    blueBg: '#E8EEF6',
    blueBorder: '#BCCBE0',
    green: '#2E6E52',
    greenBg: '#E6EFEA',
    greenBorder: '#BFD6CA',
    yellow: '#A15C07',
    yellowBg: '#FBEEDC',
    yellowBorder: '#EBCB9F',
    red: '#B42318',
    redBg: '#F8E6E4',
    redBorder: '#E8C3BE',
    purple: '#6B4E9B'
};

/**
 * Returns inline style string for a small status badge in the given colour variant.
 *
 * @param {string} variant - One of 'neutral', 'muted', 'blue', 'blueSolid', 'green', 'red', 'yellow'.
 * @returns {string} Inline CSS declarations.
 */
function inspectorBadgeStyle(variant) {
    const p = INSPECTOR_PALETTE;
    const base = 'font-family:inherit; font-size:11px; font-weight:500; padding:0 6px; border-radius:4px; border:1px solid; white-space:nowrap; line-height:18px;';
    const variants = {
        neutral: `background:${p.white}; border-color:${p.border}; color:${p.textPrimary};`,
        muted: `background:${p.bgCard}; border-color:${p.border}; color:${p.textMuted};`,
        blue: `background:${p.blueBg}; border-color:${p.blueBorder}; color:${p.blue};`,
        blueSolid: `background:${p.blue}; border-color:${p.blue}; color:${p.white};`,
        green: `background:${p.greenBg}; border-color:${p.greenBorder}; color:${p.green};`,
        red: `background:${p.redBg}; border-color:${p.redBorder}; color:${p.red};`,
        yellow: `background:${p.yellowBg}; border-color:${p.yellowBorder}; color:${p.yellow};`
    };
    return base + (variants[variant] || variants.neutral);
}

/**
 * Renders HTML markup for the unselected inspector placeholder state.
 *
 * @returns {string} HTML markup.
 */
function renderEmptySelectionComponent() {
    const p = INSPECTOR_PALETTE;
    return `
        <div class="editor-box" style="border-style:dashed;">
            <div style="font-size:13px; font-weight:600; color:${p.textPrimary}; margin-bottom:4px;">No box selected</div>
            <div style="font-size:12px; color:${p.textMuted}; line-height:1.45;">
                Click a bounding box to inspect or edit its coordinates. <strong style="color:${p.textPrimary}; font-weight:600;">Shift+click</strong> two boxes to compare and decollide them.
            </div>
            <button class="btn-decollide" onclick="decollideCurrentPage()" style="margin-top:10px;">Decollide all page boxes</button>
        </div>
    `;
}

/**
 * Renders HTML markup for quality violations attached to a selected node.
 *
 * @param {Array<Object>} nodeViols - Violations belonging to target node.
 * @param {Object} node - Target DOM node.
 * @param {number} activePresetIndex - Active timeline preset index.
 * @returns {string} HTML markup.
 */
function renderNodeViolationsComponent(nodeViols, node, activePresetIndex) {
    if (!nodeViols || nodeViols.length === 0) return '';
    const p = INSPECTOR_PALETTE;
    return `
        <div class="selected-violations-box" style="background:${p.white}; border:1px solid ${p.border}; border-left:3px solid ${p.red}; color:${p.textPrimary};">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="font-size:13px; font-weight:600; color:${p.textPrimary};">Quality violations (${nodeViols.length})</span>
                <span class="badge-status" style="${inspectorBadgeStyle('muted')}">Violation inspector</span>
            </div>
            ${nodeViols.map((v, vIdx) => {
        const isFixed = !!v.is_fixed || !!node.is_fixed || activePresetIndex === 1;
        const isSupp = isSuppressed(v);
        const canFix = !!(v.suggested_correction || v.suggestion);
        const cat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
        let statusHtml = `<span style="font-size:11px; font-weight:500; color:${p.red};">${escapeHtml(v.severity || 'WARNING')}</span>`;
        if (isFixed) {
            statusHtml = `<span class="badge-status" style="${inspectorBadgeStyle('green')}">Fixed</span>`;
        } else if (isSupp) {
            statusHtml = `<span class="badge-status" style="${inspectorBadgeStyle('green')}">Accepted (false positive)</span>`;
        }

        return `
                    <div class="selected-viol-item" style="border-top: ${vIdx > 0 ? `1px solid ${p.border}` : 'none'}; padding-top: ${vIdx > 0 ? '8px' : '0'}; margin-top: ${vIdx > 0 ? '8px' : '0'};">
                        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                <span style="font-size:13px; font-weight:500; color:${isFixed || isSupp ? p.green : p.red};">${escapeHtml(v.rule_type || v.type)}</span>
                                <span class="badge-status" style="${inspectorBadgeStyle('muted')}">${escapeHtml(cat)}</span>
                            </div>
                            ${statusHtml}
                        </div>
                        <div style="font-size:12px; color:${p.textMuted}; margin-top:4px; line-height:1.45;">${escapeHtml(v.description || '')}</div>
                        ${v.detected_snippet ? `
                            <div style="font-size:12px; font-family:monospace; margin-top:6px; padding:4px 8px; background:${p.bgCard}; border:1px solid ${p.border}; border-radius:4px; color:${p.textPrimary}; word-break:break-word;">
                                <span style="color:${p.textMuted};">Snippet:</span> '${escapeHtml(v.detected_snippet)}'${v.suggested_correction ? ` <span style="color:${p.textMuted};">→</span> '${escapeHtml(v.suggested_correction)}'` : ''}
                            </div>
                        ` : ''}
                        ${v.suggestion && v.suggestion !== v.suggested_correction ? `
                            <div style="font-size:12px; font-family:monospace; margin-top:4px; color:${p.green}; word-break:break-word;">
                                <span style="color:${p.textMuted};">Rewrite:</span> '${escapeHtml(v.suggestion)}'
                            </div>
                        ` : ''}
                        <div style="display:flex; align-items:center; gap:6px; margin-top:8px; flex-wrap:wrap;">
                            ${isSupp ? `
                                <button class="btn-restore-bundle" onclick="toggleSuppressSingleViolation(event, '${v.violation_id}', false)">
                                    Re-flag as active
                                </button>
                            ` : `
                                ${!isFixed ? `
                                    <button class="btn-accept-bundle" onclick="toggleSuppressSingleViolation(event, '${v.violation_id}', true)">
                                        Accept as legitimate
                                    </button>
                                ` : ''}
                            `}
                            ${canFix ? `
                                ${isFixed ? `
                                    <span class="badge-status" style="${inspectorBadgeStyle('green')}">Fix applied</span>
                                ` : `
                                    <button class="apply-fix-btn" style="margin-top:0;" id="btnApplyFix_${node.node_id}_${vIdx}" onclick="applySingleFix(event, '${v.violation_id || node.node_id}')">
                                        Apply suggested fix: '${escapeHtml(v.suggested_correction || v.suggestion)}'
                                    </button>
                                `}
                            ` : `
                                <span style="font-size:11px; color:${p.textMuted};">No automated fix, manual review required</span>
                            `}
                        </div>
                    </div>
                `;
    }).join('')}
        </div>
    `;
}

/**
 * Renders HTML markup for the merged element audit banner if the node is merged.
 *
 * @param {Object} node - Target DOM node.
 * @returns {string} HTML markup.
 */
function renderMergedNodeBadgeComponent(node) {
    if (!node.is_merged && (!node.merged_from || node.merged_from.length === 0)) {
        return '';
    }
    const p = INSPECTOR_PALETTE;
    const origIds = (node.merged_from || []).map(m => escapeHtml(m.node_id)).join(' + ');
    return `
        <div style="background:${p.blueBg}; border:1px solid ${p.blueBorder}; border-radius:6px; padding:8px 10px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                <span style="font-size:12px; font-weight:600; color:${p.blue};">Merged element (${(node.merged_from || []).length} elements combined)</span>
                <button class="action-btn action-btn-decollide-sm" style="color:${p.red}; border-color:${p.redBorder};" onclick="unmergeDOMNode('${node.node_id}')">Undo merge</button>
            </div>
            <div style="font-size:11px; color:${p.textMuted}; margin-top:2px; font-family:monospace;">
                Original: ${origIds}
            </div>
        </div>
    `;
}

/**
 * Renders HTML markup for the image cutout preview card and OCR action triggers.
 *
 * @param {Object} node - Target DOM node.
 * @param {Object} bbox - Node bounding box coordinates.
 * @param {number} effectiveAngle - Effective skew angle in degrees.
 * @param {boolean} hasAngle - Whether a non-zero angle is detected.
 * @param {boolean} isCutoutUnskewed - Whether unskew mode is currently active.
 * @returns {string} HTML markup.
 */
function renderCutoutPreviewCardComponent(node, bbox, effectiveAngle, hasAngle, isCutoutUnskewed) {
    const p = INSPECTOR_PALETTE;
    const w = Math.round(bbox.x1 - bbox.x0);
    const h = Math.round(bbox.y1 - bbox.y0);
    return `
        <div class="cutout-preview-card">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;">
                <span style="font-size:12px; font-weight:600; color:${p.textPrimary};">Page cutout</span>
                <div style="display:flex; align-items:center; gap:6px;">
                    ${hasAngle ? `<span class="badge-status" style="${inspectorBadgeStyle('neutral')} font-family:monospace;">Skew: ${effectiveAngle}&deg;</span>` : ''}
                    <span style="font-size:11px; color:${p.textMuted};">${w} × ${h} pt</span>
                </div>
            </div>
            <div class="cutout-display-box">
                <img id="cutoutPreviewImg_${node.node_id}" class="cutout-img" alt="Selected Bounding Box Cutout" />
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:8px;">
                <span style="font-size:11px; color:${p.textMuted};" id="cutoutModeLabel_${node.node_id}">Mode: ${isCutoutUnskewed ? 'unskewed (rectified)' : 'skewed (oriented selection)'}</span>
                <button class="action-btn action-btn-decollide-sm" id="btnToggleUnskew_${node.node_id}" onclick="toggleCutoutUnskew('${node.node_id}')" title="Transform skewed quadrilateral into a horizontal, unskewed text strip">
                    ${isCutoutUnskewed ? 'Show skewed' : 'Unskew'}
                </button>
            </div>
            <div class="cutout-action-row" style="margin-top:8px; border-top:1px solid ${p.border}; padding-top:8px; display:flex; align-items:center; justify-content:space-between; gap:8px;">
                <span style="font-size:11px; color:${p.textMuted};">Refined extraction pass</span>
                <button class="action-btn action-btn-decollide-sm" id="btnCutoutOcr_${node.node_id}" style="background:${p.textPrimary}; color:${p.bgCard}; border-color:${p.textPrimary};" onclick="triggerCutoutSecondPass('${node.node_id}')" title="Send selected section cutout to backend OCR for targeted transcription">Parse section with OCR</button>
            </div>
        </div>
    `;
}

/**
 * Renders complete HTML markup for the single-node inspector editor pane.
 *
 * @param {Object} node - Target DOM node.
 * @param {Object} options - Configuration parameters including bbox, angles, flags, and HTML sub-components.
 * @returns {string} HTML markup.
 */
function renderSingleNodeEditorComponent(node, options) {
    const p = INSPECTOR_PALETTE;
    const { bbox, effectiveAngle, hasAngle, hasQuad, isIncorrect, noteVal, isCutoutUnskewed, violationsHtml } = options;
    const mergedBadgeHtml = renderMergedNodeBadgeComponent(node);
    const cutoutCardHtml = renderCutoutPreviewCardComponent(node, bbox, effectiveAngle, hasAngle, isCutoutUnskewed);
    const angleVal = (bbox.angle !== undefined && bbox.angle !== 0) ? bbox.angle : effectiveAngle;

    return `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px;">
                <!-- TODO(TASK-701): Replace static (${escapeHtml(node.type)}) label with an interactive <select> dropdown to switch single-node semantic type. -->
                <h4 style="margin-bottom:0;">Selected: <span style="font-family:monospace; font-weight:500;">${escapeHtml(node.node_id)}</span> <span style="color:${p.textMuted}; font-weight:400;">(${escapeHtml(node.type)})</span></h4>
                <button style="background:transparent; border:none; color:${p.textMuted}; cursor:pointer; font-size:12px; padding:2px 4px;" onclick="clearSelection()">Close</button>
            </div>
            ${mergedBadgeHtml}
            <div class="coord-grid">
                <div class="coord-field"><label>X0</label><input type="number" step="0.5" id="inpX0" value="${bbox.x0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y0</label><input type="number" step="0.5" id="inpY0" value="${bbox.y0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>X1</label><input type="number" step="0.5" id="inpX1" value="${bbox.x1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y1</label><input type="number" step="0.5" id="inpY1" value="${bbox.y1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Angle</label><input type="number" step="0.1" id="inpAngle" value="${angleVal}" onchange="onManualCoordChange()"></div>
            </div>
 
            ${cutoutCardHtml}
 
            ${hasQuad ? `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px; padding:6px 10px; background:${p.yellowBg}; border:1px solid ${p.yellowBorder}; border-radius:6px;">
                <span style="font-size:12px; color:${p.yellow}; font-weight:500;">Custom quad polygon active</span>
                <button class="action-btn action-btn-decollide-sm" onclick="resetQuadToRect('${node.node_id}')">Reset to rectangle</button>
            </div>
            ` : ''}
            ${violationsHtml}
            <button class="flag-btn ${isIncorrect ? 'flagged' : ''}" onclick="toggleIncorrectText('${node.node_id}')">
                ${isIncorrect ? 'Flagged as incorrect text (click to unmark)' : 'Mark as incorrect parsed text'}
            </button>
            <div style="margin-top:10px;">
                <!-- TODO(TASK-705): When node.type === 'table_grid', mount an interactive HTML table cell/row/column editor (table_editor.js). -->
                <label style="display:block; font-size:12px; color:${p.textPrimary}; font-weight:500; margin-bottom:2px;">Parsed text / correction note</label>
                <textarea class="note-area" placeholder="Parsed text or manual correction note…" oninput="updateCorrectionNote('${node.node_id}', this.value)">${escapeHtml(noteVal)}</textarea>
            </div>
            <div style="margin-top:8px; display:flex; justify-content:flex-end;">
                <!-- TODO(TASK-702): Add a "Split at Cursor" button to split merged headings/paragraphs into two vertically stacked DOMNodes. -->
                <button class="action-btn action-btn-decollide-sm" style="color:${p.red}; border-color:${p.redBorder};" onclick="deleteDOMNode('${node.node_id}')">Delete element</button>
            </div>
            <div style="margin-top:10px; font-size:11px; color:${p.textMuted}; border-top:1px solid ${p.border}; padding-top:8px; line-height:1.45;">
                Tip: hold Shift and click another box to multi-select and decollide them.
            </div>
        </div>
    `;
}

/**
 * Renders HTML markup for an individual node card in the DOM list tree.
 *
 * @param {Object} node - Target DOM node.
 * @param {Object} options - State options including nodePage, isOnCurrentPage, isFixed, isIncorrect, isSelected, displayText.
 * @returns {string} HTML markup.
 */
function renderDOMTreeNodeCardComponent(node, options) {
    const { nodePage, isOnCurrentPage, isFixed, isIncorrect, hasActiveViol, hasSuppressedViol, displayText } = options;
    const pageBadgeVariant = isOnCurrentPage ? 'blueSolid' : 'muted';
    const isMerged = node.is_merged || (node.merged_from && node.merged_from.length > 0);

    return `
        <div class="node-header">
            <span class="node-id">${escapeHtml(node.node_id)}</span>
            <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap; justify-content:flex-end;">
                <span class="badge-status" style="${inspectorBadgeStyle(pageBadgeVariant)}">P${nodePage}</span>
                <span class="node-type">${escapeHtml(node.type)}</span>
                ${isFixed ? '<span class="node-corrected-badge">Fixed</span>' : ''}
                ${isMerged ? `<span class="badge-status" style="${inspectorBadgeStyle('blue')}">Merged</span>` : ''}
                ${!hasActiveViol && hasSuppressedViol ? `<span class="badge-status" style="${inspectorBadgeStyle('green')}">Accepted</span>` : ''}
                ${isIncorrect ? '<span class="node-incorrect-badge">Incorrect text</span>' : ''}
            </div>
        </div>
        <div class="node-text">${escapeHtml(displayText)}</div>
    `;
}

/**
 * Renders HTML markup for an empty DOM tree view.
 *
 * @param {number} currentPage - Currently active page index.
 * @param {number} totalNodes - Total number of nodes across all pages.
 * @returns {string} HTML markup.
 */
function renderDOMTreeEmptyComponent(currentPage, totalNodes) {
    const p = INSPECTOR_PALETTE;
    return `
        <div style="color:${p.textPrimary}; text-align:center; margin-top:20px; font-size:13px; padding:10px;">
            No DOM elements found on page ${currentPage}.<br>
            <span style="font-size:12px; color:${p.textMuted};">Shift+click the DOM page tab to show all ${totalNodes} elements across all pages.</span>
        </div>
    `;
}