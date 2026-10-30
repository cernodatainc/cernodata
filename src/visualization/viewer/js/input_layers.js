/**
 * src/visualization/viewer/js/input_layers.js
 *
 * Input layer abstraction and interaction manager for the visual flow canvas.
 * Decouples pointer and keyboard handling into concrete layers for selection,
 * dragging, and adding custom DOM elements.
 */

class BaseInputLayer {
    constructor(name, manager) {
        this.name = name;
        this.manager = manager;
        this.isActive = false;
    }
    activate() { this.isActive = true; }
    deactivate() { this.isActive = false; }
    onPointerDown(evt, pt, target) { return false; }
    onPointerMove(evt, pt) { return false; }
    onPointerUp(evt, pt) { return false; }
    onKeyDown(evt) { return false; }
    onWheel(evt) { return false; }
}

class SelectInputLayer extends BaseInputLayer {
    constructor(manager) {
        super('select', manager);
    }

    activate() {
        super.activate();
        const svg = document.getElementById('svgOverlay');
        const visualPane = document.getElementById('visualPane');
        const btn = document.getElementById('btnDrawSection');
        if (svg) svg.classList.remove('draw-section-active');
        if (visualPane) visualPane.style.cursor = 'default';
        if (btn) btn.classList.remove('active');
    }

    onPointerDown(evt, pt, target) {
        if (!target) return false;
        const handleEl = target.closest ? target.closest('.resize-handle') : null;
        if (handleEl) {
            const nodeId = handleEl.getAttribute('data-node-id');
            const handleAction = handleEl.getAttribute('data-handle-action');
            if (handleAction === 'corner') {
                const cornerIndex = parseInt(handleEl.getAttribute('data-corner-index') || '0', 10);
                onCornerHandleMouseDown(evt, cornerIndex, nodeId);
                return true;
            } else if (handleAction === 'edge') {
                const edgeIndex = parseInt(handleEl.getAttribute('data-edge-index') || '0', 10);
                onEdgeHandleMouseDown(evt, edgeIndex, nodeId);
                return true;
            }
        }
        const polyEl = target.closest ? target.closest('.node-bbox') : null;
        if (polyEl) {
            const nodeId = polyEl.getAttribute('data-node-id') || (polyEl.id ? polyEl.id.replace('svg-', '') : null);
            if (nodeId && selectedNodeIds.includes(nodeId)) {
                onPolygonMouseDown(evt, nodeId);
                return true;
            }
        }
        const svg = document.getElementById('svgOverlay');
        if (target === svg || target.id === 'canvasContainer' || target.id === 'pageImg') {
            clearSelection();
            return true;
        }
        return false;
    }

    onPointerMove(evt, pt) {
        if (!activeDrag) return false;
        const node = domData.nodes.find(n => n.node_id === activeDrag.nodeId);
        if (!node) return false;

        const dx = pt.x - activeDrag.startSvgX;
        const dy = pt.y - activeDrag.startSvgY;
        const initCorners = activeDrag.initialCorners;

        if (activeDrag.action === 'corner') {
            const newCorners = initCorners.map((p, idx) => (idx === activeDrag.cornerIndex ? { x: p.x + dx, y: p.y + dy } : { ...p }));
            updateBboxFromCorners(node, newCorners);
        } else if (activeDrag.action === 'edge') {
            const eIdx = activeDrag.edgeIndex;
            const nextIdx = (eIdx + 1) % 4;
            const newCorners = initCorners.map((p, idx) => ((idx === eIdx || idx === nextIdx) ? { x: p.x + dx, y: p.y + dy } : { ...p }));
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
        return true;
    }

    onPointerUp(evt, pt) {
        if (activeDrag) {
            activeDrag = null;
            renderDOMTree();
            renderSelectedEditor();
            return true;
        }
        return false;
    }

    onKeyDown(evt) {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return false;
        if (evt.key === 'ArrowLeft' || evt.key === 'PageUp') {
            prevPage();
            return true;
        } else if (evt.key === 'ArrowRight' || evt.key === 'PageDown') {
            nextPage();
            return true;
        } else if (evt.key === 'Escape') {
            clearSelection();
            return true;
        }
        return false;
    }

    onWheel(evt) {
        if (evt.ctrlKey) {
            evt.preventDefault();
            adjustZoom(evt.deltaY < 0 ? 0.1 : -0.1);
            return true;
        }
        return false;
    }
}

class DrawSectionInputLayer extends BaseInputLayer {
    constructor(manager) {
        super('draw', manager);
        this.startPt = null;
        this.previewEl = null;
    }

    activate() {
        super.activate();
        isDrawSectionMode = true;
        const btn = document.getElementById('btnDrawSection');
        const visualPane = document.getElementById('visualPane');
        const banner = document.getElementById('statusBanner');
        const svg = document.getElementById('svgOverlay');
        if (btn) btn.classList.add('active');
        if (visualPane) visualPane.style.cursor = 'crosshair';
        if (svg) svg.classList.add('draw-section-active');
        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            banner.textContent = 'Click and drag on the page to draw a new section. Press Escape to cancel.';
        }
    }

    deactivate() {
        super.deactivate();
        isDrawSectionMode = false;
        const btn = document.getElementById('btnDrawSection');
        const visualPane = document.getElementById('visualPane');
        const banner = document.getElementById('statusBanner');
        const svg = document.getElementById('svgOverlay');
        if (btn) btn.classList.remove('active');
        if (visualPane) visualPane.style.cursor = 'default';
        if (svg) svg.classList.remove('draw-section-active');
        if (banner) banner.style.display = 'none';

        if (this.previewEl && this.previewEl.parentNode) {
            this.previewEl.parentNode.removeChild(this.previewEl);
        }
        this.previewEl = null;
        this.startPt = null;
        drawRectEl = null;
        drawStartPt = null;
    }

    onPointerDown(evt, pt, target) {
        evt.preventDefault();
        evt.stopPropagation();
        const svg = document.getElementById('svgOverlay');
        if (!svg) return false;

        this.startPt = { x: pt.x, y: pt.y };
        drawStartPt = this.startPt;

        if (this.previewEl && this.previewEl.parentNode) {
            this.previewEl.parentNode.removeChild(this.previewEl);
        }

        this.previewEl = createSvgElem('rect', {
            x: pt.x,
            y: pt.y,
            width: 0,
            height: 0,
            fill: OVERLAY_COLORS.drawFill,
            stroke: OVERLAY_COLORS.drawStroke,
            'stroke-width': '2',
            'stroke-dasharray': '4 2',
            id: 'drawSectionPreview'
        });
        drawRectEl = this.previewEl;
        svg.appendChild(this.previewEl);
        return true;
    }

    onPointerMove(evt, pt) {
        if (!this.startPt || !this.previewEl) return false;
        const x = Math.min(this.startPt.x, pt.x);
        const y = Math.min(this.startPt.y, pt.y);
        const w = Math.abs(pt.x - this.startPt.x);
        const h = Math.abs(pt.y - this.startPt.y);

        this.previewEl.setAttribute('x', x);
        this.previewEl.setAttribute('y', y);
        this.previewEl.setAttribute('width', w);
        this.previewEl.setAttribute('height', h);
        return true;
    }

    onPointerUp(evt, pt) {
        if (!this.startPt || !this.previewEl) return false;
        const minX = roundCoord(Math.min(this.startPt.x, pt.x));
        const minY = roundCoord(Math.min(this.startPt.y, pt.y));
        const maxX = roundCoord(Math.max(this.startPt.x, pt.x));
        const maxY = roundCoord(Math.max(this.startPt.y, pt.y));
        const w = maxX - minX;
        const h = maxY - minY;

        if (this.previewEl.parentNode) {
            this.previewEl.parentNode.removeChild(this.previewEl);
        }
        this.previewEl = null;
        this.startPt = null;
        drawRectEl = null;
        drawStartPt = null;

        if (w >= 15 && h >= 10) {
            const newNode = this.manager.createDOMElement({
                x0: minX,
                y0: minY,
                x1: maxX,
                y1: maxY,
                type: 'paragraph',
                page: currentPage
            });

            this.manager.setMode('select');
            renderDOMTree();
            renderSVGOverlays();
            handleNodeClick(null, newNode.node_id);
            saveAnnotations(true);
            triggerCutoutSecondPass(newNode.node_id);
            return true;
        }

        this.manager.setMode('select');
        return true;
    }

    onKeyDown(evt) {
        if (evt.key === 'Escape') {
            this.manager.setMode('select');
            return true;
        }
        return false;
    }
}

class ViewerInputManager {
    constructor() {
        this.layers = new Map();
        this.activeMode = 'select';
        this.isInitialized = false;

        this.registerLayer(new SelectInputLayer(this));
        this.registerLayer(new DrawSectionInputLayer(this));
    }

    registerLayer(layer) {
        this.layers.set(layer.name, layer);
    }

    setMode(modeName) {
        if (!this.layers.has(modeName)) return;
        if (this.activeMode === modeName && this.getActiveLayer().isActive) return;

        const prevLayer = this.getActiveLayer();
        if (prevLayer) prevLayer.deactivate();

        this.activeMode = modeName;
        const nextLayer = this.getActiveLayer();
        if (nextLayer) nextLayer.activate();
    }

    getMode() {
        return this.activeMode;
    }

    getActiveLayer() {
        return this.layers.get(this.activeMode) || this.layers.get('select');
    }

    getSvgCoordinates(evt) {
        const svg = document.getElementById('svgOverlay');
        if (!svg) return { x: 0, y: 0 };

        try {
            const ctm = svg.getScreenCTM();
            if (ctm) {
                const pt = svg.createSVGPoint();
                pt.x = evt.clientX;
                pt.y = evt.clientY;
                const inv = ctm.inverse();
                if (inv) {
                    const transformed = pt.matrixTransform(inv);
                    if (!isNaN(transformed.x) && !isNaN(transformed.y)) {
                        return { x: roundCoord(transformed.x), y: roundCoord(transformed.y) };
                    }
                }
            }
        } catch (e) {
            // Fallback using bounding client rectangle
        }

        const rect = svg.getBoundingClientRect();
        const vb = svg.viewBox && svg.viewBox.baseVal;
        const vbW = (vb && vb.width > 0) ? vb.width : (rect.width || 595.28);
        const vbH = (vb && vb.height > 0) ? vb.height : (rect.height || 841.89);
        const scaleX = rect.width > 0 ? vbW / rect.width : 1.0;
        const scaleY = rect.height > 0 ? vbH / rect.height : 1.0;

        return {
            x: roundCoord((evt.clientX - rect.left) * scaleX),
            y: roundCoord((evt.clientY - rect.top) * scaleY)
        };
    }

    createDOMElement(options) {
        if (!domData) domData = { nodes: [] };
        if (!Array.isArray(domData.nodes)) domData.nodes = [];

        const page = options.page || currentPage || 1;
        const existingIds = new Set(domData.nodes.map(n => n.node_id));
        let customIndex = domData.nodes.length + 1;
        let newNodeId = `node_p${page}_custom_${customIndex}`;

        while (existingIds.has(newNodeId)) {
            customIndex++;
            newNodeId = `node_p${page}_custom_${customIndex}`;
        }

        const x0 = roundCoord(options.x0 !== undefined ? options.x0 : 50);
        const y0 = roundCoord(options.y0 !== undefined ? options.y0 : 50);
        const x1 = roundCoord(options.x1 !== undefined ? options.x1 : x0 + 100);
        const y1 = roundCoord(options.y1 !== undefined ? options.y1 : y0 + 30);
        const nodeType = options.type || 'paragraph';
        const rawText = options.text || '';

        const newNode = {
            node_id: newNodeId,
            type: nodeType,
            global_page_index: page,
            temp_slice_index: page,
            bounding_box: {
                x0: Math.min(x0, x1),
                y0: Math.min(y0, y1),
                x1: Math.max(x0, x1),
                y1: Math.max(y0, y1),
                angle: 0.0,
                quad: null
            },
            content: {
                raw_text: rawText
            },
            user_correction_note: rawText,
            is_custom: true,
            violations: []
        };

        domData.nodes.push(newNode);
        return newNode;
    }

    init() {
        if (this.isInitialized) return;
        this.isInitialized = true;

        const visualPane = document.getElementById('visualPane');
        const svg = document.getElementById('svgOverlay');

        if (svg) {
            svg.addEventListener('mousedown', (evt) => {
                const pt = this.getSvgCoordinates(evt);
                this.getActiveLayer().onPointerDown(evt, pt, evt.target);
            });
            svg.addEventListener('click', (evt) => {
                if (this.activeMode === 'select' && evt.target === svg) {
                    clearSelection();
                }
            });
        }

        if (visualPane) {
            visualPane.addEventListener('wheel', (evt) => {
                this.getActiveLayer().onWheel(evt);
            }, { passive: false });
        }

        window.addEventListener('mousemove', (evt) => {
            const pt = this.getSvgCoordinates(evt);
            this.getActiveLayer().onPointerMove(evt, pt);
        });

        window.addEventListener('mouseup', (evt) => {
            const pt = this.getSvgCoordinates(evt);
            this.getActiveLayer().onPointerUp(evt, pt);
        });

        window.addEventListener('keydown', (evt) => {
            this.getActiveLayer().onKeyDown(evt);
        });

        this.getActiveLayer().activate();
    }
}

window.ViewerInputManager = ViewerInputManager;
window.BaseInputLayer = BaseInputLayer;
window.SelectInputLayer = SelectInputLayer;
window.DrawSectionInputLayer = DrawSectionInputLayer;
window.viewerInputManager = new ViewerInputManager();

function toggleDrawSectionMode() {
    if (!window.viewerInputManager) {
        window.viewerInputManager = new ViewerInputManager();
    }
    const currentMode = window.viewerInputManager.getMode();
    const nextMode = (currentMode === 'draw') ? 'select' : 'draw';
    window.viewerInputManager.setMode(nextMode);
}

function addDOMElement(options) {
    if (!window.viewerInputManager) {
        window.viewerInputManager = new ViewerInputManager();
    }
    const node = window.viewerInputManager.createDOMElement(options || {});
    renderDOMTree();
    renderSVGOverlays();
    handleNodeClick(null, node.node_id);
    if (typeof saveAnnotations === 'function') {
        saveAnnotations(true);
    }
    return node;
}
