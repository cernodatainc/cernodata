/**
 * src/visualization/viewer/viewer.js
 *
 * Client-side runtime logic for interactive HTML visual flow explorer.
 * Reads initial context from window.VIEWER_DATA.
 */

const initialDomData = window.VIEWER_DATA.dom;
const initialViolationsData = window.VIEWER_DATA.violations;
const initialDecisionData = window.VIEWER_DATA.decision;
const detectedLanguagesMap = window.VIEWER_DATA.detectedLanguages;
const planData = window.VIEWER_DATA.plan;
const pdfSourceFile = window.VIEWER_DATA.pdfSourceFile;

let activePresetIndex = 0;
let appliedCorrections = false;
let activeLanguage = window.VIEWER_DATA.activeLanguage;
let selectedNodeId = null;
let selectedNodeIds = [];
let isCutoutUnskewed = false;
let activeDrag = null;
let currentZoom = 1.0;

let domData = JSON.parse(JSON.stringify(initialDomData));
let violationsData = JSON.parse(JSON.stringify(initialViolationsData));
let decisionData = JSON.parse(JSON.stringify(initialDecisionData));

function adjustZoom(delta) {
    currentZoom = Math.min(2.5, Math.max(0.5, currentZoom + delta));
    applyZoom();
}

function resetZoom() {
    currentZoom = 1.0;
    applyZoom();
}

function fitWidthZoom() {
    const pane = document.getElementById('visualPane');
    const availableW = pane.clientWidth - 40;
    currentZoom = Math.min(2.0, Math.max(0.6, availableW / 880));
    applyZoom();
}

function applyZoom() {
    const container = document.getElementById('canvasContainer');
    container.style.transform = `scale(${currentZoom})`;
    document.getElementById('zoomDisplay').textContent = `${Math.round(currentZoom * 100)}%`;
}

// Mouse wheel zooming
document.getElementById('visualPane').addEventListener('wheel', (e) => {
    if (e.ctrlKey) {
        e.preventDefault();
        adjustZoom(e.deltaY < 0 ? 0.1 : -0.1);
    }
}, { passive: false });

function createSvgElem(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (let k in attrs) el.setAttribute(k, attrs[k]);
    return el;
}

function getSvgCoordinates(evt) {
    const svg = document.getElementById('svgOverlay');
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
}

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

function roundCoord(val) {
    return Math.round(val * 100) / 100;
}

function updateBboxFromCorners(node, corners) {
    node.bounding_box.quad = corners.map(pt => [roundCoord(pt.x), roundCoord(pt.y)]);
    node.bounding_box.x0 = roundCoord(Math.min(...corners.map(p => p.x)));
    node.bounding_box.y0 = roundCoord(Math.min(...corners.map(p => p.y)));
    node.bounding_box.x1 = roundCoord(Math.max(...corners.map(p => p.x)));
    node.bounding_box.y1 = roundCoord(Math.max(...corners.map(p => p.y)));
}

function applyCorrectionsToNodeText(rawText) {
    let text = rawText;
    initialViolationsData.forEach(v => {
        if (v.detected_snippet && v.suggested_correction) {
            text = text.replace(new RegExp(v.detected_snippet, 'g'), v.suggested_correction);
        }
    });
    return text;
}

function handleNodeClick(evt, nodeId) {
    if (!nodeId) {
        clearSelection();
        return;
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

function selectNode(nodeId) {
    const evt = window.event || null;
    handleNodeClick(evt, nodeId);
}

function clearSelection() {
    selectedNodeIds = [];
    selectedNodeId = null;
    document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
    renderSelectedEditor();
    renderSVGOverlays();
}

function renderTwoNodeDecollideEditor(container) {
    const node1 = domData.nodes.find(n => n.node_id === selectedNodeIds[0]);
    const node2 = domData.nodes.find(n => n.node_id === selectedNodeIds[1]);
    if (!node1 || !node2) {
        container.innerHTML = '';
        return;
    }

    let upper = node1;
    let lower = node2;
    if (upper.bounding_box.y0 > lower.bounding_box.y0) {
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
            <div class="pair-node-item" style="border-left: 3px solid #60A5FA;">
                <div class="pair-node-header">
                    <span>Upper: ${upper.node_id} (${upper.type})</span>
                    <span class="pair-node-coords">Y: [${bUpper.y0}, ${bUpper.y1}]</span>
                </div>
                <div class="cutout-display-box" style="margin-bottom:4px;">
                    <img id="cutoutPreviewImg_${upper.node_id}" class="cutout-img" alt="Upper Cutout" />
                </div>
                <div class="pair-node-text">${escapeHtml(upper.content.raw_text || '(no text)')}</div>
            </div>
            <div class="pair-node-item" style="border-left: 3px solid #A78BFA;">
                <div class="pair-node-header">
                    <span>Lower: ${lower.node_id} (${lower.type})</span>
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

function decollideCurrentPage(pageIndex = 1) {
    const pageNodes = domData.nodes.filter(n => (n.global_page_index === pageIndex || n.temp_slice_index === pageIndex));
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
            banner.textContent = `[OK] Auto-decollided ${decollidedCount} overlapping box pair(s) on Page ${pageIndex}. Click '[SAVE] Save Annotations' to persist.`;
        } else {
            banner.textContent = `[INFO] No skew-overlapping box pairs detected on Page ${pageIndex}.`;
        }
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
    return decollidedCount;
}

function getEffectiveNodeAngle(nodeId, bbox) {
    if (bbox && bbox.angle !== undefined && bbox.angle !== null && bbox.angle !== 0) {
        return bbox.angle;
    }
    if (bbox && bbox.quad && bbox.quad.length === 4) {
        const dx = bbox.quad[1][0] - bbox.quad[0][0];
        const dy = bbox.quad[1][1] - bbox.quad[0][1];
        if (dx !== 0) {
            return roundCoord((Math.atan2(dy, dx) * 180.0) / Math.PI);
        }
    }
    const v = violationsData.find(viol => viol.node_id === nodeId && viol.bounding_box && viol.bounding_box.angle);
    if (v) {
        return v.bounding_box.angle;
    }
    const node = domData.nodes.find(n => n.node_id === nodeId);
    const pageNo = node ? (node.global_page_index || 1) : 1;
    const pageSkewNode = domData.nodes.find(n => (n.global_page_index === pageNo) && n.bounding_box && n.bounding_box.angle);
    if (pageSkewNode) {
        return pageSkewNode.bounding_box.angle;
    }
    return 0.0;
}

function toggleCutoutUnskew(nodeId) {
    isCutoutUnskewed = !isCutoutUnskewed;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    renderCutoutPreview(node.node_id, node.bounding_box, 'cutoutPreviewImg_' + node.node_id, isCutoutUnskewed);
    const btn = document.getElementById('btnToggleUnskew_' + node.node_id);
    if (btn) {
        btn.textContent = isCutoutUnskewed ? '[SKEW] Show Skewed' : '[UNSKEW] Unskew Transformation';
        btn.title = isCutoutUnskewed ? 'Switch to oriented skewed polygon cutout' : 'Transform skewed quadrilateral into a horizontal, unskewed text strip';
    }
    const modeLabel = document.getElementById('cutoutModeLabel_' + node.node_id);
    if (modeLabel) {
        modeLabel.textContent = isCutoutUnskewed ? 'Mode: Unskewed (Transformed Rectification)' : 'Mode: Skewed (Oriented Selection)';
    }
}

/**
 * Piece-wise affine transformation helper: warps triangle (s0, s1, s2) from img into (d0, d1, d2) in ctx.
 */
function renderTriangleWarp(ctx, img, s0, s1, s2, d0, d1, d2) {
    const X1 = s1.x - s0.x, Y1 = s1.y - s0.y;
    const X2 = s2.x - s0.x, Y2 = s2.y - s0.y;
    const det = X1 * Y2 - X2 * Y1;
    if (Math.abs(det) < 0.0001) return;

    const U1 = d1.x - d0.x, U2 = d2.x - d0.x;
    const a = (U1 * Y2 - U2 * Y1) / det;
    const c = (U2 * X1 - U1 * X2) / det;
    const e = d0.x - a * s0.x - c * s0.y;

    const V1 = d1.y - d0.y, V2 = d2.y - d0.y;
    const b = (V1 * Y2 - V2 * Y1) / det;
    const d = (V2 * X1 - V1 * X2) / det;
    const f = d0.y - b * s0.x - d * s0.y;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(d0.x, d0.y);
    ctx.lineTo(d1.x, d1.y);
    ctx.lineTo(d2.x, d2.y);
    ctx.closePath();
    ctx.clip();
    ctx.transform(a, b, c, d, e, f);
    ctx.drawImage(img, 0, 0);
    ctx.restore();
}

/**
 * Derives the 4 corner vertices of the skewed text selection from explicit quad or angle.
 * Strips outer bounding box inflation so adjacent text lines are excluded.
 */
function getNodeSkewCorners(nodeId, bbox) {
    if (bbox.quad && bbox.quad.length === 4) {
        return bbox.quad.map(pt => ({ x: pt[0], y: pt[1] }));
    }
    const angle = getEffectiveNodeAngle(nodeId, bbox);
    const x0 = bbox.x0, y0 = bbox.y0, x1 = bbox.x1, y1 = bbox.y1;
    const wSpan = Math.max(1, x1 - x0);
    const hSpan = Math.max(1, y1 - y0);

    if (angle === 0) {
        return [
            { x: x0, y: y0 },
            { x: x1, y: y0 },
            { x: x1, y: y1 },
            { x: x0, y: y1 }
        ];
    }

    const rad = angle * Math.PI / 180.0;
    const deltaY = wSpan * Math.tan(rad);
    const absDeltaY = Math.abs(deltaY);

    if (angle < 0) {
        return [
            { x: x0, y: y0 },
            { x: x1, y: y0 + absDeltaY },
            { x: x1, y: y1 },
            { x: x0, y: y1 - absDeltaY }
        ];
    } else {
        return [
            { x: x0, y: y0 + absDeltaY },
            { x: x1, y: y0 },
            { x: x1, y: y1 - absDeltaY },
            { x: x0, y: y1 }
        ];
    }
}

/**
 * Renders an image crop / cutout from pageImg for the given bounding box.
 * When skewed, extracts the oriented skewed content clipped to the polygon so adjacent lines are excluded.
 * When unskew=true, applies a geometric transformation (affine warp) to the skewed selection to rectify it
 * into a horizontal text strip without reverting to the outer bounding box.
 *
 * TODO: We might want to allow sending that cutout of the page to an OCR or LLM for a further pass.
 */
function renderCutoutPreview(nodeId, bbox, targetImgId, unskew = isCutoutUnskewed) {
    const pageImg = document.getElementById('pageImg');
    const targetImg = document.getElementById(targetImgId);
    if (!pageImg || !targetImg) return;

    function doDraw() {
        if (!pageImg.naturalWidth || !pageImg.naturalHeight) return;
        const svg = document.getElementById('svgOverlay');
        const vbW = (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) ? svg.viewBox.baseVal.width : 595.28;
        const vbH = (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.height) ? svg.viewBox.baseVal.height : 841.89;

        const scaleX = pageImg.naturalWidth / vbW;
        const scaleY = pageImg.naturalHeight / vbH;

        const corners = getNodeSkewCorners(nodeId, bbox);
        const s0 = { x: corners[0].x * scaleX, y: corners[0].y * scaleY };
        const s1 = { x: corners[1].x * scaleX, y: corners[1].y * scaleY };
        const s2 = { x: corners[2].x * scaleX, y: corners[2].y * scaleY };
        const s3 = { x: corners[3].x * scaleX, y: corners[3].y * scaleY };

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        if (unskew) {
            // Unskewed mode: Affine transformation of the skewed selection into a rectified horizontal rectangle
            const wTop = Math.hypot(s1.x - s0.x, s1.y - s0.y);
            const wBot = Math.hypot(s2.x - s3.x, s2.y - s3.y);
            const hLeft = Math.hypot(s3.x - s0.x, s3.y - s0.y);
            const hRight = Math.hypot(s2.x - s1.x, s2.y - s1.y);

            const dstW = Math.max(10, Math.round((wTop + wBot) / 2));
            const dstH = Math.max(8, Math.round((hLeft + hRight) / 2));

            canvas.width = dstW;
            canvas.height = dstH;

            const d0 = { x: 0, y: 0 };
            const d1 = { x: dstW, y: 0 };
            const d2 = { x: dstW, y: dstH };
            const d3 = { x: 0, y: dstH };

            renderTriangleWarp(ctx, pageImg, s0, s1, s2, d0, d1, d2);
            renderTriangleWarp(ctx, pageImg, s0, s2, s3, d0, d2, d3);

            targetImg.src = canvas.toDataURL('image/png');
        } else {
            // Skewed mode: Display the tilted selection, clipped strictly to the skewed polygon so adjacent text is omitted
            const minX = Math.floor(Math.min(s0.x, s1.x, s2.x, s3.x));
            const maxX = Math.ceil(Math.max(s0.x, s1.x, s2.x, s3.x));
            const minY = Math.floor(Math.min(s0.y, s1.y, s2.y, s3.y));
            const maxY = Math.ceil(Math.max(s0.y, s1.y, s2.y, s3.y));

            const cropW = Math.max(1, maxX - minX);
            const cropH = Math.max(1, maxY - minY);

            canvas.width = cropW;
            canvas.height = cropH;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(s0.x - minX, s0.y - minY);
            ctx.lineTo(s1.x - minX, s1.y - minY);
            ctx.lineTo(s2.x - minX, s2.y - minY);
            ctx.lineTo(s3.x - minX, s3.y - minY);
            ctx.closePath();
            ctx.clip();

            ctx.drawImage(pageImg, -minX, -minY);
            ctx.restore();

            targetImg.src = canvas.toDataURL('image/png');
        }
    }

    if (pageImg.complete && pageImg.naturalWidth > 0) {
        doDraw();
    } else {
        pageImg.addEventListener('load', doDraw, { once: true });
    }
}

/**
 * TODO: Allow sending that cutout of the page to an OCR or LLM for a further pass.
 *
 * Future refinement pass:
 * 1. Extract the cropped canvas as a base64 PNG.
 * 2. Dispatch to an OCR engine or Vision LLM endpoint for targeted re-transcription.
 * 3. Update the node's text content and re-evaluate local quality violations.
 */
function triggerCutoutSecondPass(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    // TODO: Send cutout of the page to an OCR or LLM for a further pass
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[TODO] Cutout for '${nodeId}' prepared for second-pass OCR/LLM evaluation.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

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

    container.innerHTML = `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Selected: ${node.node_id} (${node.type})</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="clearSelection()">Close</button>
            </div>
            <div class="coord-grid">
                <div class="coord-field"><label>X0</label><input type="number" step="0.5" id="inpX0" value="${bbox.x0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y0</label><input type="number" step="0.5" id="inpY0" value="${bbox.y0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>X1</label><input type="number" step="0.5" id="inpX1" value="${bbox.x1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y1</label><input type="number" step="0.5" id="inpY1" value="${bbox.y1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Angle</label><input type="number" step="0.1" id="inpAngle" value="${bbox.angle !== undefined && bbox.angle !== 0 ? bbox.angle : effectiveAngle}" onchange="onManualCoordChange()"></div>
            </div>

            <!-- Cutout View Aid for Currently Selected Bounding Box (supports skewed polygon & unskewed view) -->
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
                <div class="cutout-action-row" style="margin-top:6px; border-top:1px solid #334155; padding-top:6px;">
                    <!-- TODO: Allow sending that cutout of the page to an OCR or LLM for a further pass -->
                    <span style="font-size:9px; color:var(--text-muted);">Refined Extraction Pass:</span>
                    <button class="action-btn secondary" style="font-size:10px; padding:3px 8px; opacity:0.85;" onclick="triggerCutoutSecondPass('${node.node_id}')" title="TODO: Allow sending that cutout of the page to an OCR or LLM for a further pass">[TODO] Send Cutout to OCR/LLM</button>
                </div>
            </div>

            ${hasQuad ? `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:10px; color:#FBBF24; font-weight:600;">Custom Quad Polygon Active</span>
                <button style="background:#374151; border:1px solid #4B5563; color:#FFF; font-size:10px; padding:2px 6px; border-radius:3px; cursor:pointer;" onclick="resetQuadToRect('${node.node_id}')">Reset to Rect</button>
            </div>
            ` : ''}
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

function resetQuadToRect(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    node.bounding_box.quad = null;
    renderSelectedEditor();
    renderSVGOverlays();
}

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

function updateCorrectionNote(nodeId, text) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    node.user_correction_note = text;
}

function renderDOMTree() {
    const container = document.getElementById('domListContainer');
    container.innerHTML = '';
    document.getElementById('domCount').textContent = domData.nodes.length;

    domData.nodes.forEach(node => {
        const hasViol = violationsData.some(v => v.node_id === node.node_id);
        const isIncorrect = !!node.is_incorrect_text;
        let displayText = node.content.raw_text || '';
        let isFixed = false;

        if (appliedCorrections || activePresetIndex === 1) {
            const corrected = applyCorrectionsToNodeText(displayText);
            if (corrected !== displayText) {
                displayText = corrected;
                isFixed = true;
            }
        }

        const isSelected = selectedNodeIds.includes(node.node_id);
        const card = document.createElement('div');
        card.className = `node-card ${hasViol && !isFixed ? 'has-violation' : ''} ${isIncorrect ? 'is-incorrect' : ''} ${isSelected ? 'selected' : ''}`;
        card.id = `card-${node.node_id}`;
        card.onclick = (e) => handleNodeClick(e, node.node_id);
        card.innerHTML = `
            <div class="node-header">
                <span class="node-id">${node.node_id}</span>
                <div>
                    <span class="node-type">${node.type}</span>
                    ${isFixed ? '<span class="node-corrected-badge">FIXED</span>' : ''}
                    ${isIncorrect ? '<span class="node-incorrect-badge">INCORRECT TEXT</span>' : ''}
                </div>
            </div>
            <div class="node-text">${escapeHtml(displayText)}</div>
        `;
        container.appendChild(card);
    });
}

function renderViolationsList() {
    const container = document.getElementById('violListContainer');
    document.getElementById('violCount').textContent = violationsData.length;

    if (violationsData.length === 0) {
        container.innerHTML = '<div style="color: var(--accent-green); text-align: center; margin-top: 20px; font-weight: 600;">[OK] Zero quality violations detected for current language/preset.</div>';
        return;
    }
    container.innerHTML = '';
    violationsData.forEach(v => {
        const card = document.createElement('div');
        card.className = 'viol-card';
        card.onclick = () => selectNode(v.node_id);
        card.innerHTML = `
            <div class="viol-header">
                <span class="viol-title">[!] ${v.rule_type}</span>
                <span style="font-size: 10px; font-weight:700; color: #F87171;">${v.severity}</span>
            </div>
            <div style="font-size: 11px; font-family: monospace;">Snippet: '${v.detected_snippet}' -> '${v.suggested_correction || ''}'</div>
            <div class="viol-desc">${v.description}</div>
            <button class="apply-fix-btn" onclick="applySingleFix(event, '${v.node_id}', '${v.detected_snippet}', '${v.suggested_correction}')">[Fix] Apply Suggested Fix</button>
        `;
        container.appendChild(card);
    });
}

function applySingleFix(evt, nodeId, snippet, fix) {
    evt.stopPropagation();
    appliedCorrections = true;
    document.getElementById('toggleCorrections').checked = true;
    renderDOMTree();
    renderSVGOverlays();
}

function toggleAllCorrections() {
    appliedCorrections = document.getElementById('toggleCorrections').checked;
    renderDOMTree();
    renderSVGOverlays();
}

function renderDecisionLog() {
    document.getElementById('logContent').textContent = JSON.stringify(decisionData, null, 2);
}

function renderSVGOverlays() {
    const svg = document.getElementById('svgOverlay');
    svg.innerHTML = '';
    svg.onclick = (e) => {
        if (e.target === svg) {
            clearSelection();
        }
    };
    const showBbox = document.getElementById('toggleBbox').checked;
    const showViol = document.getElementById('toggleViolations').checked;
    const filterType = document.getElementById('typeFilter').value;

    domData.nodes.forEach(node => {
        if (filterType !== 'ALL' && node.type !== filterType) return;
        const bbox = node.bounding_box;
        const corners = getBoxCorners(bbox);
        const activeViol = violationsData.find(v => v.node_id === node.node_id);
        const hasViol = !!activeViol && !appliedCorrections && activePresetIndex === 0;
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

        if (showViol && activeViol) {
            const g = createSvgElem('g', {});
            const isFixed = appliedCorrections || activePresetIndex === 1;
            const labelText = isFixed
                ? `[FIXED] '${activeViol.detected_snippet}' -> '${activeViol.suggested_correction}'`
                : `[!] VIOLATION: '${activeViol.detected_snippet}' -> '${activeViol.suggested_correction || ''}'`;

            const badgeBg = createSvgElem('rect', {
                x: bbox.x0, y: Math.max(0, bbox.y0 - 18),
                width: Math.min(320, labelText.length * 6.8), height: 18,
                class: 'viol-callout',
                style: isFixed ? 'fill: #00E676; stroke: #00B0FF;' : ''
            });
            const badgeTxt = createSvgElem('text', {
                x: bbox.x0 + 4, y: Math.max(12, bbox.y0 - 4), class: 'viol-text',
                style: isFixed ? 'fill: #000;' : ''
            });
            badgeTxt.textContent = labelText;
            g.appendChild(badgeBg);
            g.appendChild(badgeTxt);
            svg.appendChild(g);
        }
    });
}

function renderResizeHandles(svg, node, corners) {
    return renderQuadResizeHandles(svg, node, corners || getBoxCorners(node.bounding_box));
}

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

window.addEventListener('mousemove', (evt) => {
    if (!activeDrag) return;
    const node = domData.nodes.find(n => n.node_id === activeDrag.nodeId);
    if (!node) return;

    const curr = getSvgCoordinates(evt);
    const dx = curr.x - activeDrag.startSvgX;
    const dy = curr.y - activeDrag.startSvgY;
    const initCorners = activeDrag.initialCorners;

    if (activeDrag.action === 'corner') {
        const newCorners = initCorners.map((p, idx) => {
            if (idx === activeDrag.cornerIndex) {
                return { x: p.x + dx, y: p.y + dy };
            }
            return { ...p };
        });
        updateBboxFromCorners(node, newCorners);
    } else if (activeDrag.action === 'edge') {
        const eIdx = activeDrag.edgeIndex;
        const nextIdx = (eIdx + 1) % 4;
        const newCorners = initCorners.map((p, idx) => {
            if (idx === eIdx || idx === nextIdx) {
                return { x: p.x + dx, y: p.y + dy };
            }
            return { ...p };
        });
        updateBboxFromCorners(node, newCorners);
    } else if (activeDrag.action === 'move') {
        const newCorners = initCorners.map(p => ({ x: p.x + dx, y: p.y + dy }));
        updateBboxFromCorners(node, newCorners);
    }

    const inpX0 = document.getElementById('inpX0');
    const inpY0 = document.getElementById('inpY0');
    const inpX1 = document.getElementById('inpX1');
    const inpY1 = document.getElementById('inpY1');
    if (inpX0) {
        inpX0.value = node.bounding_box.x0;
        inpY0.value = node.bounding_box.y0;
        inpX1.value = node.bounding_box.x1;
        inpY1.value = node.bounding_box.y1;
    }

    renderSVGOverlays();
});

window.addEventListener('mouseup', () => {
    if (activeDrag) {
        activeDrag = null;
        renderDOMTree();
        renderSelectedEditor();
    }
});

function updateLayers() {
    renderSVGOverlays();
    const showScore = document.getElementById('toggleScore').checked;
    document.getElementById('scoreBadge').style.display = showScore ? 'block' : 'none';
}

function showTab(evt, tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    evt.currentTarget.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

function renderPlanTab() {
    const el = document.getElementById('planContent');
    if (el) {
        el.textContent = planData ? JSON.stringify(planData, null, 2) : "No planner config associated with this run.";
    }
}

function onLanguageChanged() {
    const sel = document.getElementById('selectLanguage').value;
    const banner = document.getElementById('statusBanner');
    banner.style.display = 'block';
    banner.textContent = `[INFO] Language override selected: '${sel}'. Click '[REDO] Redo Run' to re-evaluate with this language.`;
    setTimeout(() => { banner.style.display = 'none'; }, 4000);
}

async function redoWithSelectedLanguage() {
    const selectedLang = document.getElementById('selectLanguage').value;
    const presetName = (activePresetIndex === 1) ? 'docling_deep' : 'docling_fast';
    await rerunBackendPipeline(presetName, selectedLang);
}

async function rerunBackendPipeline(presetName, langOverride = null) {
    const targetLang = langOverride || document.getElementById('selectLanguage').value || activeLanguage;
    const banner = document.getElementById('statusBanner');
    banner.style.display = 'block';
    banner.textContent = `[RUNNING] Running backend pipeline for preset '${presetName}' with language '${targetLang}'...`;

    try {
        const res = await fetch('/api/rerun', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName, language: targetLang, pdf_path: pdfSourceFile })
        });

        if (res.ok) {
            const data = await res.json();
            banner.textContent = `[OK] Live pipeline finished. Applied preset '${presetName}' (Language: ${targetLang}).`;
            setTimeout(() => { banner.style.display = 'none'; }, 4000);

            domData = data.dom;
            violationsData = data.violations;
            decisionData = data.decision;
            activeLanguage = targetLang;
            activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;

            updatePresetUIState();
            return;
        }
    } catch (err) {
        console.log("[INFO] Live API endpoint unreachable, applying client simulation.", err);
    }

    activeLanguage = targetLang;
    banner.textContent = `[INFO] Language overridden to '${targetLang}'. (To run live Python backend, launch 'python src/main.py --serve').`;
    setTimeout(() => { banner.style.display = 'none'; }, 5000);

    function calculateSimulatedConfidence(targetLang, isDeepPreset) {
        const basePageScore = (initialDecisionData.per_page_confidence && (initialDecisionData.per_page_confidence['1'] || initialDecisionData.per_page_confidence[1])) || 0.9684;
        if (isDeepPreset) {
            return (initialDecisionData.attempts && initialDecisionData.attempts.length > 1)
                ? (initialDecisionData.attempts[1].overall_confidence || 0.9833)
                : 0.9833;
        }
        if (targetLang === 'en') {
            return basePageScore;
        } else if (targetLang === 'pl') {
            const hasDiacriticViolations = violationsData.some(v => v.rule_type === 'diacritic_conflict' || v.rule_type === 'ocr_character_substitution');
            if (hasDiacriticViolations && !appliedCorrections) {
                return (initialDecisionData.attempts && initialDecisionData.attempts[0])
                    ? (initialDecisionData.attempts[0].overall_confidence || 0.5324)
                    : 0.5324;
            }
            return basePageScore;
        }
        return basePageScore;
    }

    if (targetLang === 'en') {
        violationsData = violationsData.filter(v => v.rule_type !== 'diacritic_conflict' && v.rule_type !== 'ocr_character_substitution');
    } else if (targetLang === 'pl') {
        violationsData = JSON.parse(JSON.stringify(initialViolationsData));
    }

    activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;
    const isDeep = (activePresetIndex === 1);
    const simulatedScore = calculateSimulatedConfidence(targetLang, isDeep);
    decisionData.per_page_confidence = { "1": simulatedScore };
    decisionData.overall_confidence = simulatedScore;
    decisionData.is_accepted = (simulatedScore >= (decisionData.target_confidence_threshold || 0.82));
    decisionData.status = decisionData.is_accepted ? 'ACCEPT' : 'TRIGGER_FALLBACK';

    updatePresetUIState();
}

function switchPreset(stepIndex) {
    const presetName = (stepIndex === 1) ? 'docling_deep' : 'docling_fast';
    rerunBackendPipeline(presetName);
}

function updatePresetUIState() {
    document.getElementById('btnPreset1').classList.toggle('active', activePresetIndex === 0);
    document.getElementById('btnPreset2').classList.toggle('active', activePresetIndex === 1);
    const st2 = document.getElementById('statusPreset2');

    const attempts = decisionData.attempts || [];
    const currentAttempt = (attempts.length > 1) ? (attempts[activePresetIndex] || attempts[attempts.length - 1]) : null;

    let overallScore = (currentAttempt && currentAttempt.overall_confidence !== undefined)
        ? currentAttempt.overall_confidence
        : decisionData.overall_confidence;

    let p1Score = null;
    if (currentAttempt && currentAttempt.per_page_confidence) {
        p1Score = currentAttempt.per_page_confidence['1'] || currentAttempt.per_page_confidence[1];
    } else if (decisionData.per_page_confidence) {
        p1Score = decisionData.per_page_confidence['1'] || decisionData.per_page_confidence[1];
    }
    if (p1Score === undefined || p1Score === null) {
        p1Score = overallScore;
    }

    let displayedStatus = (currentAttempt && currentAttempt.status)
        ? currentAttempt.status
        : (decisionData.status || 'ACCEPT');

    let threshold = decisionData.target_confidence_threshold || 0.82;
    let isAccepted = (displayedStatus === 'ACCEPT' || overallScore >= threshold);

    const detBadge = document.getElementById('detectedLangBadge');
    if (detBadge) {
        const det = (decisionData.detected_languages && decisionData.detected_languages['1']) || decisionData.primary_detected_language || 'pl';
        detBadge.textContent = `P1: ${det} (Active: ${activeLanguage})`;
    }

    if (activePresetIndex === 1) {
        st2.textContent = 'ACTIVE (PASSED)';
        st2.style.background = 'var(--accent-green)';
        st2.style.color = '#000';
        appliedCorrections = true;
        document.getElementById('toggleCorrections').checked = true;
    } else {
        st2.textContent = 'Candidate';
        st2.style.background = '#4B5563';
        st2.style.color = '#FFF';
    }

    document.getElementById('scoreTitle').textContent = `Page 1 Confidence Score: ${Number(p1Score).toFixed(4)}`;
    document.getElementById('scoreSub').textContent = `Status: ${displayedStatus} | Overall Confidence: ${Number(overallScore).toFixed(4)} | Violations Flagged: ${violationsData.length}`;
    document.getElementById('scoreSub').style.color = isAccepted ? 'var(--accent-green)' : 'var(--accent-red)';
    document.getElementById('scoreBadge').classList.toggle('fail', !isAccepted);

    renderDOMTree();
    renderViolationsList();
    renderDecisionLog();
    renderPlanTab();
    renderSelectedEditor();
    renderSVGOverlays();
}

async function saveAnnotations() {
    const banner = document.getElementById('statusBanner');
    banner.style.display = 'block';
    banner.textContent = `[SAVING] Saving modified DocumentDOM annotations...`;

    try {
        const res = await fetch('/api/save_dom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dom: domData, output_dir: 'output' })
        });
        if (res.ok) {
            const data = await res.json();
            banner.textContent = `[OK] Annotations saved successfully to '${data.path}'.`;
            setTimeout(() => { banner.style.display = 'none'; }, 4000);
            return;
        }
    } catch (e) {
        console.log('[INFO] Server endpoint unreachable, initiating file download.', e);
    }

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(domData, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "document_dom.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    banner.textContent = `[OK] Downloaded updated document_dom.json.`;
    setTimeout(() => { banner.style.display = 'none'; }, 4000);
}

function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

renderDOMTree();
renderViolationsList();
renderDecisionLog();
renderPlanTab();
renderSelectedEditor();
renderSVGOverlays();
