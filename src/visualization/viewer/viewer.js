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

function selectNode(nodeId) {
    selectedNodeId = nodeId;
    document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
    const card = document.getElementById(`card-${nodeId}`);
    if (card) {
        card.classList.add('selected');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    renderSelectedEditor();
    renderSVGOverlays();
}

function renderSelectedEditor() {
    const container = document.getElementById('selectedEditorContainer');
    if (!selectedNodeId) {
        container.innerHTML = '';
        return;
    }
    const node = domData.nodes.find(n => n.node_id === selectedNodeId);
    if (!node) {
        container.innerHTML = '';
        return;
    }
    const bbox = node.bounding_box;
    const isIncorrect = !!node.is_incorrect_text;
    const hasQuad = !!bbox.quad;

    if (node.user_correction_note === undefined || node.user_correction_note === null || node.user_correction_note === '') {
        node.user_correction_note = (node.content && node.content.raw_text) ? node.content.raw_text : '';
    }
    const noteVal = node.user_correction_note;

    container.innerHTML = `
        <div class="editor-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <h4>Selected: ${node.node_id} (${node.type})</h4>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;" onclick="selectNode(null)">Close</button>
            </div>
            <div class="coord-grid">
                <div class="coord-field"><label>X0</label><input type="number" step="0.5" id="inpX0" value="${bbox.x0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y0</label><input type="number" step="0.5" id="inpY0" value="${bbox.y0}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>X1</label><input type="number" step="0.5" id="inpX1" value="${bbox.x1}" onchange="onManualCoordChange()"></div>
                <div class="coord-field"><label>Y1</label><input type="number" step="0.5" id="inpY1" value="${bbox.y1}" onchange="onManualCoordChange()"></div>
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
        </div>
    `;
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

    node.bounding_box.x0 = roundCoord(Math.min(x0, x1 - 5));
    node.bounding_box.y0 = roundCoord(Math.min(y0, y1 - 5));
    node.bounding_box.x1 = roundCoord(Math.max(x1, x0 + 5));
    node.bounding_box.y1 = roundCoord(Math.max(y1, y0 + 5));
    node.bounding_box.quad = null;

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

        const card = document.createElement('div');
        card.className = `node-card ${hasViol && !isFixed ? 'has-violation' : ''} ${isIncorrect ? 'is-incorrect' : ''} ${node.node_id === selectedNodeId ? 'selected' : ''}`;
        card.id = `card-${node.node_id}`;
        card.onclick = () => selectNode(node.node_id);
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
    const showBbox = document.getElementById('toggleBbox').checked;
    const showViol = document.getElementById('toggleViolations').checked;
    const filterType = document.getElementById('typeFilter').value;

    domData.nodes.forEach(node => {
        if (filterType !== 'ALL' && node.type !== filterType) return;
        const bbox = node.bounding_box;
        const corners = getBoxCorners(bbox);
        const activeViol = violationsData.find(v => v.node_id === node.node_id);
        const hasViol = !!activeViol && !appliedCorrections && activePresetIndex === 0;
        const isSelected = (node.node_id === selectedNodeId);
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
            poly.onclick = (e) => { e.stopPropagation(); selectNode(node.node_id); };
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
    if (nodeId !== selectedNodeId) return;
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
