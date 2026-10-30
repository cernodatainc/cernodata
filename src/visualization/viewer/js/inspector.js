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
            selectedNodeIds = (selectedNodeIds.length >= 2) ? [selectedNodeIds[1], nodeId] : [...selectedNodeIds, nodeId];
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

function selectAdjacentViolation(delta) {
    const viols = getViolationsList();
    const activeViols = viols.filter(v => !v.is_fixed && !isSuppressed(v));
    if (activeViols.length === 0) {
        if (typeof showStatusBanner === 'function') {
            showStatusBanner('No active quality violations found.', 'info', 2000);
        }
        return;
    }
    const currentIdx = activeViols.findIndex(v => v.node_id === selectedNodeId);
    const targetIdx = (currentIdx === -1)
        ? (delta > 0 ? 0 : activeViols.length - 1)
        : (currentIdx + delta + activeViols.length) % activeViols.length;
    const targetViol = activeViols[targetIdx];
    selectNode(targetViol.node_id, getViolationPage(targetViol));
    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Violation [${targetIdx + 1}/${activeViols.length}]: ${targetViol.rule_type || targetViol.type}`, 'info', 2000);
    }
}

/**
 * Selects the next active quality violation across document nodes.
 */
function selectNextViolation() {
    selectAdjacentViolation(1);
}

/**
 * Selects the previous active quality violation across document nodes.
 */
function selectPreviousViolation() {
    selectAdjacentViolation(-1);
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
        container.innerHTML = renderEmptySelectionComponent();
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
    const violationsHtml = renderNodeViolationsComponent(nodeViols, node, activePresetIndex);

    const pageNodes = (domData && domData.nodes) ? domData.nodes.filter(n => getNodePage(n) === currentPage) : [];
    const pageSeq = pageNodes.findIndex(n => n.node_id === node.node_id) + 1;

    container.innerHTML = renderSingleNodeEditorComponent(node, {
        bbox, effectiveAngle, hasAngle, hasQuad, isIncorrect, noteVal, isCutoutUnskewed, violationsHtml, pageSeq
    });
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
 * Updates a DOM node's semantic type, re-renders tree card and overlays,
 * and persists changes.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {string} newType - New DOMNodeType value.
 */
async function onNodeTypeChange(nodeId, newType) {
    if (!domData || !domData.nodes) return;
    const idx = domData.nodes.findIndex(n => n.node_id === nodeId);
    if (idx === -1) return;
    const node = domData.nodes[idx];
    if (node.type === newType) return;

    const origNode = JSON.parse(JSON.stringify(node));
    node.type = newType;
    const updatedNode = JSON.parse(JSON.stringify(node));

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'change_type',
            description: `Change type of '${nodeId}' to '${newType}'`,
            page: getNodePage(node),
            removed: [{ index: idx, node: origNode }],
            inserted: [{ index: idx, node: updatedNode }],
            beforeSelection: { selectedNodeId, selectedNodeIds: [...selectedNodeIds] },
            afterSelection: { selectedNodeId, selectedNodeIds: [...selectedNodeIds] },
            meta: { node_id: nodeId, old_type: origNode.type, new_type: newType }
        });
    }

    renderDOMTree();
    renderSVGOverlays();
    renderSelectedEditor();

    if (typeof saveAnnotations === 'function') {
        await saveAnnotations(true);
    }

    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Changed element '${nodeId}' type to '${newType}'. Persisted.`, 'success', 3000);
    }
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
    if (node.content) {
        node.content.raw_text = text;
    } else {
        node.content = { raw_text: text };
    }
    renderDOMTree();
}

/**
 * Deletes a DOM node, updates the DOM tree and SVG overlays, and persists changes.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
async function deleteDOMNode(nodeId) {
    if (!domData || !domData.nodes) return;
    const idx = domData.nodes.findIndex(n => n.node_id === nodeId);
    if (idx === -1) return;

    const origNode = JSON.parse(JSON.stringify(domData.nodes[idx]));
    const beforeSel = {
        selectedNodeId: (typeof selectedNodeId !== 'undefined' ? selectedNodeId : null),
        selectedNodeIds: (typeof selectedNodeIds !== 'undefined' ? [...selectedNodeIds] : [])
    };

    domData.nodes.splice(idx, 1);
    clearSelection();

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'delete_node',
            description: `Delete element '${nodeId}'`,
            page: getNodePage(origNode),
            removed: [{ index: idx, node: origNode }],
            inserted: [],
            beforeSelection: beforeSel,
            afterSelection: { selectedNodeId: null, selectedNodeIds: [] },
            meta: { deleted_node_id: nodeId }
        });
    }

    renderDOMTree();
    renderSVGOverlays();
    if (typeof saveAnnotations === 'function') {
        await saveAnnotations(true);
    }
    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Deleted element '${nodeId}'. Persisted.`, 'info', 3000);
    }
}

/**
 * Moves a DOM element earlier in the page reading sequence order.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function moveNodeOrderUp(nodeId) {
    if (!domData || !domData.nodes) return;
    const targetId = nodeId || selectedNodeId;
    if (!targetId) return;

    const pageNodes = domData.nodes.filter(n => getNodePage(n) === currentPage);
    const pageIdx = pageNodes.findIndex(n => n.node_id === targetId);
    if (pageIdx <= 0) {
        if (typeof showStatusBanner === 'function') {
            showStatusBanner('Element is already at the beginning of reading order.', 'info', 2000);
        }
        return;
    }

    const prevNode = pageNodes[pageIdx - 1];
    const gIdx1 = domData.nodes.findIndex(n => n.node_id === prevNode.node_id);
    const gIdx2 = domData.nodes.findIndex(n => n.node_id === targetId);
    const origN1 = JSON.parse(JSON.stringify(domData.nodes[gIdx1]));
    const origN2 = JSON.parse(JSON.stringify(domData.nodes[gIdx2]));

    const temp = domData.nodes[gIdx2];
    domData.nodes.splice(gIdx2, 1);
    domData.nodes.splice(gIdx1, 0, temp);

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'reorder_node',
            description: `Move reading order up: ${targetId}`,
            page: currentPage,
            removed: [{ index: Math.min(gIdx1, gIdx2), node: origN1 }, { index: Math.max(gIdx1, gIdx2), node: origN2 }],
            inserted: [{ index: Math.min(gIdx1, gIdx2), node: origN2 }, { index: Math.max(gIdx1, gIdx2), node: origN1 }],
            beforeSelection: { selectedNodeId, selectedNodeIds: [...selectedNodeIds] },
            afterSelection: { selectedNodeId: targetId, selectedNodeIds: [targetId] },
            meta: { node_id: targetId, direction: 'up' }
        });
    }

    renderDOMTree();
    renderSVGOverlays();
    renderSelectedEditor();
    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Moved '${targetId}' earlier in reading order.`, 'success', 2500);
    }
}

/**
 * Moves a DOM element later in the page reading sequence order.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function moveNodeOrderDown(nodeId) {
    if (!domData || !domData.nodes) return;
    const targetId = nodeId || selectedNodeId;
    if (!targetId) return;

    const pageNodes = domData.nodes.filter(n => getNodePage(n) === currentPage);
    const pageIdx = pageNodes.findIndex(n => n.node_id === targetId);
    if (pageIdx === -1 || pageIdx >= pageNodes.length - 1) {
        if (typeof showStatusBanner === 'function') {
            showStatusBanner('Element is already at the end of reading order.', 'info', 2000);
        }
        return;
    }

    const nextNode = pageNodes[pageIdx + 1];
    const gIdx1 = domData.nodes.findIndex(n => n.node_id === targetId);
    const gIdx2 = domData.nodes.findIndex(n => n.node_id === nextNode.node_id);
    const origN1 = JSON.parse(JSON.stringify(domData.nodes[gIdx1]));
    const origN2 = JSON.parse(JSON.stringify(domData.nodes[gIdx2]));

    const temp = domData.nodes[gIdx1];
    domData.nodes.splice(gIdx1, 1);
    domData.nodes.splice(gIdx2, 0, temp);

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'reorder_node',
            description: `Move reading order down: ${targetId}`,
            page: currentPage,
            removed: [{ index: Math.min(gIdx1, gIdx2), node: origN1 }, { index: Math.max(gIdx1, gIdx2), node: origN2 }],
            inserted: [{ index: Math.min(gIdx1, gIdx2), node: origN2 }, { index: Math.max(gIdx1, gIdx2), node: origN1 }],
            beforeSelection: { selectedNodeId, selectedNodeIds: [...selectedNodeIds] },
            afterSelection: { selectedNodeId: targetId, selectedNodeIds: [targetId] },
            meta: { node_id: targetId, direction: 'down' }
        });
    }

    renderDOMTree();
    renderSVGOverlays();
    renderSelectedEditor();
    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Moved '${targetId}' later in reading order.`, 'success', 2500);
    }
}

/**
 * Renders the hierarchical DOM element tree cards for the active page.
 */
function renderDOMTree() {
    // TODO(TASK-704): Add reading-order Move Up / Move Down controls and sequence badges to fix multi-column ordering.
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
        container.innerHTML = renderDOMTreeEmptyComponent(currentPage, domData.nodes.length);
        return;
    }

    const pageSeqMap = new Map();
    const currPageNodes = domData.nodes.filter(n => getNodePage(n) === currentPage);
    currPageNodes.forEach((n, idx) => { pageSeqMap.set(n.node_id, idx + 1); });

    nodesToDisplay.forEach(node => {
        const nodePage = getNodePage(node);
        const isOnCurrentPage = (nodePage === currentPage);
        const pageSeq = pageSeqMap.get(node.node_id) || 1;
        const viols = getViolationsList();
        const hasActiveViol = viols.some(v => v.node_id === node.node_id && !v.is_fixed && !isSuppressed(v));
        const hasSuppressedViol = viols.some(v => v.node_id === node.node_id && isSuppressed(v));
        const isIncorrect = !!node.is_incorrect_text;
        let displayText = (node.content && node.content.raw_text) ? node.content.raw_text : '';
        let isFixed = !!node.is_fixed;

        if (activePresetIndex === 1) {
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
        card.innerHTML = renderDOMTreeNodeCardComponent(node, {
            nodePage, isOnCurrentPage, isFixed, isIncorrect, hasActiveViol, hasSuppressedViol, displayText, pageSeq
        });
        container.appendChild(card);
    });
}

/** Formats and renders raw decision JSON payload into the decision log tab. */
function renderDecisionLog() {
    const el = document.getElementById('logContent');
    if (el) el.textContent = JSON.stringify(decisionData, null, 2);
}

/** Formats and renders raw DocumentPlan JSON payload into the plan tab. */
function renderPlanTab() {
    const el = document.getElementById('planContent');
    if (el) el.textContent = planData ? JSON.stringify(planData, null, 2) : 'No planner config associated with this run.';
}
