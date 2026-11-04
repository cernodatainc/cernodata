/**
 * src/visualization/viewer/js/cutout.js
 *
 * Image crop preview, polygon vertex extraction, affine warping unskew transformations,
 * and targeted section OCR re-parsing.
 */
 
/**
 * Computes or retrieves the effective rotation angle in degrees for a bounding box.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {Object} bbox - Bounding box object.
 * @returns {number} Angle in degrees.
 */
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
    const viols = getViolationsList();
    const v = viols.find(viol => viol.node_id === nodeId && viol.bounding_box && viol.bounding_box.angle);
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
 
/**
 * Toggles between unskewed affine-rectified crop and raw skewed oriented polygon cutout.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function toggleCutoutUnskew(nodeId) {
    isCutoutUnskewed = !isCutoutUnskewed;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    renderCutoutPreview(node.node_id, node.bounding_box, 'cutoutPreviewImg_' + node.node_id, isCutoutUnskewed);
    const btn = document.getElementById('btnToggleUnskew_' + node.node_id);
    if (btn) {
        btn.textContent = isCutoutUnskewed ? 'Show skewed' : 'Unskew';
        btn.title = isCutoutUnskewed ? 'Switch to oriented skewed polygon cutout' : 'Transform skewed quadrilateral into a horizontal, unskewed text strip';
    }
    const modeLabel = document.getElementById('cutoutModeLabel_' + node.node_id);
    if (modeLabel) {
        modeLabel.textContent = isCutoutUnskewed ? 'Mode: unskewed (rectified)' : 'Mode: skewed (oriented selection)';
    }
}
 
/**
 * Warps a source image triangle (s0, s1, s2) onto a destination canvas triangle (d0, d1, d2)
 * using an affine 2D transform matrix.
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas 2D context.
 * @param {HTMLImageElement} img - Source page image.
 * @param {{x: number, y: number}} s0 - Source vertex 0.
 * @param {{x: number, y: number}} s1 - Source vertex 1.
 * @param {{x: number, y: number}} s2 - Source vertex 2.
 * @param {{x: number, y: number}} d0 - Destination vertex 0.
 * @param {{x: number, y: number}} d1 - Destination vertex 1.
 * @param {{x: number, y: number}} d2 - Destination vertex 2.
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
 * Calculates quadrilateral polygon vertices representing the skewed footprint of a bounding box.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {Object} bbox - Bounding box object.
 * @returns {Array<{x: number, y: number}>} Array of 4 vertices [TL, TR, BR, BL].
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
 * Extracts and renders a high-resolution image crop of a bounding box into target <img> element.
 *
 * @param {string} nodeId - Node identifier.
 * @param {Object} bbox - Bounding box definition.
 * @param {string} targetImgId - DOM element ID of the target preview image.
 * @param {boolean} [unskew=isCutoutUnskewed] - Whether to apply perspective rectification.
 */
/**
 * Extracts base64 encoded PNG data URI of a node's cropped canvas.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {boolean} [unskew=isCutoutUnskewed] - Whether to rectify skewed angle.
 * @returns {string|null} Base64 PNG data URI string or null.
 */
function getCutoutBase64(nodeId, unskew = isCutoutUnskewed) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return null;
    const pageImg = document.getElementById('pageImg');
    if (!pageImg || !pageImg.naturalWidth || !pageImg.naturalHeight) return null;

    const svg = document.getElementById('svgOverlay');
    const vbW = (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) ? svg.viewBox.baseVal.width : 595.28;
    const vbH = (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.height) ? svg.viewBox.baseVal.height : 841.89;

    const scaleX = pageImg.naturalWidth / vbW;
    const scaleY = pageImg.naturalHeight / vbH;

    const corners = getNodeSkewCorners(nodeId, node.bounding_box);
    const s0 = { x: corners[0].x * scaleX, y: corners[0].y * scaleY };
    const s1 = { x: corners[1].x * scaleX, y: corners[1].y * scaleY };
    const s2 = { x: corners[2].x * scaleX, y: corners[2].y * scaleY };
    const s3 = { x: corners[3].x * scaleX, y: corners[3].y * scaleY };

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    if (unskew) {
        const wTop = Math.hypot(s1.x - s0.x, s1.y - s0.y);
        const wBot = Math.hypot(s2.x - s3.x, s2.y - s3.y);
        const hLeft = Math.hypot(s3.x - s0.x, s3.y - s0.y);
        const hRight = Math.hypot(s2.x - s1.x, s2.y - s1.y);

        const dstW = Math.max(10, Math.round((wTop + wBot) / 2));
        const dstH = Math.max(8, Math.round((hLeft + hRight) / 2));

        canvas.width = dstW;
        canvas.height = dstH;

        const d0 = { x: 0, y: 0 }, d1 = { x: dstW, y: 0 }, d2 = { x: dstW, y: dstH }, d3 = { x: 0, y: dstH };
        renderTriangleWarp(ctx, pageImg, s0, s1, s2, d0, d1, d2);
        renderTriangleWarp(ctx, pageImg, s0, s2, s3, d0, d2, d3);
        return canvas.toDataURL('image/png');
    } else {
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

        return canvas.toDataURL('image/png');
    }
}

/**
 * Extracts and renders a high-resolution image crop of a bounding box into target <img> element.
 *
 * @param {string} nodeId - Node identifier.
 * @param {Object} bbox - Bounding box definition.
 * @param {string} targetImgId - DOM element ID of the target preview image.
 * @param {boolean} [unskew=isCutoutUnskewed] - Whether to apply perspective rectification.
 */
function renderCutoutPreview(nodeId, bbox, targetImgId, unskew = isCutoutUnskewed) {
    const pageImg = document.getElementById('pageImg');
    const targetImg = document.getElementById(targetImgId);
    if (!pageImg || !targetImg) return;

    function doDraw() {
        if (!pageImg.naturalWidth || !pageImg.naturalHeight) return;
        const b64 = getCutoutBase64(nodeId, unskew);
        if (b64) targetImg.src = b64;
    }

    if (pageImg.complete && pageImg.naturalWidth > 0) {
        doDraw();
    } else {
        pageImg.addEventListener('load', doDraw, { once: true });
    }
}
 
/**
 * Triggers backend targeted OCR re-extraction pass for the selected section.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
window.selectedOcrEnginesMap = window.selectedOcrEnginesMap || {};
window.pendingOcrResultsMap = window.pendingOcrResultsMap || {};

/**
 * Updates selected OCR engines list for a given node.
 *
 * @param {string} nodeId - Target node ID.
 * @param {string} engine - Engine name.
 * @param {boolean} checked - Whether checked.
 */
function onOcrEngineToggle(nodeId, engine, checked) {
    const curr = window.selectedOcrEnginesMap[nodeId] ? [...window.selectedOcrEnginesMap[nodeId]] : ['rapidocr'];
    if (checked && !curr.includes(engine)) curr.push(engine);
    else if (!checked) {
        const idx = curr.indexOf(engine);
        if (idx !== -1) curr.splice(idx, 1);
    }
    window.selectedOcrEnginesMap[nodeId] = curr.length > 0 ? curr : ['rapidocr'];
}

/**
 * Triggers backend targeted OCR re-extraction pass with selected engines.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
async function triggerCutoutSecondPass(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const banner = document.getElementById('statusBanner');
    const ocrBtn = document.getElementById(`btnCutoutOcr_${nodeId}`);
    if (ocrBtn) {
        ocrBtn.disabled = true;
        ocrBtn.textContent = 'Parsing…';
    }

    const engines = (window.selectedOcrEnginesMap && window.selectedOcrEnginesMap[nodeId] && window.selectedOcrEnginesMap[nodeId].length > 0)
        ? window.selectedOcrEnginesMap[nodeId]
        : ['rapidocr'];

    if (banner) {
        banner.style.display = 'block';
        banner.className = 'status-banner';
        banner.textContent = `Parsing section '${nodeId}' with [${engines.join(', ')}]…`;
    }

    let b64 = getCutoutBase64(nodeId, isCutoutUnskewed);
    if (!b64) {
        const previewImg = document.getElementById(`cutoutPreviewImg_${nodeId}`);
        if (previewImg && previewImg.src && previewImg.src.startsWith('data:image')) {
            b64 = previewImg.src;
        }
    }

    const payload = {
        node_id: nodeId,
        image_base64: b64,
        bbox: node.bounding_box,
        page: node.global_page_index || 1,
        pdf_path: pdfSourceFile || '',
        language: activeLanguage || 'en',
        engines: engines
    };

    try {
        const resp = await fetch('/api/parse_section_ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.error || `Server returned ${resp.status}`);
        }

        const data = await resp.json();
        window.pendingOcrResultsMap[nodeId] = data;
        promptAcceptOcrOutput(nodeId, data);
    } catch (err) {
        console.error('Section OCR parse error:', err);
        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            banner.textContent = `Could not parse section with OCR: ${err.message}`;
            setTimeout(() => { banner.style.display = 'none'; }, 6000);
        }
    } finally {
        if (ocrBtn) {
            ocrBtn.disabled = false;
            ocrBtn.textContent = 'Parse section with OCR';
        }
    }
}

/**
 * Prompts user to review and accept or discard OCR engine output.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {Object} data - OCR response payload.
 */
function promptAcceptOcrOutput(nodeId, data) {
    const container = document.getElementById(`ocrPromptContainer_${nodeId}`);
    const banner = document.getElementById('statusBanner');
    if (!container) {
        const primaryText = data.text || '';
        if (window.confirm(`Accept OCR output for node '${nodeId}'?\n\n"${primaryText}"`)) {
            acceptOcrOutput(nodeId, data.engine || 'rapidocr');
        } else {
            dismissOcrPrompt(nodeId);
        }
        return;
    }

    const p = (typeof INSPECTOR_PALETTE !== 'undefined') ? INSPECTOR_PALETTE : {
        border: '#D0CDC6', textPrimary: '#1F1D1A', textMuted: '#625E57', blue: '#1E4B8A',
        green: '#2E6E52', red: '#B42318', bgCard: '#FDFCFC', bgDark: '#EFF1F2'
    };

    const results = data.results || { [data.engine || 'rapidocr']: data };
    const entries = Object.entries(results);

    const itemsHtml = entries.map(([eng, res]) => {
        const success = res && res.success;
        const textVal = (res && res.text) || '';
        const confPct = Math.round(((res && res.confidence) || 0) * 100);
        const errVal = (res && res.error) || 'Engine failed';

        if (!success) {
            return `
                <div style="background:${p.bgCard}; border:1px solid ${p.border}; border-radius:4px; padding:6px 8px; margin-bottom:6px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:11px; font-weight:600; text-transform:uppercase; color:${p.textMuted};">${escapeHtml(eng)}</span>
                        <span style="font-size:11px; color:${p.red};">Failed</span>
                    </div>
                    <div style="font-size:11px; color:${p.textMuted}; margin-top:2px;">${escapeHtml(errVal)}</div>
                </div>
            `;
        }

        return `
            <div style="background:${p.bgCard}; border:1px solid ${p.border}; border-radius:4px; padding:6px 8px; margin-bottom:6px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-size:11px; font-weight:600; text-transform:uppercase; color:${p.blue};">${escapeHtml(eng)}</span>
                    <span style="font-size:11px; font-weight:500; color:${p.green};">${confPct}% confidence</span>
                </div>
                <textarea id="ocrCandidateText_${nodeId}_${escapeHtml(eng)}" style="width:100%; box-sizing:border-box; font-family:monospace; font-size:11px; padding:4px 6px; border:1px solid ${p.border}; border-radius:3px; background:${p.bgDark}; color:${p.textPrimary}; resize:vertical; min-height:45px;">${escapeHtml(textVal)}</textarea>
                <div style="display:flex; justify-content:flex-end; margin-top:4px;">
                    <button class="action-btn action-btn-decollide-sm" style="background:${p.green}; color:#FFFFFF; border-color:${p.green}; cursor:pointer;" onclick="acceptOcrOutput('${nodeId}', '${escapeHtml(eng)}')">Accept ${escapeHtml(eng)}</button>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div style="background:#FFFFFF; border:1px solid ${p.blue}; border-left:4px solid ${p.blue}; border-radius:4px; padding:8px 10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:12px; font-weight:600; color:${p.blue};">Accept OCR output for '${escapeHtml(nodeId)}'?</span>
                <button class="action-btn action-btn-decollide-sm" style="color:${p.red}; border-color:${p.border};" onclick="dismissOcrPrompt('${nodeId}')">Discard all</button>
            </div>
            ${itemsHtml}
        </div>
    `;
    container.style.display = 'block';

    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        banner.textContent = `OCR completed for '${nodeId}'. Please accept or discard the extracted text.`;
    }
}

/**
 * Accepts output of a specific OCR engine and updates the DOM node.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {string} engineName - Chosen OCR engine identifier.
 */
async function acceptOcrOutput(nodeId, engineName) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const data = window.pendingOcrResultsMap && window.pendingOcrResultsMap[nodeId];
    const engRes = (data && data.results && data.results[engineName]) ? data.results[engineName] : (data || {});
    const chosenText = txtElem ? txtElem.value : (engRes.text || '');
    const chosenConf = engRes.confidence || 0.0;

    if (!node.content) node.content = {};
    node.content.raw_text = chosenText;
    node.user_correction_note = chosenText;
    node.ocr_confidence = chosenConf;
    node.is_incorrect_text = false;

    dismissOcrPrompt(nodeId);

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();
    await saveAnnotations(true);

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.className = 'status-banner';
        banner.style.display = 'block';
        banner.textContent = `Accepted '${engineName}' OCR output for section '${nodeId}'.`;
        setTimeout(() => { banner.style.display = 'none'; }, 5000);
    }
}

/**
 * Dismisses OCR review prompt without modifying node text.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function dismissOcrPrompt(nodeId) {
    if (window.pendingOcrResultsMap) {
        delete window.pendingOcrResultsMap[nodeId];
    }
    const container = document.getElementById(`ocrPromptContainer_${nodeId}`);
    if (container) {
        container.style.display = 'none';
        container.innerHTML = '';
    }
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.textContent = `OCR output dismissed for section '${nodeId}'.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}
