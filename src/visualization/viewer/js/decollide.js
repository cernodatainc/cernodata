/**
 * src/visualization/viewer/js/decollide.js
 *
 * Pairwise bounding box decollision, multi-node overlap inspection,
 * and element merging for textual and non-textual DOM elements.
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

    const statusBadge = hasCollision
        ? `<div class="collision-status-badge overlap">
                <span>[!] Skew Overlap: ${vOverlap.toFixed(2)} pt</span>
                <span>Horiz: ${hOverlap.toFixed(2)} pt</span>
           </div>`
        : `<div class="collision-status-badge clean">
                <span>[OK] No Overlap Detected</span>
                <span>Gap: ${(bLower.y0 - bUpper.y1).toFixed(2)} pt</span>
           </div>`;

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
        mergeHtml = `
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
    } else if (!sameType) {
        mergeHtml = `
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
    } else {
        mergeHtml = `
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

    container.innerHTML = `
        <div class="multi-editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Shift-Selection: 2 Boxes</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="clearSelection()">Clear</button>
            </div>
            ${statusBadge}
            <button class="btn-decollide" onclick="decollideSelectedPair()" ${!hasCollision ? 'style="background:#2563EB;"' : ''}>
                ${hasCollision ? '[AUTO-DECOLLIDE] De-collide Selected Boxes' : 'Evenly Space / Align Boundary'}
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
                <div class="pair-node-text">${escapeHtml(upper.content.raw_text || '(no text)')}</div>
            </div>
            <div class="pair-node-item" style="border-left: 3px solid #A78BFA;">
                <div class="pair-node-header">
                    <span>Lower: ${escapeHtml(lower.node_id)} (${escapeHtml(lower.type)})</span>
                    <span class="pair-node-coords">Y: [${bLower.y0}, ${bLower.y1}]</span>
                </div>
                <div class="cutout-display-box" style="margin-bottom:4px;">
                    <img id="cutoutPreviewImg_${lower.node_id}" class="cutout-img" alt="Lower Cutout" />
                </div>
                <div class="pair-node-text">${escapeHtml(lower.content.raw_text || '(no text)')}</div>
            </div>
            <div style="margin-top:8px; font-size:10px; color:var(--text-muted);">
                Boundary split calculates the median inter-line position and adjusts top/bottom edges cleanly without manual adjustment.
            </div>
        </div>
    `;
    renderCutoutPreview(upper.node_id, upper.bounding_box, 'cutoutPreviewImg_' + upper.node_id);
    renderCutoutPreview(lower.node_id, lower.bounding_box, 'cutoutPreviewImg_' + lower.node_id);
}

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

function executeMergeElements() {
    if (selectedNodeIds.length !== 2) return;
    const n1 = selectedNodeIds[0];
    const n2 = selectedNodeIds[1];

    const typeEl = document.getElementById('mergeTargetType');
    const actionEl = document.getElementById('mergeContentAction');
    const textEl = document.getElementById('mergeMergedText');

    const targetType = typeEl ? typeEl.value : null;
    const contentAction = actionEl ? actionEl.value : 'concat';
    const mergedText = textEl ? textEl.value : null;

    mergeDOMNodes(n1, n2, { targetType, contentAction, mergedText });
}

function mergeDOMNodes(nodeId1, nodeId2, options = {}) {
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

    const mergedContent = Object.assign({}, upper.content, lower.content, { raw_text: mergedText });

    upper.type = targetType;
    upper.bounding_box = mergedBbox;
    upper.content = mergedContent;
    upper.user_correction_note = mergedText;

    domData.nodes = domData.nodes.filter(n => n.node_id !== lower.node_id);

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    viols.forEach(v => {
        if (v.node_id === lower.node_id) {
            v.node_id = upper.node_id;
        }
    });

    selectedNodeIds = [upper.node_id];
    selectedNodeId = upper.node_id;

    renderDOMTree();
    renderViolationsList();
    renderSelectedEditor();
    renderSVGOverlays();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[OK] Merged '${upper.node_id}' and '${lower.node_id}' into '${upper.node_id}' (${targetType}). Click '[SAVE] Save Annotations' to persist.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }

    return upper;
}

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
