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
    bgDark: '#EFF1F2',
    bgCard: '#FDFCFC',
    bgCardHover: '#F5F7F8;',
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
            <div style="display:flex; gap:8px; margin-top:10px;">
                <button class="action-btn action-btn-draw-section-sm" id="btnInspectorDrawSection" onclick="toggleDrawSectionMode()" style="flex:1;">Draw new section</button>
                <button class="btn-decollide" onclick="decollideCurrentPage()" style="flex:1; margin-top:0;">Decollide page</button>
            </div>
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
        const hasCorrection = !!(v.suggested_correction && v.suggested_correction !== v.detected_snippet);
        const canFix = hasCorrection || !!(v.suggestion && v.suggestion !== v.detected_snippet && v.suggestion !== (v.raw_text || ''));
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
                                <span style="color:${p.textMuted};">Snippet:</span> '${escapeHtml(v.detected_snippet)}'${hasCorrection ? ` <span style="color:${p.textMuted};">→</span> '${escapeHtml(v.suggested_correction)}'` : ''}
                            </div>
                        ` : ''}
                        ${hasCorrection && v.suggestion && v.suggestion !== v.suggested_correction ? `
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
    if (!window.selectedOcrEnginesMap) {
        window.selectedOcrEnginesMap = {};
    }
    if (!window.selectedOcrEnginesMap[node.node_id] || window.selectedOcrEnginesMap[node.node_id].length === 0) {
        window.selectedOcrEnginesMap[node.node_id] = ['rapidocr'];
    }
    const selectedEngines = window.selectedOcrEnginesMap[node.node_id] || ['rapidocr'];
    const availableEngines = ['rapidocr', 'tesseract', 'easyocr'];
    const engineCheckboxesHtml = availableEngines.map(eng => {
        const checked = selectedEngines.includes(eng) ? 'checked' : '';
        const labelText = eng === 'rapidocr' ? 'RapidOCR (default)' : (eng === 'tesseract' ? 'Tesseract' : 'EasyOCR');
        const titleText = eng === 'rapidocr'
            ? 'RapidOCR: Built-in default OCR engine'
            : (eng === 'tesseract' ? 'Tesseract: Requires pytesseract and system tesseract binary' : 'EasyOCR: Requires easyocr package');
        return `
            <label style="display:inline-flex; align-items:center; gap:4px; font-size:11px; color:${p.textPrimary}; cursor:pointer;" title="${titleText}">
                <input type="checkbox" value="${eng}" class="ocr-engine-cb-${node.node_id}" ${checked} onchange="onOcrEngineToggle('${node.node_id}', '${eng}', this.checked)" />
                ${labelText}
            </label>
        `;
    }).join('');

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
            <div style="margin-top:8px; border-top:1px solid ${p.border}; padding-top:6px;">
                <div style="font-size:11px; font-weight:600; color:${p.textPrimary}; margin-bottom:4px;">OCR Engines (select 1 or more):</div>
                <div style="display:flex; flex-wrap:wrap; gap:10px;">
                    ${engineCheckboxesHtml}
                </div>
            </div>
            <div style="margin-top:8px; border-top:1px solid ${p.border}; padding-top:6px;">
                <label style="display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600; color:${p.textPrimary}; cursor:pointer;" title="Enable custom OCR engine flags and parameter overrides">
                    <input type="checkbox" id="chkOcrAdvanced_${node.node_id}" onchange="toggleOcrAdvancedMode('${node.node_id}', this.checked)" />
                    <span>Advanced mode (custom OCR flags)</span>
                </label>
                <div id="ocrAdvancedContainer_${node.node_id}" style="display:none; margin-top:6px;">
                    <div style="font-size:10px; color:${p.textMuted}; margin-bottom:2px;">Custom flags / parameters:</div>
                    <input type="text" id="inpOcrCustomFlags_${node.node_id}" placeholder="e.g. --psm 6 --oem 1, binarize=1, contrast=1.5" style="width:100%; box-sizing:border-box; font-family:monospace; font-size:11px; padding:3px 6px; border:1px solid ${p.border}; border-radius:3px; background:${p.bgDark}; color:${p.textPrimary};" />
                    <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;">
                        <button type="button" class="action-btn action-btn-decollide-sm" onclick="appendOcrCustomFlag('${node.node_id}', 'binarize=1')">+ Binarize</button>
                        <button type="button" class="action-btn action-btn-decollide-sm" onclick="appendOcrCustomFlag('${node.node_id}', '--psm 6')">+ PSM 6</button>
                        <button type="button" class="action-btn action-btn-decollide-sm" onclick="appendOcrCustomFlag('${node.node_id}', '--oem 1')">+ OEM 1</button>
                        <button type="button" class="action-btn action-btn-decollide-sm" onclick="appendOcrCustomFlag('${node.node_id}', 'invert=1')">+ Invert</button>
                        <button type="button" class="action-btn action-btn-decollide-sm" onclick="appendOcrCustomFlag('${node.node_id}', 'contrast=1.5')">+ Contrast</button>
                    </div>
                </div>
            </div>
            <div class="cutout-action-row" style="margin-top:8px; border-top:1px solid ${p.border}; padding-top:8px; display:flex; align-items:center; justify-content:space-between; gap:8px;">
                <span style="font-size:11px; color:${p.textMuted};">Refined extraction pass</span>
                <button class="action-btn action-btn-decollide-sm" id="btnCutoutOcr_${node.node_id}" style="background:${p.textPrimary}; color:${p.bgCard}; border-color:${p.textPrimary};" onclick="triggerCutoutSecondPass('${node.node_id}')" title="Send selected section cutout to backend OCR for targeted transcription">Parse section with OCR</button>
            </div>
            <div id="ocrPromptContainer_${node.node_id}" style="display:none; margin-top:10px;"></div>
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
    const { bbox, effectiveAngle, hasAngle, hasQuad, isIncorrect, noteVal, isCutoutUnskewed, violationsHtml, pageSeq } = options;
    const mergedBadgeHtml = renderMergedNodeBadgeComponent(node);
    const cutoutCardHtml = renderCutoutPreviewCardComponent(node, bbox, effectiveAngle, hasAngle, isCutoutUnskewed);
    const angleVal = (bbox.angle !== undefined && bbox.angle !== 0) ? bbox.angle : effectiveAngle;

    const isTable = node.type === 'table_grid' || (node.content && (node.content.rows || node.content.markdown_table || node.content.grid));
    let tableDimText = 'Table';
    if (isTable && node.content) {
        const rCount = node.content.num_rows || (Array.isArray(node.content.rows) ? node.content.rows.length : 0);
        const cCount = node.content.num_cols || (Array.isArray(node.content.columns) ? node.content.columns.length : 0);
        if (rCount > 0 && cCount > 0) {
            tableDimText = `${rCount} rows x ${cCount} cols`;
        } else if (rCount > 0) {
            tableDimText = `${rCount} rows`;
        }
    }

    const domNodeTypes = ['paragraph', 'heading', 'table_grid', 'figure', 'header_footer', 'multi_column_group'];
    if (node.type && !domNodeTypes.includes(node.type)) {
        domNodeTypes.push(node.type);
    }
    const typeOptionsHtml = domNodeTypes.map(t => {
        const sel = (t === node.type) ? ' selected' : '';
        return `<option value="${escapeHtml(t)}"${sel}>${escapeHtml(t)}</option>`;
    }).join('');

    return `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px;">
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <h4 style="margin-bottom:0;">Selected: <span style="font-family:monospace; font-weight:500;">${escapeHtml(node.node_id)}</span></h4>
                    <span class="badge-status" style="${inspectorBadgeStyle('neutral')}" title="Reading sequence position">#${pageSeq || 1}</span>
                    <select id="selectNodeType_${escapeHtml(node.node_id)}" class="type-filter" style="font-size:12px; padding:2px 6px;" onchange="onNodeTypeChange('${node.node_id}', this.value)" title="Change node semantic type">
                        ${typeOptionsHtml}
                    </select>
                </div>
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

            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:8px; margin-bottom:8px; padding:4px 8px; background:${p.bgCard}; border:1px solid ${p.border}; border-radius:4px;">
                <span style="font-size:11px; color:${p.textMuted};">Reading order:</span>
                <div style="display:flex; gap:4px;">
                    <button class="action-btn action-btn-decollide-sm" onclick="moveNodeOrderUp('${node.node_id}')" title="Move earlier in reading order">Move up</button>
                    <button class="action-btn action-btn-decollide-sm" onclick="moveNodeOrderDown('${node.node_id}')" title="Move later in reading order">Move down</button>
                </div>
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
            ${isTable ? `
            <div style="margin-top:10px;">
                <button class="action-btn action-btn-view-table" id="btnOpenTableModal_${escapeHtml(node.node_id)}" onclick="openTableModal('${escapeHtml(node.node_id)}')" title="View structured table content in modal">
                    View Table Content (${tableDimText})
                </button>
            </div>
            ` : ''}
            <div style="margin-top:10px;">
                ${isTable && typeof renderTableEditorComponent === 'function' ? renderTableEditorComponent(node) : ''}
                <label style="display:block; font-size:12px; color:${p.textPrimary}; font-weight:500; margin-bottom:2px;">Parsed text / correction note</label>
                <textarea class="note-area" placeholder="Parsed text or manual correction note…" oninput="updateCorrectionNote('${node.node_id}', this.value)">${escapeHtml(noteVal)}</textarea>
            </div>
            <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center; gap:8px;">
                <button class="action-btn action-btn-decollide-sm" style="color:${p.blue}; border-color:${p.blueBorder};" onclick="splitSelectedDOMNode('${node.node_id}')">[SPLIT] Split at Cursor</button>
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
    const { nodePage, isOnCurrentPage, isFixed, isIncorrect, hasActiveViol, hasSuppressedViol, displayText, pageSeq } = options;
    const pageBadgeVariant = isOnCurrentPage ? 'blueSolid' : 'muted';
    const isMerged = node.is_merged || (node.merged_from && node.merged_from.length > 0);
    const p = VIEWER_PALETTE;
    const orderBtnStyle = `font-size:10px; padding:1px 5px; border:1px solid ${p.border}; border-radius:3px; background:${p.bgLight}; color:${p.textPrimary}; cursor:pointer; line-height:1.2;`;

    return `
        <div class="node-header">
            <div style="display:flex; align-items:center; gap:6px;">
                <span class="badge-status" style="${inspectorBadgeStyle('neutral')}" title="Sequence #${pageSeq || 1}">#${pageSeq || 1}</span>
                <span class="node-id">${escapeHtml(node.node_id)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap; justify-content:flex-end;">
                <button type="button" class="btn-order-up" style="${orderBtnStyle}" onclick="event.stopPropagation(); moveNodeOrderUp('${node.node_id}')" title="Move earlier in reading order">Up</button>
                <button type="button" class="btn-order-down" style="${orderBtnStyle}" onclick="event.stopPropagation(); moveNodeOrderDown('${node.node_id}')" title="Move later in reading order">Dn</button>
                <span class="badge-status" style="${inspectorBadgeStyle(pageBadgeVariant)}">P${nodePage}</span>
                <span class="node-type type-${escapeHtml(node.type)}">${escapeHtml(node.type)}</span>
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

/**
 * Appends a preset flag token in the advanced custom OCR flags input.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {string} flagToken - Flag snippet to append if absent.
 */
function appendOcrCustomFlag(nodeId, flagToken) {
    const inp = document.getElementById(`inpOcrCustomFlags_${nodeId}`);
    if (!inp) return;
    const current = inp.value.trim();
    if (!current.includes(flagToken)) {
        inp.value = current ? `${current} ${flagToken}` : flagToken;
    }
}