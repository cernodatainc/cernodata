/**
 * src/visualization/viewer/js/inspector.js
 *
 * Inspector panel: DOM element list tree, single-node inspector editor,
 * manual coordinate adjustment, and decision log & plan tabs.
 */

/**
 * Handles element selection click on tree card or overlay polygon.
 * Supports Shift+click for pairwise multi-selection.
 *
 * @param {MouseEvent|null} evt - Triggering click event.
 * @param {string|null} nodeId - Identifier of target DOM node.
 */
function handleNodeClick(evt, nodeId) {
    if (!nodeId) {
        clearSelection();
        return;
    }

    const targetNode = domData.nodes.find(n => n.node_id === nodeId);
    if (targetNode && targetNode.global_page_index && targetNode.global_page_index !== currentPage) {
        switchPage(targetNode.global_page_index);
    }

    if (evt && evt.shiftKey) {
        if (selectedNodeIds.includes(nodeId)) {
            selectedNodeIds = selectedNodeIds.filter(id => id !== nodeId);
        } else {
            if (selectedNodeIds.length >= 2) {
                selectedNodeIds = [selectedNodeIds[1], nodeId];
            } else {
                selectedNodeIds.push(nodeId);
            }
        }
    } else {
        selectedNodeIds = [nodeId];
    }

    selectedNodeId = selectedNodeIds.length > 0 ? selectedNodeIds[selectedNodeIds.length - 1] : null;

    document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
    selectedNodeIds.forEach(id => {
        const c = document.getElementById(`card-${id}`);
        if (c) c.classList.add('selected');
    });

    if (selectedNodeId) {
        const card = document.getElementById(`card-${selectedNodeId}`);
        if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    renderSelectedEditor();
    renderSVGOverlays();
}

/**
 * Programmatically selects a node and navigates to its page if necessary.
 *
 * @param {string} nodeId - Identifier of target DOM node.
 * @param {number|null} [pageIndex=null] - Target 1-indexed page index.
 */
function selectNode(nodeId, pageIndex = null) {
    if (pageIndex && pageIndex !== currentPage) {
        switchPage(pageIndex);
    }
    const evt = window.event || null;
    handleNodeClick(evt, nodeId);
}

/**
 * Clears current node selection state and hides active editor pane.
 */
function clearSelection() {
    selectedNodeIds = [];
    selectedNodeId = null;
    document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
    renderSelectedEditor();
    renderSVGOverlays();
}

/**
 * Renders the right-hand inspector pane for the currently selected node(s).
 */
function renderSelectedEditor() {
    const container = document.getElementById('selectedEditorContainer');
    if (!container) return;

    if (selectedNodeIds.length === 0) {
        container.innerHTML = `
            <div class="editor-box" style="border-style:dashed;">
                <div style="font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:4px;">No Box Selected</div>
                <div style="font-size:11px; color:var(--text-muted); line-height:1.4;">
                    Click a bounding box to inspect/edit coordinates. <strong>Shift+Click</strong> two boxes to compare and auto-decollide them.
                </div>
                <button class="btn-decollide" onclick="decollideCurrentPage()" style="margin-top:8px;">[AUTO-DECOLLIDE] Decollide All Page Boxes</button>
            </div>
        `;
        return;
    }

    if (selectedNodeIds.length === 2) {
        renderTwoNodeDecollideEditor(container);
        return;
    }

    const node = domData.nodes.find(n => n.node_id === selectedNodeIds[0]);
    if (!node) {
        container.innerHTML = '';
        return;
    }
    const bbox = node.bounding_box;
    const isIncorrect = !!node.is_incorrect_text;
    const hasQuad = !!bbox.quad;
    const effectiveAngle = getEffectiveNodeAngle(node.node_id, bbox);
    const hasAngle = (effectiveAngle !== 0);

    if (node.user_correction_note === undefined || node.user_correction_note === null || node.user_correction_note === '') {
        node.user_correction_note = (node.content && node.content.raw_text) ? node.content.raw_text : '';
    }
    const noteVal = node.user_correction_note;

    const viols = getViolationsList();
    const nodeViols = viols.filter(v => v.node_id === node.node_id);
    let violationsHtml = '';
    if (nodeViols.length > 0) {
        violationsHtml = `
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

    container.innerHTML = `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Selected: ${node.node_id} (${node.type})</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="clearSelection()">Close</button>
            </div>
            ${(node.is_merged || (node.merged_from && node.merged_from.length > 0)) ? `
            <div style="background: rgba(37, 99, 235, 0.15); border: 1px solid #3B82F6; border-radius: 4px; padding: 6px 8px; margin-bottom: 8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:11px; font-weight:600; color:#93C5FD;">[MERGE] Merged Element (${(node.merged_from || []).length} elements combined)</span>
                    <button class="action-btn" style="background:#DC2626; color:#FFF; font-size:10px; padding:2px 8px;" onclick="unmergeDOMNode('${node.node_id}')">[UNMERGE] Undo Merge</button>
                </div>
                <div style="font-size:10px; color:#BFDBFE; margin-top:2px;">
                    Original: ${(node.merged_from || []).map(m => escapeHtml(m.node_id)).join(' + ')}
                </div>
            </div>
            ` : ''}
            <div class="coord-grid">
                <div class="coord-field"><label>X0</label><input type="number" step="0.5" id="inpX0" value="${bbox.x0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y0</label><input type="number" step="0.5" id="inpY0" value="${bbox.y0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>X1</label><input type="number" step="0.5" id="inpX1" value="${bbox.x1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y1</label><input type="number" step="0.5" id="inpY1" value="${bbox.y1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Angle</label><input type="number" step="0.1" id="inpAngle" value="${bbox.angle !== undefined && bbox.angle !== 0 ? bbox.angle : effectiveAngle}" onchange="onManualCoordChange()"></div>
            </div>

            <div class="cutout-preview-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:10px; font-weight:700; color:#93C5FD; text-transform:uppercase;">Page Cutout View</span>
                    <div style="display:flex; align-items:center; gap:6px;">
                        ${hasAngle ? `<span class="badge-status lang" style="font-size:9px; padding:1px 5px;">Skew: ${effectiveAngle}°</span>` : ''}
                        <span style="font-size:10px; color:var(--text-muted);">${Math.round(bbox.x1 - bbox.x0)} x ${Math.round(bbox.y1 - bbox.y0)} pt</span>
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
    renderCutoutPreview(node.node_id, node.bounding_box, 'cutoutPreviewImg_' + node.node_id, isCutoutUnskewed);
}

/**
 * Resets a custom quadrilateral polygon to an axis-aligned rectangle.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function resetQuadToRect(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    node.bounding_box.quad = null;
    renderSelectedEditor();
    renderSVGOverlays();
}

/**
 * Updates node bounding box when coordinate number inputs are manually edited.
 */
function onManualCoordChange() {
    if (!selectedNodeId) return;
    const node = domData.nodes.find(n => n.node_id === selectedNodeId);
    if (!node) return;

    const x0 = parseFloat(document.getElementById('inpX0').value) || 0;
    const y0 = parseFloat(document.getElementById('inpY0').value) || 0;
    const x1 = parseFloat(document.getElementById('inpX1').value) || (x0 + 10);
    const y1 = parseFloat(document.getElementById('inpY1').value) || (y0 + 10);
    const inpAngle = document.getElementById('inpAngle');

    node.bounding_box.x0 = roundCoord(Math.min(x0, x1 - 5));
    node.bounding_box.y0 = roundCoord(Math.min(y0, y1 - 5));
    node.bounding_box.x1 = roundCoord(Math.max(x1, x0 + 5));
    node.bounding_box.y1 = roundCoord(Math.max(y1, y0 + 5));
    if (inpAngle) {
        node.bounding_box.angle = roundCoord(parseFloat(inpAngle.value) || 0);
    }
    node.bounding_box.quad = null;

    renderCutoutPreview(node.node_id, node.bounding_box, 'cutoutPreviewImg_' + node.node_id, isCutoutUnskewed);
    renderSVGOverlays();
}

/**
 * Toggles user flag marking a node as containing incorrect parsed text.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function toggleIncorrectText(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    node.is_incorrect_text = !node.is_incorrect_text;
    if (node.is_incorrect_text && (!node.user_correction_note)) {
        node.user_correction_note = (node.content && node.content.raw_text) ? node.content.raw_text : '';
    }
    renderSelectedEditor();
    renderDOMTree();
    renderSVGOverlays();
}

/**
 * Updates manual user correction note text for a node.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {string} text - User entered correction text.
 */
function updateCorrectionNote(nodeId, text) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    node.user_correction_note = text;
}

/**
 * Renders the hierarchical DOM element tree cards for the active page.
 */
function renderDOMTree() {
    const container = document.getElementById('domListContainer');
    if (!container) return;
    container.innerHTML = '';

    const nodesToDisplay = showAllDomNodes
        ? domData.nodes
        : domData.nodes.filter(node => getNodePage(node) === currentPage);

    const countEl = document.getElementById('domCount');
    if (countEl) countEl.textContent = nodesToDisplay.length;

    const labelEl = document.getElementById('domTabLabel');
    if (labelEl) {
        labelEl.textContent = showAllDomNodes ? 'DOM Page [ALL]' : 'DOM Page';
    }

    if (nodesToDisplay.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); text-align: center; margin-top: 20px; font-size: 12px; padding: 10px;">
            No DOM elements found on Page ${currentPage}.<br>
            <span style="font-size:10px; color: #9CA3AF;">(Shift-click "DOM Page" tab to show all ${domData.nodes.length} elements across all pages)</span>
        </div>`;
        return;
    }

    nodesToDisplay.forEach(node => {
        const nodePage = getNodePage(node);
        const isOnCurrentPage = (nodePage === currentPage);
        const viols = getViolationsList();
        const hasActiveViol = viols.some(v => v.node_id === node.node_id && !v.is_fixed && !isSuppressed(v));
        const hasSuppressedViol = viols.some(v => v.node_id === node.node_id && isSuppressed(v));
        const isIncorrect = !!node.is_incorrect_text;
        let displayText = (node.content && node.content.raw_text) ? node.content.raw_text : '';
        let isFixed = !!node.is_fixed;

        if (appliedCorrections || activePresetIndex === 1) {
            const corrected = applyCorrectionsToNodeText(displayText);
            if (corrected !== displayText) {
                displayText = corrected;
                isFixed = true;
            }
        }

        const isSelected = selectedNodeIds.includes(node.node_id);
        const card = document.createElement('div');
        card.className = `node-card ${hasActiveViol && !isFixed ? 'has-violation' : ''} ${isIncorrect ? 'is-incorrect' : ''} ${isSelected ? 'selected' : ''}`;
        card.id = `card-${node.node_id}`;
        card.onclick = (e) => handleNodeClick(e, node.node_id);
        card.innerHTML = `
            <div class="node-header">
                <span class="node-id">${escapeHtml(node.node_id)}</span>
                <div style="display:flex; align-items:center; gap:4px;">
                    <span class="badge-status" style="font-size:9px; background:${isOnCurrentPage ? '#2563EB' : '#374151'}; color:#FFF;">P${nodePage}</span>
                    <span class="node-type">${escapeHtml(node.type)}</span>
                    ${isFixed ? '<span class="node-corrected-badge">FIXED</span>' : ''}
                    ${node.is_merged || (node.merged_from && node.merged_from.length > 0) ? '<span class="badge-status" style="font-size:9px; background:#1E40AF; color:#DBEAFE;">MERGED</span>' : ''}
                    ${!hasActiveViol && hasSuppressedViol ? '<span class="badge-status" style="font-size:9px; background:#065F46; color:#A7F3D0;">ACCEPTED</span>' : ''}
                    ${isIncorrect ? '<span class="node-incorrect-badge">INCORRECT TEXT</span>' : ''}
                </div>
            </div>
            <div class="node-text">${escapeHtml(displayText)}</div>
        `;
        container.appendChild(card);
    });
}

/**
 * Formats and renders raw decision JSON payload into the decision log tab.
 */
function renderDecisionLog() {
    const el = document.getElementById('logContent');
    if (el) {
        el.textContent = JSON.stringify(decisionData, null, 2);
    }
}

/**
 * Formats and renders raw DocumentPlan JSON payload into the plan tab.
 */
function renderPlanTab() {
    const el = document.getElementById('planContent');
    if (el) {
        el.textContent = planData ? JSON.stringify(planData, null, 2) : "No planner config associated with this run.";
    }
}
