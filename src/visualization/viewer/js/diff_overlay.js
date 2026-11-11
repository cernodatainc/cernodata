/**
 * src/visualization/viewer/js/diff_overlay.js
 *
 * Dual-run visual diff highlighting (TASK-711):
 * Compares the active DOM against the raw/baseline run and overlays
 * added, removed, and modified bounding boxes on the SVG canvas.
 */

let isDiffOverlayActive = false;
let customDiffBaselineNodes = null;

/**
 * Sets an explicit baseline node list (e.g. from another preset run) for visual diffing.
 *
 * @param {Array<Object>|null} nodes - Baseline DOM nodes, or null to compare against rawDomData.
 */
function setDiffOverlayBaselineNodes(nodes) {
    customDiffBaselineNodes = Array.isArray(nodes) ? JSON.parse(JSON.stringify(nodes)) : null;
    if (isDiffOverlayActive && typeof renderSVGOverlays === 'function') {
        renderSVGOverlays();
    }
}

/**
 * Checks whether two bounding boxes or node contents differ meaningfully.
 *
 * @param {Object} baseNode - Baseline DOM node.
 * @param {Object} currNode - Current DOM node.
 * @returns {boolean} True if coordinates, type, or text changed.
 */
function _hasNodeChanged(baseNode, currNode) {
    if (!baseNode || !currNode) return true;
    const b1 = baseNode.bounding_box || {};
    const b2 = currNode.bounding_box || {};
    const eps = 1.0;
    const bboxMoved = Math.abs((b1.x0 || 0) - (b2.x0 || 0)) > eps
        || Math.abs((b1.y0 || 0) - (b2.y0 || 0)) > eps
        || Math.abs((b1.x1 || 0) - (b2.x1 || 0)) > eps
        || Math.abs((b1.y1 || 0) - (b2.y1 || 0)) > eps
        || Math.abs((b1.angle || 0) - (b2.angle || 0)) > 0.2;
    if (bboxMoved) return true;
    if (baseNode.type !== currNode.type) return true;
    const t1 = ((baseNode.content && baseNode.content.raw_text) || '').trim();
    const t2 = (currNode.corrected_text || (currNode.content && currNode.content.raw_text) || '').trim();
    return t1 !== t2 || !!currNode.is_corrected || !!currNode.is_fixed;
}

/**
 * Computes added, removed, and modified node classification on a target page.
 *
 * @param {number} [pageNum=currentPage] - 1-indexed page number.
 * @returns {{ added: Set<string>, modified: Map<string, Object>, removed: Array<Object>, counts: Object }}
 */
function computeVisualDiffForPage(pageNum) {
    const pNum = pageNum !== undefined ? pageNum : (typeof currentPage !== 'undefined' ? currentPage : 1);
    const currNodes = ((typeof domData !== 'undefined' && domData && Array.isArray(domData.nodes)) ? domData.nodes : [])
        .filter(n => (typeof getNodePage === 'function' ? getNodePage(n) : 1) === pNum);

    const rawNodesSource = customDiffBaselineNodes
        || ((typeof rawDomData !== 'undefined' && rawDomData && Array.isArray(rawDomData.nodes)) ? rawDomData.nodes : []);
    const baseNodes = rawNodesSource.filter(n => (typeof getNodePage === 'function' ? getNodePage(n) : 1) === pNum);

    const baseById = new Map(baseNodes.map(n => [n.node_id, n]));
    const currById = new Map(currNodes.map(n => [n.node_id, n]));

    const added = new Set();
    const modified = new Map();
    const removed = [];

    for (const cNode of currNodes) {
        const bNode = baseById.get(cNode.node_id);
        if (!bNode) {
            added.add(cNode.node_id);
        } else if (_hasNodeChanged(bNode, cNode)) {
            modified.set(cNode.node_id, bNode);
        }
    }

    for (const bNode of baseNodes) {
        if (!currById.has(bNode.node_id)) {
            removed.push(bNode);
        }
    }

    return {
        added,
        modified,
        removed,
        counts: {
            added: added.size,
            modified: modified.size,
            removed: removed.length
        }
    };
}

/**
 * Toggles dual-run visual diff overlay mode on the SVG canvas.
 */
function toggleDiffOverlay() {
    isDiffOverlayActive = !isDiffOverlayActive;
    const btn = document.getElementById('btnDiffOverlay');
    if (btn) {
        btn.classList.toggle('active', isDiffOverlayActive);
    }
    if (typeof renderSVGOverlays === 'function') {
        renderSVGOverlays();
    }
    if (typeof showStatusBanner === 'function') {
        if (isDiffOverlayActive) {
            const diff = computeVisualDiffForPage();
            showStatusBanner(
                `Diff Overlay active: ${diff.counts.added} added, ${diff.counts.removed} removed, ${diff.counts.modified} modified.`,
                'info',
                3500
            );
        } else {
            showStatusBanner('Diff Overlay disabled.', 'info', 2000);
        }
    }
}

/**
 * Renders baseline ghost bounding boxes (removed + prior positions of modified nodes) into SVG.
 *
 * @param {SVGElement} svg - Target SVG overlay canvas.
 * @param {{ added: Set<string>, modified: Map<string, Object>, removed: Array<Object> }} diffInfo - Computed diff state.
 */
function renderDiffOverlayBaselineGhosts(svg, diffInfo) {
    if (!svg || !diffInfo || !isDiffOverlayActive) return;

    const drawGhost = (node, labelText, strokeColor, fillColor) => {
        if (!node || !node.bounding_box || typeof getBoxCorners !== 'function' || typeof createSvgElem !== 'function') return;
        const corners = getBoxCorners(node.bounding_box);
        const pts = corners.map(pt => `${roundCoord(pt.x)},${roundCoord(pt.y)}`).join(' ');
        svg.appendChild(createSvgElem('polygon', {
            points: pts,
            class: 'node-bbox diff-ghost-box',
            stroke: strokeColor,
            fill: fillColor,
            'stroke-width': '2',
            'stroke-dasharray': '5 3',
            'pointer-events': 'none'
        }));
        const bx = Number(node.bounding_box.x0 || 0);
        const by = Math.max(12, Number(node.bounding_box.y0 || 0) - 4);
        const txt = createSvgElem('text', {
            x: bx,
            y: by,
            fill: strokeColor,
            'font-size': '10px',
            'font-weight': '700',
            'pointer-events': 'none'
        });
        txt.textContent = labelText;
        svg.appendChild(txt);
    };

    diffInfo.removed.forEach(node => {
        drawGhost(node, `REMOVED: ${node.node_id}`, '#B42318', 'rgba(240, 68, 56, 0.14)');
    });
    diffInfo.modified.forEach(prevNode => {
        drawGhost(prevNode, `PREV: ${prevNode.node_id}`, '#B54708', 'rgba(247, 144, 9, 0.08)');
    });
}
