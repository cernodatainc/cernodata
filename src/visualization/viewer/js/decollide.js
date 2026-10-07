/**
 * src/visualization/viewer/js/decollide.js
 *
 * Pairwise bounding box decollision, multi-node overlap inspection,
 * and element merging for textual and non-textual DOM elements.
 */

/**
 * Renders pairwise collision inspector and merge configuration editor for 2 selected nodes.
 *
 * @param {HTMLElement} container - Target container DOM element for the editor.
 */
function renderTwoNodeDecollideEditor(container) {
    const node1 = domData.nodes.find(n => n.node_id === selectedNodeIds[0]);
    const node2 = domData.nodes.find(n => n.node_id === selectedNodeIds[1]);
    if (!node1 || !node2) {
        container.innerHTML = '';
        return;
    }

    let upper = node1;
    let lower = node2;
    if (upper.bounding_box.y0 > lower.bounding_box.y0 ||
       (Math.abs(upper.bounding_box.y0 - lower.bounding_box.y0) < 5 && upper.bounding_box.x0 > lower.bounding_box.x0)) {
        upper = node2;
        lower = node1;
    }

    const bUpper = upper.bounding_box;
    const bLower = lower.bounding_box;

    const hOverlap = Math.max(0, Math.min(bUpper.x1, bLower.x1) - Math.max(bUpper.x0, bLower.x0));
    const vOverlap = Math.max(0, bUpper.y1 - bLower.y0);
    const hasCollision = (vOverlap > 0 && hOverlap > 0);
    const gap = bLower.y0 - bUpper.y1;

    const statusBadge = renderCollisionStatusBadgeComponent(hasCollision, vOverlap, hOverlap, gap);

    const upperText = (upper.content && upper.content.raw_text) ? upper.content.raw_text.trim() : '';
    const lowerText = (lower.content && lower.content.raw_text) ? lower.content.raw_text.trim() : '';
    const isUpperText = isTextualNode(upper);
    const isLowerText = isTextualNode(lower);
    const bothTextual = isUpperText && isLowerText;
    const sameType = (upper.type === lower.type);

    const isSameLine = Math.abs(bUpper.y0 - bLower.y0) < 6;
    const defaultMergedText = (upperText && lowerText)
        ? (upperText + (isSameLine ? ' ' : '\n') + lowerText)
        : (upperText || lowerText);

    let mergeHtml = '';
    if (sameType && bothTextual) {
        mergeHtml = renderMergeTextualEditorComponent(upper, lower, defaultMergedText);
    } else if (!sameType) {
        mergeHtml = renderMergeDifferentTypesEditorComponent(upper, lower, defaultMergedText);
    } else {
        mergeHtml = renderMergeNonTextualEditorComponent(upper, lower);
    }

    container.innerHTML = renderTwoNodeDecollideCardComponent(
        upper,
        lower,
        bUpper,
        bLower,
        statusBadge,
        mergeHtml,
        hasCollision
    );

    renderCutoutPreview(upper.node_id, upper.bounding_box, 'cutoutPreviewImg_' + upper.node_id);
    renderCutoutPreview(lower.node_id, lower.bounding_box, 'cutoutPreviewImg_' + lower.node_id);
}

/**
 * Synchronizes merged text preview textarea when merge content handling dropdown changes.
 */
function onMergeConfigChanged() {
    const actionEl = document.getElementById('mergeContentAction');
    const textEl = document.getElementById('mergeMergedText');
    if (!actionEl || !textEl || selectedNodeIds.length !== 2) return;

    const n1 = domData.nodes.find(n => n.node_id === selectedNodeIds[0]);
    const n2 = domData.nodes.find(n => n.node_id === selectedNodeIds[1]);
    if (!n1 || !n2) return;

    let upper = (n1.bounding_box.y0 <= n2.bounding_box.y0) ? n1 : n2;
    let lower = (n1.bounding_box.y0 <= n2.bounding_box.y0) ? n2 : n1;

    const tUpper = (upper.content && upper.content.raw_text) ? upper.content.raw_text.trim() : '';
    const tLower = (lower.content && lower.content.raw_text) ? lower.content.raw_text.trim() : '';

    if (actionEl.value === 'keep_upper') {
        textEl.value = tUpper;
    } else if (actionEl.value === 'keep_lower') {
        textEl.value = tLower;
    } else if (actionEl.value === 'concat') {
        const isSameLine = Math.abs(upper.bounding_box.y0 - lower.bounding_box.y0) < 6;
        textEl.value = (tUpper && tLower) ? (tUpper + (isSameLine ? ' ' : '\n') + tLower) : (tUpper || tLower);
    }
}

/**
 * Handles UI trigger to merge the 2 currently selected DOM nodes.
 */
async function executeMergeElements() {
    if (selectedNodeIds.length !== 2) return;
    const n1 = selectedNodeIds[0];
    const n2 = selectedNodeIds[1];

    const typeEl = document.getElementById('mergeTargetType');
    const actionEl = document.getElementById('mergeContentAction');
    const textEl = document.getElementById('mergeMergedText');

    const targetType = typeEl ? typeEl.value : null;
    const contentAction = actionEl ? actionEl.value : 'concat';
    const mergedText = textEl ? textEl.value : null;

    await mergeDOMNodes(n1, n2, { targetType, contentAction, mergedText });
}

/**
 * Merges two DOM nodes into a single consolidated element, recalculating bounding envelope
 * and preserving audit history for undo support.
 *
 * @param {string} nodeId1 - First node identifier.
 * @param {string} nodeId2 - Second node identifier.
 * @param {Object} [options={}] - Options specifying targetType, contentAction, and custom mergedText.
 * @returns {Promise<Object|null>} Consolidated upper node object or null on failure.
 */
async function mergeDOMNodes(nodeId1, nodeId2, options = {}) {
    const n1 = domData.nodes.find(n => n.node_id === nodeId1);
    const n2 = domData.nodes.find(n => n.node_id === nodeId2);
    if (!n1 || !n2) return null;

    let upper = n1;
    let lower = n2;
    if (upper.bounding_box.y0 > lower.bounding_box.y0 ||
       (Math.abs(upper.bounding_box.y0 - lower.bounding_box.y0) < 5 && upper.bounding_box.x0 > lower.bounding_box.x0)) {
        upper = n2;
        lower = n1;
    }

    const bUpper = upper.bounding_box;
    const bLower = lower.bounding_box;

    const targetType = options.targetType || (upper.type === lower.type ? upper.type : upper.type);

    let mergedText = '';
    const upperText = (upper.content && upper.content.raw_text) ? upper.content.raw_text.trim() : '';
    const lowerText = (lower.content && lower.content.raw_text) ? lower.content.raw_text.trim() : '';

    if (options.mergedText !== undefined && options.mergedText !== null) {
        mergedText = options.mergedText;
    } else if (options.contentAction === 'keep_upper') {
        mergedText = upperText;
    } else if (options.contentAction === 'keep_lower') {
        mergedText = lowerText;
    } else {
        const isSameLine = Math.abs(bUpper.y0 - bLower.y0) < 6;
        if (upperText && lowerText) {
            mergedText = upperText + (isSameLine ? ' ' : '\n') + lowerText;
        } else {
            mergedText = upperText || lowerText;
        }
    }

    const mergedBbox = {
        x0: roundCoord(Math.min(bUpper.x0, bLower.x0)),
        y0: roundCoord(Math.min(bUpper.y0, bLower.y0)),
        x1: roundCoord(Math.max(bUpper.x1, bLower.x1)),
        y1: roundCoord(Math.max(bUpper.y1, bLower.y1)),
        angle: 0.0,
        quad: null
    };

    const origUpper = JSON.parse(JSON.stringify(upper));
    const origLower = JSON.parse(JSON.stringify(lower));

    const mergedContent = Object.assign({}, upper.content, lower.content, { raw_text: mergedText });

    upper.type = targetType;
    upper.bounding_box = mergedBbox;
    upper.content = mergedContent;
    upper.user_correction_note = mergedText;
    upper.is_merged = true;
    upper.merged_from = [origUpper, origLower];
    upper.merged_at = new Date().toISOString();

    domData.nodes = domData.nodes.filter(n => n.node_id !== lower.node_id);

    const viols = getViolationsList();
    viols.forEach(v => {
        if (v.node_id === lower.node_id) {
            v.node_id = upper.node_id;
        }
    });

    selectedNodeIds = [upper.node_id];
    selectedNodeId = upper.node_id;

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }

    renderDOMTree();
    renderViolationsList();
    renderSelectedEditor();
    renderSVGOverlays();

    if (typeof saveAnnotations === 'function') {
        await saveAnnotations(true);
    }

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[OK] Merged '${upper.node_id}' and '${lower.node_id}' into '${upper.node_id}' (${targetType}). Persisted.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }

    return upper;
}

/**
 * Reverts a previous element merge, restoring the original component nodes
 * and re-associating their violations.
 *
 * @param {string} nodeId - Consolidated node ID to unmerge.
 * @returns {Promise<Array<Object>|null>} Array of restored component nodes or null on failure.
 */
async function unmergeDOMNode(nodeId) {
    if (!domData || !domData.nodes) return null;
    const target = domData.nodes.find(n => n.node_id === nodeId);
    if (!target || !target.merged_from || !Array.isArray(target.merged_from) || target.merged_from.length === 0) {
        return null;
    }

    const restoredNodes = JSON.parse(JSON.stringify(target.merged_from));
    const targetIdx = domData.nodes.findIndex(n => n.node_id === nodeId);
    if (targetIdx === -1) return null;

    domData.nodes.splice(targetIdx, 1, ...restoredNodes);

    const viols = getViolationsList();
    restoredNodes.forEach(rn => {
        if (rn.violations && Array.isArray(rn.violations)) {
            rn.violations.forEach(rv => {
                const found = viols.find(v => v.violation_id === rv.violation_id);
                if (found) {
                    found.node_id = rn.node_id;
                }
            });
        }
    });

    selectedNodeIds = restoredNodes.map(n => n.node_id);
    selectedNodeId = restoredNodes[0] ? restoredNodes[0].node_id : null;

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }

    renderDOMTree();
    renderViolationsList();
    renderSelectedEditor();
    renderSVGOverlays();

    if (typeof saveAnnotations === 'function') {
        await saveAnnotations(true);
    }

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        const restoredNames = restoredNodes.map(n => `'${n.node_id}'`).join(' and ');
        banner.textContent = `[OK] Undid merge. Restored original elements ${restoredNames}. Persisted.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }

    return restoredNodes;
}

/**
 * Resolves vertical overlap between the 2 currently selected bounding boxes
 * by adjusting their top and bottom boundaries to a shared split line.
 */
function decollideSelectedPair() {
    if (selectedNodeIds.length !== 2) return;
    const node1 = domData.nodes.find(n => n.node_id === selectedNodeIds[0]);
    const node2 = domData.nodes.find(n => n.node_id === selectedNodeIds[1]);
    if (!node1 || !node2) return;

    let upper = node1;
    let lower = node2;
    if (upper.bounding_box.y0 > lower.bounding_box.y0) {
        upper = node2;
        lower = node1;
    }

    const bUpper = upper.bounding_box;
    const bLower = lower.bounding_box;

    const midY = roundCoord((bUpper.y1 + bLower.y0) / 2);
    const gap = 0.5;

    bUpper.y1 = roundCoord(Math.max(bUpper.y0 + 2, midY - gap / 2));
    bLower.y0 = roundCoord(Math.min(bLower.y1 - 2, midY + gap / 2));
    bUpper.quad = null;
    bLower.quad = null;

    renderSVGOverlays();
    renderDOMTree();
    renderSelectedEditor();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[OK] De-collided '${upper.node_id}' and '${lower.node_id}' at Y = ${midY}. Click '[SAVE] Save Annotations' to persist.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

/**
 * Sweeps all bounding boxes on the target page and automatically decollides
 * vertically overlapping adjacent pairs.
 *
 * @param {number|null} [pageIndex=null] - 1-indexed target page number or null for currentPage.
 * @returns {number} Count of decollided box pairs.
 */
function decollideCurrentPage(pageIndex = null) {
    const targetPage = (typeof pageIndex === 'number' && pageIndex > 0) ? pageIndex : currentPage;
    const pageNodes = domData.nodes.filter(n => (n.global_page_index === targetPage || n.temp_slice_index === targetPage));
    const sorted = [...pageNodes].sort((a, b) => a.bounding_box.y0 - b.bounding_box.y0);
    let decollidedCount = 0;

    for (let i = 0; i < sorted.length; i++) {
        for (let j = i + 1; j < sorted.length; j++) {
            const upper = sorted[i];
            const lower = sorted[j];

            if (lower.bounding_box.y0 >= upper.bounding_box.y1 + 30) {
                break;
            }

            const bUpper = upper.bounding_box;
            const bLower = lower.bounding_box;

            const xOverlap = Math.min(bUpper.x1, bLower.x1) - Math.max(bUpper.x0, bLower.x0);
            const minW = Math.min(bUpper.x1 - bUpper.x0, bLower.x1 - bLower.x0);

            if (xOverlap > 0 && (xOverlap / Math.max(1, minW)) >= 0.25) {
                const vOverlap = bUpper.y1 - bLower.y0;
                const upperH = bUpper.y1 - bUpper.y0;
                const lowerH = bLower.y1 - bLower.y0;

                if (vOverlap > 0 && vOverlap <= Math.max(upperH, lowerH) * 0.5) {
                    const midY = roundCoord((bUpper.y1 + bLower.y0) / 2);
                    const gap = 0.5;
                    bUpper.y1 = roundCoord(Math.max(bUpper.y0 + 2, midY - gap / 2));
                    bLower.y0 = roundCoord(Math.min(bLower.y1 - 2, midY + gap / 2));
                    bUpper.quad = null;
                    bLower.quad = null;
                    decollidedCount++;
                }
            }
        }
    }

    renderSVGOverlays();
    renderDOMTree();
    renderSelectedEditor();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        if (decollidedCount > 0) {
            banner.textContent = `[OK] Auto-decollided ${decollidedCount} overlapping box pair(s) on Page ${targetPage}. Click '[SAVE] Save Annotations' to persist.`;
        } else {
            banner.textContent = `[INFO] No skew-overlapping box pairs detected on Page ${targetPage}.`;
        }
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
    return decollidedCount;
}
