/**
 * src/visualization/viewer/js/overlay.js
 *
 * SVG canvas overlays, bounding box visualization, interactive dragging and resizing handles,
 * and custom section drawing tools.
 */

let isDrawSectionMode = false;
let drawStartPt = null;
let drawRectEl = null;

/**
 * Creates an SVG DOM element with namespace and applies attribute key-value pairs.
 *
 * @param {string} tag - SVG tag name (e.g. 'rect', 'polygon', 'text').
 * @param {Object.<string, string|number>} attrs - Attribute dictionary.
 * @returns {SVGElement} Instantiated SVG element.
 */
function createSvgElem(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
}

/**
 * Transforms screen mouse coordinates to SVG canvas internal coordinate system.
 *
 * @param {MouseEvent} evt - Mouse event with clientX and clientY.
 * @returns {SVGPoint} Scaled point in SVG coordinates.
 */
function getSvgCoordinates(evt) {
    const svg = document.getElementById('svgOverlay');
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
}

/**
 * Calculates 4 corner coordinates for a bounding box, applying angle rotation if present.
 *
 * @param {Object} bbox - Bounding box definition with x0, y0, x1, y1, angle, and optional quad.
 * @returns {Array<{x: number, y: number}>} Array of 4 corner points [TL, TR, BR, BL].
 */
function getBoxCorners(bbox) {
    if (bbox.quad && bbox.quad.length === 4) {
        return bbox.quad.map(pt => ({ x: pt[0], y: pt[1] }));
    }
    const x0 = bbox.x0, y0 = bbox.y0, x1 = bbox.x1, y1 = bbox.y1;
    const angle = bbox.angle || 0;
    const corners = [
        { x: x0, y: y0 }, // 0: Top-Left
        { x: x1, y: y0 }, // 1: Top-Right
        { x: x1, y: y1 }, // 2: Bottom-Right
        { x: x0, y: y1 }  // 3: Bottom-Left
    ];
    if (angle === 0) return corners;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rad = angle * Math.PI / 180;
    const cos = Math.cos(rad), sin = Math.sin(rad);
    return corners.map(pt => {
        const dx = pt.x - cx, dy = pt.y - cy;
        return {
            x: cx + dx * cos - dy * sin,
            y: cy + dx * sin + dy * cos
        };
    });
}

/**
 * Recalculates bounding box envelope coordinates and optional quad polygon from corner array.
 *
 * @param {Object} node - DOM node object whose bounding_box is being updated.
 * @param {Array<{x: number, y: number}>} corners - 4 modified corner points.
 */
function updateBboxFromCorners(node, corners) {
    node.bounding_box.quad = corners.map(pt => [roundCoord(pt.x), roundCoord(pt.y)]);
    node.bounding_box.x0 = roundCoord(Math.min(...corners.map(p => p.x)));
    node.bounding_box.y0 = roundCoord(Math.min(...corners.map(p => p.y)));
    node.bounding_box.x1 = roundCoord(Math.max(...corners.map(p => p.x)));
    node.bounding_box.y1 = roundCoord(Math.max(...corners.map(p => p.y)));
}

/**
 * Toggles interactive rectangle drawing mode for creating new user-defined sections.
 */
function toggleDrawSectionMode() {
    isDrawSectionMode = !isDrawSectionMode;
    const btn = document.getElementById('btnDrawSection');
    const visualPane = document.getElementById('visualPane');
    const banner = document.getElementById('statusBanner');
    if (isDrawSectionMode) {
        if (btn) btn.classList.add('active');
        if (visualPane) visualPane.style.cursor = 'crosshair';
        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            banner.textContent = '[MODE] Click and drag on page to draw and select a new section.';
        }
    } else {
        if (btn) btn.classList.remove('active');
        if (visualPane) visualPane.style.cursor = 'default';
        if (banner) banner.style.display = 'none';
        if (drawRectEl && drawRectEl.parentNode) {
            drawRectEl.parentNode.removeChild(drawRectEl);
            drawRectEl = null;
        }
        drawStartPt = null;
    }
}

/**
 * Renders all SVG bounding box polygons, selection resize handles, and violation callout badges.
 */
function renderSVGOverlays() {
    const svg = document.getElementById('svgOverlay');
    if (!svg) return;
    svg.innerHTML = '';
    svg.onclick = (e) => {
        if (!isDrawSectionMode && e.target === svg) {
            clearSelection();
        }
    };
    svg.onmousedown = (e) => {
        if (isDrawSectionMode && (e.target === svg || e.target.id === 'pageImg')) {
            e.preventDefault();
            e.stopPropagation();
            drawStartPt = getSvgCoordinates(e);
            drawRectEl = createSvgElem('rect', {
                x: drawStartPt.x,
                y: drawStartPt.y,
                width: 0,
                height: 0,
                fill: 'rgba(16, 185, 129, 0.2)',
                stroke: '#10B981',
                'stroke-width': '2',
                'stroke-dasharray': '4 2',
                id: 'drawSectionPreview'
            });
            svg.appendChild(drawRectEl);
        }
    };
    const showBbox = document.getElementById('toggleBbox') ? document.getElementById('toggleBbox').checked : true;
    const showViol = document.getElementById('toggleViolations') ? document.getElementById('toggleViolations').checked : true;
    const filterType = document.getElementById('typeFilter') ? document.getElementById('typeFilter').value : 'ALL';

    domData.nodes.forEach(node => {
        const nodePage = node.global_page_index || 1;
        if (nodePage !== currentPage) return;
        if (filterType !== 'ALL' && node.type !== filterType) return;
        const bbox = node.bounding_box;
        const corners = getBoxCorners(bbox);
        const viols = getViolationsList();
        const nodeViols = viols.filter(v => v.node_id === node.node_id && (v.global_page_index || 1) === currentPage);
        const hasUnfixedViol = nodeViols.some(v => !v.is_fixed && !isSuppressed(v));
        const hasViol = hasUnfixedViol && !appliedCorrections && activePresetIndex === 0;
        const isSelected = selectedNodeIds.includes(node.node_id);
        const isIncorrect = !!node.is_incorrect_text;

        if (showBbox) {
            let classNames = ['node-bbox'];
            if (isSelected) classNames.push('highlighted');
            if (hasViol) classNames.push('violation');
            if (isIncorrect) classNames.push('incorrect-text');

            const pointsStr = corners.map(p => `${roundCoord(p.x)},${roundCoord(p.y)}`).join(' ');
            const poly = createSvgElem('polygon', {
                points: pointsStr,
                class: classNames.join(' '),
                id: `svg-${node.node_id}`
            });
            poly.onmousedown = (e) => onPolygonMouseDown(e, node.node_id);
            poly.onclick = (e) => { e.stopPropagation(); handleNodeClick(e, node.node_id); };
            svg.appendChild(poly);

            if (isSelected) {
                renderQuadResizeHandles(svg, node, corners);
            }

            if (isIncorrect) {
                const tagW = 120, tagH = 16;
                const tagBg = createSvgElem('rect', {
                    x: bbox.x0, y: Math.max(0, bbox.y0 - tagH - 2),
                    width: tagW, height: tagH,
                    fill: '#D97706', stroke: '#FDE68A', 'stroke-width': '1',
                    rx: '3'
                });
                const tagTxt = createSvgElem('text', {
                    x: bbox.x0 + 4, y: Math.max(11, bbox.y0 - 4),
                    fill: '#FFF', 'font-size': '9px', 'font-weight': '700',
                    'pointer-events': 'none'
                });
                tagTxt.textContent = '[!] INCORRECT TEXT';
                svg.appendChild(tagBg);
                svg.appendChild(tagTxt);
            }
        }

        if ((showViol || isSelected) && nodeViols.length > 0) {
            nodeViols.forEach((viol, vIdx) => {
                const g = createSvgElem('g', {});
                const isFixed = !!viol.is_fixed || !!node.is_fixed || appliedCorrections || activePresetIndex === 1;
                const labelText = isFixed
                    ? `[FIXED] '${viol.detected_snippet}' -> '${viol.suggested_correction || ''}'`
                    : `[!] VIOLATION: '${viol.detected_snippet}' -> '${viol.suggested_correction || ''}'`;

                const yOffset = vIdx * 20;
                const badgeBg = createSvgElem('rect', {
                    x: bbox.x0, y: Math.max(0, bbox.y0 - 18 - yOffset),
                    width: Math.min(360, labelText.length * 6.8), height: 18,
                    class: 'viol-callout',
                    style: isFixed ? 'fill: #00E676; stroke: #00B0FF;' : ''
                });
                const badgeTxt = createSvgElem('text', {
                    x: bbox.x0 + 4, y: Math.max(12, bbox.y0 - 4 - yOffset), class: 'viol-text',
                    style: isFixed ? 'fill: #000;' : ''
                });
                badgeTxt.textContent = labelText;
                g.appendChild(badgeBg);
                g.appendChild(badgeTxt);
                svg.appendChild(g);
            });
        }
    });
}

/**
 * Convenience alias for rendering quadrilateral resizing handles on selected node.
 *
 * @param {SVGElement} svg - Target SVG overlay canvas.
 * @param {Object} node - DOM node object.
 * @param {Array<{x: number, y: number}>|null} corners - Optional corner array.
 */
function renderResizeHandles(svg, node, corners) {
    return renderQuadResizeHandles(svg, node, corners || getBoxCorners(node.bounding_box));
}

/**
 * Renders corner handles (crosshair) and edge midpoint handles (ew/ns-resize) on bounding box.
 *
 * @param {SVGElement} svg - Target SVG overlay canvas.
 * @param {Object} node - DOM node object.
 * @param {Array<{x: number, y: number}>} corners - 4 corner coordinates.
 */
function renderQuadResizeHandles(svg, node, corners) {
    const hs = 9;

    const cornerDefs = [
        { cornerIndex: 0, pt: corners[0], cursor: 'crosshair', title: 'Top-Left Corner' },
        { cornerIndex: 1, pt: corners[1], cursor: 'crosshair', title: 'Top-Right Corner' },
        { cornerIndex: 2, pt: corners[2], cursor: 'crosshair', title: 'Bottom-Right Corner' },
        { cornerIndex: 3, pt: corners[3], cursor: 'crosshair', title: 'Bottom-Left Corner' }
    ];

    cornerDefs.forEach(cd => {
        const hRect = createSvgElem('rect', {
            x: cd.pt.x - hs / 2, y: cd.pt.y - hs / 2, width: hs, height: hs,
            class: 'resize-handle corner',
            style: `cursor: ${cd.cursor};`
        });
        hRect.onmousedown = (e) => onCornerHandleMouseDown(e, cd.cornerIndex, node.node_id);
        svg.appendChild(hRect);
    });

    const edgeDefs = [
        { edge: 0, p1: corners[0], p2: corners[1], cursor: 'ns-resize' },
        { edge: 1, p1: corners[1], p2: corners[2], cursor: 'ew-resize' },
        { edge: 2, p1: corners[2], p2: corners[3], cursor: 'ns-resize' },
        { edge: 3, p1: corners[3], p2: corners[0], cursor: 'ew-resize' }
    ];

    edgeDefs.forEach(ed => {
        const mx = (ed.p1.x + ed.p2.x) / 2;
        const my = (ed.p1.y + ed.p2.y) / 2;
        const hRect = createSvgElem('rect', {
            x: mx - (hs - 2) / 2, y: my - (hs - 2) / 2, width: hs - 2, height: hs - 2,
            class: 'resize-handle',
            style: `cursor: ${ed.cursor};`
        });
        hRect.onmousedown = (e) => onEdgeHandleMouseDown(e, ed.edge, node.node_id);
        svg.appendChild(hRect);
    });
}

/**
 * Initiates dragging interaction on a specific corner handle.
 *
 * @param {MouseEvent} evt - MouseDown event.
 * @param {number} cornerIndex - Corner index (0..3).
 * @param {string} nodeId - Identifier of target DOM node.
 */
function onCornerHandleMouseDown(evt, cornerIndex, nodeId) {
    evt.stopPropagation();
    evt.preventDefault();
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const svgPt = getSvgCoordinates(evt);
    const corners = getBoxCorners(node.bounding_box);
    activeDrag = {
        action: 'corner',
        cornerIndex: cornerIndex,
        nodeId: nodeId,
        startSvgX: svgPt.x,
        startSvgY: svgPt.y,
        initialCorners: corners.map(p => ({ ...p }))
    };
}

/**
 * Initiates dragging interaction on a specific edge midpoint handle.
 *
 * @param {MouseEvent} evt - MouseDown event.
 * @param {number} edgeIndex - Edge index (0..3).
 * @param {string} nodeId - Identifier of target DOM node.
 */
function onEdgeHandleMouseDown(evt, edgeIndex, nodeId) {
    evt.stopPropagation();
    evt.preventDefault();
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const svgPt = getSvgCoordinates(evt);
    const corners = getBoxCorners(node.bounding_box);
    activeDrag = {
        action: 'edge',
        edgeIndex: edgeIndex,
        nodeId: nodeId,
        startSvgX: svgPt.x,
        startSvgY: svgPt.y,
        initialCorners: corners.map(p => ({ ...p }))
    };
}

/**
 * Initiates dragging interaction to translate/move an entire bounding box.
 *
 * @param {MouseEvent} evt - MouseDown event.
 * @param {string} nodeId - Identifier of target DOM node.
 */
function onPolygonMouseDown(evt, nodeId) {
    if (!selectedNodeIds.includes(nodeId)) return;
    evt.stopPropagation();
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const svgPt = getSvgCoordinates(evt);
    const corners = getBoxCorners(node.bounding_box);
    activeDrag = {
        action: 'move',
        nodeId: nodeId,
        startSvgX: svgPt.x,
        startSvgY: svgPt.y,
        initialCorners: corners.map(p => ({ ...p }))
    };
}
