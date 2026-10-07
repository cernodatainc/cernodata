/**
 * src/visualization/viewer/js/decollide_components.js
 *
 * Reusable UI presentation components and HTML templates for pairwise decollision,
 * overlap inspection, and element merge configuration cards.
 */

/**
 * Renders HTML markup for the collision status badge between two bounding boxes.
 *
 * @param {boolean} hasCollision - Whether vertical and horizontal overlap exist.
 * @param {number} vOverlap - Vertical overlap in points.
 * @param {number} hOverlap - Horizontal overlap in points.
 * @param {number} gap - Vertical gap when there is no collision.
 * @returns {string} HTML markup.
 */
function renderCollisionStatusBadgeComponent(hasCollision, vOverlap, hOverlap, gap) {
    if (hasCollision) {
        return `
            <div class="collision-status-badge overlap">
                <span>[!] Skew Overlap: ${vOverlap.toFixed(2)} pt</span>
                <span>Horiz: ${hOverlap.toFixed(2)} pt</span>
            </div>
        `;
    }
    return `
        <div class="collision-status-badge clean">
            <span>[OK] No Overlap Detected</span>
            <span>Gap: ${gap.toFixed(2)} pt</span>
        </div>
    `;
}

/**
 * Renders merge configuration editor card when both elements are textual.
 *
 * @param {Object} upper - Top/primary DOM node.
 * @param {Object} lower - Bottom/secondary DOM node.
 * @param {string} defaultMergedText - Precalculated merged text preview.
 * @returns {string} HTML markup.
 */
function renderMergeTextualEditorComponent(upper, lower, defaultMergedText) {
    return `
        <div class="merge-editor-card">
            <div class="merge-editor-title">
                <span>[MERGE] Merge Elements (${escapeHtml(upper.type)})</span>
                <span class="badge-status" style="font-size:9px; background:#065F46; color:#6EE7B7;">Textual</span>
            </div>
            <div class="merge-editor-subtitle">
                Both elements are textual (${escapeHtml(upper.type)}). Text will be merged in reading order.
            </div>
            <div class="merge-field-group">
                <label class="merge-field-label">Merged Text Preview (editable):</label>
                <textarea id="mergeMergedText" class="merge-textarea" rows="3">${escapeHtml(defaultMergedText)}</textarea>
            </div>
            <button class="btn-merge textual" id="btnMergeElements" onclick="executeMergeElements()">
                [MERGE] Merge Textual Elements
            </button>
        </div>
    `;
}

/**
 * Renders merge configuration editor card when elements are of different types.
 *
 * @param {Object} upper - Top/primary DOM node.
 * @param {Object} lower - Bottom/secondary DOM node.
 * @param {string} defaultMergedText - Precalculated merged text preview.
 * @returns {string} HTML markup.
 */
function renderMergeDifferentTypesEditorComponent(upper, lower, defaultMergedText) {
    return `
        <div class="merge-editor-card" style="border-color:#F59E0B;">
            <div class="merge-editor-title" style="color:#FBBF24;">
                <span>[MERGE] Merge Elements (Different Types)</span>
                <span class="badge-status" style="font-size:9px; background:#78350F; color:#FDE68A;">${escapeHtml(upper.type)} vs ${escapeHtml(lower.type)}</span>
            </div>
            <div class="merge-editor-subtitle">
                Both elements are of different types. Select what happens to the merged element:
            </div>
            <div class="merge-field-group">
                <label class="merge-field-label">Resulting Element Type:</label>
                <select id="mergeTargetType" class="type-filter" style="width: 100%;" onchange="onMergeConfigChanged()">
                    <option value="${escapeHtml(upper.type)}" selected>Keep '${escapeHtml(upper.type)}' (from ${escapeHtml(upper.node_id)})</option>
                    <option value="${escapeHtml(lower.type)}">Keep '${escapeHtml(lower.type)}' (from ${escapeHtml(lower.node_id)})</option>
                    <option value="paragraph">paragraph</option>
                    <option value="heading">heading</option>
                    <option value="table_grid">table_grid</option>
                    <option value="figure">figure</option>
                    <option value="header_footer">header_footer</option>
                </select>
            </div>
            <div class="merge-field-group">
                <label class="merge-field-label">Content / Text Handling:</label>
                <select id="mergeContentAction" class="type-filter" style="width: 100%;" onchange="onMergeConfigChanged()">
                    <option value="concat" selected>Merge text from both elements (${escapeHtml(upper.node_id)} + ${escapeHtml(lower.node_id)})</option>
                    <option value="keep_upper">Keep only ${escapeHtml(upper.node_id)} content ('${escapeHtml(upper.type)}')</option>
                    <option value="keep_lower">Keep only ${escapeHtml(lower.node_id)} content ('${escapeHtml(lower.type)}')</option>
                    <option value="custom">Custom text</option>
                </select>
            </div>
            <div class="merge-field-group">
                <label class="merge-field-label">Resulting Text Preview (editable):</label>
                <textarea id="mergeMergedText" class="merge-textarea" rows="3">${escapeHtml(defaultMergedText)}</textarea>
            </div>
            <button class="btn-merge different-type" id="btnMergeElements" onclick="executeMergeElements()">
                [MERGE] Merge Elements as Selected
            </button>
        </div>
    `;
}

/**
 * Renders merge configuration editor card when combining non-textual elements.
 *
 * @param {Object} upper - Top/primary DOM node.
 * @param {Object} lower - Bottom/secondary DOM node.
 * @returns {string} HTML markup.
 */
function renderMergeNonTextualEditorComponent(upper, lower) {
    return `
        <div class="merge-editor-card">
            <div class="merge-editor-title">
                <span>[MERGE] Merge Elements (${escapeHtml(upper.type)})</span>
                <span class="badge-status" style="font-size:9px; background:#1F2937; color:#9CA3AF;">Non-textual</span>
            </div>
            <div class="merge-editor-subtitle">
                Both elements are of type '${escapeHtml(upper.type)}'. Merging will combine their bounding boxes and properties.
            </div>
            <div class="merge-field-group">
                <label class="merge-field-label">Resulting Element Type:</label>
                <select id="mergeTargetType" class="type-filter" style="width: 100%;">
                    <option value="${escapeHtml(upper.type)}" selected>${escapeHtml(upper.type)}</option>
                    <option value="figure">figure</option>
                    <option value="table_grid">table_grid</option>
                    <option value="paragraph">paragraph</option>
                </select>
            </div>
            <button class="btn-merge different-type" id="btnMergeElements" onclick="executeMergeElements()">
                [MERGE] Combine Bounding Boxes into Single Element
            </button>
        </div>
    `;
}

/**
 * Renders the complete two-node comparison, decollision, and merge card markup.
 *
 * @param {Object} upper - Upper positioned DOM node.
 * @param {Object} lower - Lower positioned DOM node.
 * @param {Object} bUpper - Bounding box of upper node.
 * @param {Object} bLower - Bounding box of lower node.
 * @param {string} statusBadgeHtml - Rendered collision status badge component.
 * @param {string} mergeHtml - Rendered merge editor component.
 * @param {boolean} hasCollision - Whether bounding boxes collide.
 * @returns {string} HTML markup.
 */
function renderTwoNodeDecollideCardComponent(upper, lower, bUpper, bLower, statusBadgeHtml, mergeHtml, hasCollision) {
    const btnStyle = !hasCollision ? 'style="background:#2563EB;"' : '';
    const btnText = hasCollision ? '[AUTO-DECOLLIDE] De-collide Selected Boxes' : 'Evenly Space / Align Boundary';
    const upperText = (upper.content && upper.content.raw_text) ? upper.content.raw_text : '(no text)';
    const lowerText = (lower.content && lower.content.raw_text) ? lower.content.raw_text : '(no text)';

    return `
        <div class="multi-editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Shift-Selection: 2 Boxes</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="clearSelection()">Clear</button>
            </div>
            ${statusBadgeHtml}
            <button class="btn-decollide" onclick="decollideSelectedPair()" ${btnStyle}>
                ${btnText}
            </button>
            ${mergeHtml}
            <div class="pair-node-item" style="border-left: 3px solid #60A5FA;">
                <div class="pair-node-header">
                    <span>Upper: ${escapeHtml(upper.node_id)} (${escapeHtml(upper.type)})</span>
                    <span class="pair-node-coords">Y: [${bUpper.y0}, ${bUpper.y1}]</span>
                </div>
                <div class="cutout-display-box" style="margin-bottom:4px;">
                    <img id="cutoutPreviewImg_${upper.node_id}" class="cutout-img" alt="Upper Cutout" />
                </div>
                <div class="pair-node-text">${escapeHtml(upperText)}</div>
            </div>
            <div class="pair-node-item" style="border-left: 3px solid #A78BFA;">
                <div class="pair-node-header">
                    <span>Lower: ${escapeHtml(lower.node_id)} (${escapeHtml(lower.type)})</span>
                    <span class="pair-node-coords">Y: [${bLower.y0}, ${bLower.y1}]</span>
                </div>
                <div class="cutout-display-box" style="margin-bottom:4px;">
                    <img id="cutoutPreviewImg_${lower.node_id}" class="cutout-img" alt="Lower Cutout" />
                </div>
                <div class="pair-node-text">${escapeHtml(lowerText)}</div>
            </div>
            <div style="margin-top:8px; font-size:10px; color:var(--text-muted);">
                Boundary split calculates the median inter-line position and adjusts top/bottom edges cleanly without manual adjustment.
            </div>
        </div>
    `;
}
