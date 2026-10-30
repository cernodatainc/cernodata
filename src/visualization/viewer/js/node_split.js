/**
 * src/visualization/viewer/js/node_split.js
 *
 * Interactive DOM node splitting at text cursor or newline offsets.
 * Divides merged paragraphs/headings vertically and updates annotations.
 */

/**
 * Splits the selected DOM node into two vertically stacked elements
 * at the current cursor position in .note-area (or at the first newline).
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
async function splitSelectedDOMNode(nodeId) {
    if (!domData || !domData.nodes) return;
    const targetId = nodeId || selectedNodeId;
    if (!targetId) return;

    const node = domData.nodes.find(n => n.node_id === targetId);
    if (!node) return;

    const rawText = String(
        (node.content && node.content.raw_text) ? node.content.raw_text : (node.user_correction_note || '')
    );
    if (!rawText || rawText.length < 2) {
        const banner = document.getElementById('statusBanner');
        if (banner) {
            banner.className = 'status-banner';
            banner.style.display = 'block';
            banner.textContent = '[WARN] Cannot split: text is too short or empty.';
            setTimeout(() => { banner.style.display = 'none'; }, 3000);
        }
        return;
    }

    // Determine split character index from textarea cursor or first newline
    let splitOffset = -1;
    const noteArea = document.querySelector('.note-area');
    if (noteArea && typeof noteArea.selectionStart === 'number') {
        const sel = noteArea.selectionStart;
        if (sel > 0 && sel < noteArea.value.length) {
            splitOffset = sel;
        }
    }

    if (splitOffset <= 0 || splitOffset >= rawText.length) {
        const nlIdx = rawText.indexOf('\n');
        if (nlIdx > 0 && nlIdx < rawText.length - 1) {
            splitOffset = nlIdx + 1;
        } else {
            splitOffset = Math.floor(rawText.length / 2);
        }
    }

    const text1 = rawText.slice(0, splitOffset).replace(/[\r\n]+$/, '');
    const text2 = rawText.slice(splitOffset).replace(/^[\r\n]+/, '');

    const totalLen = (text1.length + text2.length) || 1;
    const ratio = Math.max(0.1, Math.min(0.9, text1.length / totalLen));

    const bbox = node.bounding_box || { x0: 0, y0: 0, x1: 100, y1: 100 };
    const yMid = Math.round((bbox.y0 + (bbox.y1 - bbox.y0) * ratio) * 100) / 100;

    const bbox1 = {
        x0: bbox.x0,
        y0: bbox.y0,
        x1: bbox.x1,
        y1: yMid,
        angle: bbox.angle || 0,
        quad: null
    };

    const bbox2 = {
        x0: bbox.x0,
        y0: yMid,
        x1: bbox.x1,
        y1: bbox.y1,
        angle: bbox.angle || 0,
        quad: null
    };

    const node1Id = `${node.node_id}_s1`;
    const node2Id = `${node.node_id}_s2`;

    const node1 = {
        ...JSON.parse(JSON.stringify(node)),
        node_id: node1Id,
        bounding_box: bbox1,
        content: { ...(node.content || {}), raw_text: text1 },
        user_correction_note: text1,
        is_custom: true,
        violations: []
    };

    const node2 = {
        ...JSON.parse(JSON.stringify(node)),
        node_id: node2Id,
        bounding_box: bbox2,
        content: { ...(node.content || {}), raw_text: text2 },
        user_correction_note: text2,
        is_custom: true,
        violations: []
    };

    const idx = domData.nodes.findIndex(n => n.node_id === targetId);
    if (idx === -1) return;

    const origNode = JSON.parse(JSON.stringify(node));
    const beforeSel = {
        selectedNodeId: (typeof selectedNodeId !== 'undefined' ? selectedNodeId : null),
        selectedNodeIds: (typeof selectedNodeIds !== 'undefined' ? [...selectedNodeIds] : [])
    };

    domData.nodes.splice(idx, 1, node1, node2);
    selectedNodeId = node1Id;
    selectedNodeIds = [node1Id];

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'split_node',
            description: `Split element '${targetId}' into '${node1Id}' and '${node2Id}'`,
            page: getNodePage(origNode),
            removed: [{ index: idx, node: origNode }],
            inserted: [
                { index: idx, node: JSON.parse(JSON.stringify(node1)) },
                { index: idx + 1, node: JSON.parse(JSON.stringify(node2)) }
            ],
            beforeSelection: beforeSel,
            afterSelection: { selectedNodeId: node1Id, selectedNodeIds: [node1Id] },
            meta: { split_from: targetId, split_into: [node1Id, node2Id] }
        });
    }

    renderDOMTree();
    renderSelectedEditor();
    renderSVGOverlays();

    if (typeof saveAnnotations === 'function') {
        await saveAnnotations(true);
    }

    if (typeof showStatusBanner === 'function') {
        showStatusBanner(`Split element '${targetId}' into '${node1Id}' and '${node2Id}'. Persisted.`, 'success', 3000);
    }
}
