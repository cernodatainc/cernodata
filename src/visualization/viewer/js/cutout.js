/**
 * src/visualization/viewer/js/cutout.js
 *
 * Image crop preview, polygon vertex extraction, affine warping unskew transformations,
 * and targeted section OCR re-parsing.
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

        const d0 = { x: 0, y: 0 };
        const d1 = { x: dstW, y: 0 };
        const d2 = { x: dstW, y: dstH };
        const d3 = { x: 0, y: dstH };

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

async function triggerCutoutSecondPass(nodeId) {
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const banner = document.getElementById('statusBanner');
    const ocrBtn = document.getElementById(`btnCutoutOcr_${nodeId}`);
    if (ocrBtn) {
        ocrBtn.disabled = true;
        ocrBtn.textContent = '[OCR] Parsing...';
    }

    if (banner) {
        banner.style.display = 'block';
        banner.className = 'status-banner';
        banner.textContent = `[RUNNING] Parsing selected section '${nodeId}' with OCR...`;
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
        language: activeLanguage || 'en'
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
        const extractedText = data.text || '';
        const confPercent = Math.round((data.confidence || 0) * 100);

        if (!node.content) node.content = {};
        node.content.raw_text = extractedText;
        node.user_correction_note = extractedText;
        node.ocr_confidence = data.confidence;
        node.is_incorrect_text = false;

        renderDOMTree();
        renderSelectedEditor();
        renderSVGOverlays();

        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            const previewSnippet = extractedText.length > 50 ? extractedText.slice(0, 50) + '...' : extractedText;
            banner.textContent = `[OCR SUCCESS] Section '${nodeId}' parsed (${confPercent}% conf): "${previewSnippet || '(no text detected)'}"`;
            setTimeout(() => { banner.style.display = 'none'; }, 6000);
        }
    } catch (err) {
        console.error('Section OCR parse error:', err);
        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            banner.textContent = `[ERROR] Failed to parse section with OCR: ${err.message}`;
            setTimeout(() => { banner.style.display = 'none'; }, 6000);
        }
    } finally {
        if (ocrBtn) {
            ocrBtn.disabled = false;
            ocrBtn.textContent = '[OCR] Parse Section with OCR';
        }
    }
}
