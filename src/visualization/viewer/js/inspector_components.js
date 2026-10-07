/**
 * src/visualization/viewer/js/inspector_components.js
 *
 * Reusable UI presentation components and HTML templates for the inspector pane,
 * DOM element tree cards, and single-node property editors.
 */

/**
 * Renders HTML markup for the unselected inspector placeholder state.
 *
 * @returns {string} HTML markup.
 */
function renderEmptySelectionComponent() {
    return `
        <div class="editor-box" style="border-style:dashed;">
            <div style="font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:4px;">No Box Selected</div>
            <div style="font-size:11px; color:var(--text-muted); line-height:1.4;">
                Click a bounding box to inspect/edit coordinates. <strong>Shift+Click</strong> two boxes to compare and auto-decollide them.
            </div>
            <button class="btn-decollide" onclick="decollideCurrentPage()" style="margin-top:8px;">[AUTO-DECOLLIDE] Decollide All Page Boxes</button>
        </div>
    `;
}

/**
 * Renders HTML markup for quality violations attached to a selected node.
 *
 * @param {Array<Object>} nodeViols - Violations belonging to target node.
 * @param {Object} node - Target DOM node.
 * @param {boolean} appliedCorrections - Whether corrections are globally active.
 * @param {number} activePresetIndex - Active timeline preset index.
 * @returns {string} HTML markup.
 */
function renderNodeViolationsComponent(nodeViols, node, appliedCorrections, activePresetIndex) {
    if (!nodeViols || nodeViols.length === 0) return '';
    return `
        <div class="selected-violations-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:10px; font-weight:700; color:#FCA5A5; text-transform:uppercase;">[!] Quality Violations (${nodeViols.length})</span>
                <span class="badge-status" style="font-size:9px; background:#7F1D1D; color:#FECACA;">Violation Inspector</span>
            </div>
            ${nodeViols.map((v, vIdx) => {
                const isFixed = !!v.is_fixed || !!node.is_fixed || appliedCorrections || activePresetIndex === 1;
                const isSupp = isSuppressed(v);
                const canFix = !!(v.suggested_correction || v.suggestion);
                const cat = v.type || (v.rule_type === 'garbage_character_ratio' ? 'symbols' : 'diacritic');
                let statusColor = '#F87171';
                let statusLabel = escapeHtml(v.severity || 'WARNING');
                if (isFixed) {
                    statusColor = '#10B981';
                    statusLabel = '[FIXED]';
                } else if (isSupp) {
                    statusColor = '#34D399';
                    statusLabel = '[ACCEPTED (FALSE POSITIVE)]';
                }

                return `
                    <div class="selected-viol-item" style="border-top: ${vIdx > 0 ? '1px solid #451A20' : 'none'}; padding-top: ${vIdx > 0 ? '6px' : '0'}; margin-top: ${vIdx > 0 ? '6px' : '0'};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="display:flex; align-items:center; gap:4px;">
                                <span style="font-size:11px; font-weight:600; color:#F87171;">[!] ${escapeHtml(v.rule_type || v.type)}</span>
                                <span class="badge-status" style="font-size:9px; background:#4B5563; color:#E5E7EB;">${escapeHtml(cat)}</span>
                            </div>
                            <span style="font-size:9px; font-weight:700; color:${statusColor};">${statusLabel}</span>
                        </div>
                        <div style="font-size:10px; color:#FECACA; margin-top:2px;">${escapeHtml(v.description || '')}</div>
                        ${v.detected_snippet ? `
                            <div style="font-size:11px; font-family:monospace; margin-top:4px; color:#FDE047;">
                                Snippet: '${escapeHtml(v.detected_snippet)}'${v.suggested_correction ? ` -> '${escapeHtml(v.suggested_correction)}'` : ''}
                            </div>
                        ` : ''}
                        ${v.suggestion && v.suggestion !== v.suggested_correction ? `
                            <div style="font-size:10px; font-family:monospace; margin-top:2px; color:#A7F3D0;">
                                Rewrite: '${escapeHtml(v.suggestion)}'
                            </div>
                        ` : ''}
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
                                    <button class="apply-fix-btn" style="margin-top:0;" id="btnApplyFix_${node.node_id}_${vIdx}" onclick="applySingleFix(event, '${v.violation_id || node.node_id}')">
                                        [Fix] Apply Suggested Fix: '${escapeHtml(v.suggested_correction || v.suggestion)}'
                                    </button>
                                `}
                            ` : `
                                <span style="font-size:9px; color:var(--text-muted);">(No automated fix - manual review required)</span>
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
    const origIds = (node.merged_from || []).map(m => escapeHtml(m.node_id)).join(' + ');
    return `
        <div style="background: rgba(37, 99, 235, 0.15); border: 1px solid #3B82F6; border-radius: 4px; padding: 6px 8px; margin-bottom: 8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:11px; font-weight:600; color:#93C5FD;">[MERGE] Merged Element (${(node.merged_from || []).length} elements combined)</span>
                <button class="action-btn" style="background:#DC2626; color:#FFF; font-size:10px; padding:2px 8px;" onclick="unmergeDOMNode('${node.node_id}')">[UNMERGE] Undo Merge</button>
            </div>
            <div style="font-size:10px; color:#BFDBFE; margin-top:2px;">
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
    const w = Math.round(bbox.x1 - bbox.x0);
    const h = Math.round(bbox.y1 - bbox.y0);
    return `
        <div class="cutout-preview-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:10px; font-weight:700; color:#93C5FD; text-transform:uppercase;">Page Cutout View</span>
                <div style="display:flex; align-items:center; gap:6px;">
                    ${hasAngle ? `<span class="badge-status lang" style="font-size:9px; padding:1px 5px;">Skew: ${effectiveAngle}&deg;</span>` : ''}
                    <span style="font-size:10px; color:var(--text-muted);">${w} x ${h} pt</span>
                </div>
            </div>
            <div class="cutout-display-box">
                <img id="cutoutPreviewImg_${node.node_id}" class="cutout-img" alt="Selected Bounding Box Cutout" />
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                <span style="font-size:9px; color:var(--text-muted);" id="cutoutModeLabel_${node.node_id}">Mode: ${isCutoutUnskewed ? 'Unskewed (Transformed Rectification)' : 'Skewed (Oriented Selection)'}</span>
                <button class="action-btn" id="btnToggleUnskew_${node.node_id}" style="font-size:10px; padding:2px 8px; background:linear-gradient(135deg, #10B981 0%, #0284C7 100%); color:#FFF;" onclick="toggleCutoutUnskew('${node.node_id}')" title="Transform skewed quadrilateral into a horizontal, unskewed text strip">
                    ${isCutoutUnskewed ? '[SKEW] Show Skewed' : '[UNSKEW] Unskew Transformation'}
                </button>
            </div>
            <div class="cutout-action-row" style="margin-top:6px; border-top:1px solid #334155; padding-top:6px; display:flex; align-items:center; justify-content:space-between;">
                <span style="font-size:9px; color:var(--text-muted);">Refined Extraction Pass:</span>
                <button class="action-btn" id="btnCutoutOcr_${node.node_id}" style="font-size:10px; padding:3px 10px; background:linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%); color:#FFF;" onclick="triggerCutoutSecondPass('${node.node_id}')" title="Send selected section cutout to backend OCR for targeted transcription">[OCR] Parse Section with OCR</button>
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
    const { bbox, effectiveAngle, hasAngle, hasQuad, isIncorrect, noteVal, isCutoutUnskewed, violationsHtml } = options;
    const mergedBadgeHtml = renderMergedNodeBadgeComponent(node);
    const cutoutCardHtml = renderCutoutPreviewCardComponent(node, bbox, effectiveAngle, hasAngle, isCutoutUnskewed);
    const angleVal = (bbox.angle !== undefined && bbox.angle !== 0) ? bbox.angle : effectiveAngle;

    return `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Selected: ${escapeHtml(node.node_id)} (${escapeHtml(node.type)})</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="clearSelection()">Close</button>
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
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:10px; color:#FBBF24; font-weight:600;">Custom Quad Polygon Active</span>
                <button style="background:#374151; border:1px solid #4B5563; color:#FFF; font-size:10px; padding:2px 6px; border-radius:3px; cursor:pointer;" onclick="resetQuadToRect('${node.node_id}')">Reset to Rect</button>
            </div>
            ` : ''}
            ${violationsHtml}
            <button class="flag-btn ${isIncorrect ? 'flagged' : ''}" onclick="toggleIncorrectText('${node.node_id}')">
                ${isIncorrect ? '[X] Flagged: Incorrect Parsed Text (Click to Unmark)' : '[!] Mark as Incorrect Parsed Text'}
            </button>
            <div style="margin-top:6px;">
                <label style="font-size:10px; color:var(--text-muted); font-weight:600;">Parsed Text / Correction Note (Defaulted to Content):</label>
                <textarea class="note-area" placeholder="Parsed text / manual correction note..." oninput="updateCorrectionNote('${node.node_id}', this.value)">${escapeHtml(noteVal)}</textarea>
            </div>
            <div style="margin-top:8px; font-size:10px; color:var(--text-muted); border-top:1px solid #334155; padding-top:6px;">
                Tip: Hold Shift and click another box to multi-select and auto-decollide them.
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
    const pageBg = isOnCurrentPage ? '#2563EB' : '#374151';
    const isMerged = node.is_merged || (node.merged_from && node.merged_from.length > 0);

    return `
        <div class="node-header">
            <span class="node-id">${escapeHtml(node.node_id)}</span>
            <div style="display:flex; align-items:center; gap:4px;">
                <span class="badge-status" style="font-size:9px; background:${pageBg}; color:#FFF;">P${nodePage}</span>
                <span class="node-type">${escapeHtml(node.type)}</span>
                ${isFixed ? '<span class="node-corrected-badge">FIXED</span>' : ''}
                ${isMerged ? '<span class="badge-status" style="font-size:9px; background:#1E40AF; color:#DBEAFE;">MERGED</span>' : ''}
                ${!hasActiveViol && hasSuppressedViol ? '<span class="badge-status" style="font-size:9px; background:#065F46; color:#A7F3D0;">ACCEPTED</span>' : ''}
                ${isIncorrect ? '<span class="node-incorrect-badge">INCORRECT TEXT</span>' : ''}
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
    return `
        <div style="color: var(--text-muted); text-align: center; margin-top: 20px; font-size: 12px; padding: 10px;">
            No DOM elements found on Page ${currentPage}.<br>
            <span style="font-size:10px; color: #9CA3AF;">(Shift-click "DOM Page" tab to show all ${totalNodes} elements across all pages)</span>
        </div>
    `;
}
