/**
 * src/visualization/viewer/js/app.js
 *
 * Global event listener bindings (drag, wheel zoom, keyboard navigation),
 * viewer initialization, and runtime startup.
 */

// Mouse wheel zooming
const visualPaneEl = document.getElementById('visualPane');
if (visualPaneEl) {
    visualPaneEl.addEventListener('wheel', (e) => {
        if (e.ctrlKey) {
            e.preventDefault();
            adjustZoom(e.deltaY < 0 ? 0.1 : -0.1);
        }
    }, { passive: false });
}

window.addEventListener('mousemove', (evt) => {
    if (isDrawSectionMode && drawStartPt && drawRectEl) {
        const curr = getSvgCoordinates(evt);
        const x = Math.min(drawStartPt.x, curr.x);
        const y = Math.min(drawStartPt.y, curr.y);
        const w = Math.abs(curr.x - drawStartPt.x);
        const h = Math.abs(curr.y - drawStartPt.y);
        drawRectEl.setAttribute('x', x);
        drawRectEl.setAttribute('y', y);
        drawRectEl.setAttribute('width', w);
        drawRectEl.setAttribute('height', h);
        return;
    }

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

window.addEventListener('mouseup', (evt) => {
    if (isDrawSectionMode && drawStartPt && drawRectEl) {
        const curr = getSvgCoordinates(evt);
        const minX = roundCoord(Math.min(drawStartPt.x, curr.x));
        const minY = roundCoord(Math.min(drawStartPt.y, curr.y));
        const maxX = roundCoord(Math.max(drawStartPt.x, curr.x));
        const maxY = roundCoord(Math.max(drawStartPt.y, curr.y));
        const w = maxX - minX;
        const h = maxY - minY;

        if (drawRectEl.parentNode) {
            drawRectEl.parentNode.removeChild(drawRectEl);
        }
        drawRectEl = null;
        drawStartPt = null;

        if (w >= 15 && h >= 10) {
            const newIndex = domData.nodes.length + 1;
            const newNodeId = `node_p${currentPage}_custom_${newIndex}`;
            const newNode = {
                node_id: newNodeId,
                type: 'paragraph',
                global_page_index: currentPage,
                temp_slice_index: currentPage,
                bounding_box: {
                    x0: minX,
                    y0: minY,
                    x1: maxX,
                    y1: maxY,
                    angle: 0.0
                },
                content: {
                    raw_text: ''
                },
                user_correction_note: ''
            };
            domData.nodes.push(newNode);
            toggleDrawSectionMode();
            handleNodeClick(null, newNodeId);
            // Proactively trigger OCR for newly drawn section
            triggerCutoutSecondPass(newNodeId);
            return;
        }
    }

    if (activeDrag) {
        activeDrag = null;
        renderDOMTree();
        renderSelectedEditor();
    }
});

window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        prevPage();
    } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
        nextPage();
    }
});

async function startViewer() {
    const urlParams = new URLSearchParams(window.location.search);
    const outputDirParam = urlParams.get('output_dir');
    const targetPageParam = parseInt(urlParams.get('page') || '1', 10) || 1;
    const stepParam = urlParams.get('step');

    if (window.VIEWER_DATA && window.VIEWER_DATA.dom && window.VIEWER_DATA.dom.nodes && window.VIEWER_DATA.dom.nodes.length > 0) {
        hydrateViewer(window.VIEWER_DATA, targetPageParam);
        return;
    }

    try {
        let fetchUrl = '/api/viewer_data';
        const params = [];
        if (outputDirParam) params.push(`output_dir=${encodeURIComponent(outputDirParam)}`);
        if (stepParam) params.push(`step=${encodeURIComponent(stepParam)}`);
        if (params.length > 0) fetchUrl += `?${params.join('&')}`;

        const resp = await fetch(fetchUrl);
        if (resp.ok) {
            const data = await resp.json();
            hydrateViewer(data, targetPageParam);
            return;
        }
    } catch (e) {
        console.log('[INFO] Backend /api/viewer_data not reachable, using offline state.');
    }

    initPageControls();
    switchPage(targetPageParam);
}

const pageImgEl = document.getElementById('pageImg');
if (pageImgEl) {
    pageImgEl.addEventListener('load', () => {
        if (typeof updateSvgViewBox === 'function') {
            updateSvgViewBox();
        }
        if (typeof renderSVGOverlays === 'function') {
            renderSVGOverlays();
        }
    });
}

startViewer();
