/**
 * src/visualization/viewer/js/live_output.js
 *
 * Synchronous Live Output preview tab (TASK-709):
 * Renders real-time Markdown output and RAG chunk previews derived from the
 * active DocumentDOM, with bidirectional hover highlighting and click navigation
 * to canvas bounding boxes.
 */

let liveOutputViewMode = 'split';
let liveOutputPageOnly = false;
let hoveredLiveOutputNodeId = null;

/**
 * Resolves the current effective display text for a DOM node.
 *
 * @param {Object} node - DOM node record.
 * @returns {string} Effective text or Markdown content.
 */
function _resolveLiveNodeText(node) {
    if (!node) return '';
    if (typeof userCorrections === 'object' && userCorrections !== null && userCorrections[node.node_id]) {
        return String(userCorrections[node.node_id]);
    }
    if (node.corrected_text) return String(node.corrected_text);
    const content = node.content || {};
    if (node.type === 'table_grid') {
        if (content.markdown_table) return String(content.markdown_table);
        if (Array.isArray(content.rows) && content.rows.length > 0) {
            const hasExplicitHeaders = Array.isArray(content.headers) && content.headers.length > 0;
            const hdrs = hasExplicitHeaders ? content.headers : content.rows[0];
            const skipFirst = !hasExplicitHeaders || (
                content.rows[0].length === hdrs.length &&
                content.rows[0].every((val, idx) => String(val || '') === String(hdrs[idx] || ''))
            );
            const bodyRows = skipFirst ? content.rows.slice(1) : content.rows;
            const lines = [
                `| ${hdrs.join(' | ')} |`,
                `| ${hdrs.map(() => '---').join(' | ')} |`
            ];
            for (const row of bodyRows) {
                lines.push(`| ${(Array.isArray(row) ? row : []).join(' | ')} |`);
            }
            return lines.join('\n');
        }
    }
    if (node.type === 'figure') {
        return String(content.caption || content.raw_text || `[Figure ${node.node_id}]`);
    }
    return String(content.markdown_text || content.raw_text || content.caption || '');
}

/**
 * Formats a single DOM node into a Markdown block string.
 *
 * @param {Object} node - DOM node record.
 * @param {string} rawText - Resolved text content.
 * @returns {string} Markdown snippet.
 */
function _formatNodeMarkdown(node, rawText) {
    const clean = (rawText || '').trim();
    if (!clean) return '';
    if (node.type === 'heading') {
        const lvl = Math.max(1, Math.min(6, Number((node.content && node.content.heading_level) || 2)));
        return `${'#'.repeat(lvl)} ${clean.replace(/\s+/g, ' ')}`;
    }
    if (node.type === 'figure') {
        return `> [Figure] ${clean}`;
    }
    return clean;
}

/**
 * Builds synchronous Markdown sections and RAG chunks from current domData.
 *
 * @returns {{ fullMarkdown: string, blocks: Array<Object>, chunks: Array<Object> }}
 */
function buildLiveOutputPayload() {
    const nodes = (typeof domData !== 'undefined' && domData && Array.isArray(domData.nodes)) ? domData.nodes : [];
    const targetNodes = liveOutputPageOnly
        ? nodes.filter(n => (typeof getNodePage === 'function' ? getNodePage(n) : (n.global_page_index || 1)) === currentPage)
        : nodes;

    const headingStack = [];
    const blocks = [];
    const chunks = [];
    const mdSections = [];

    targetNodes.forEach((node, idx) => {
        const nodePage = typeof getNodePage === 'function' ? getNodePage(node) : (node.global_page_index || 1);
        const text = _resolveLiveNodeText(node);
        const mdBlock = _formatNodeMarkdown(node, text);
        if (!mdBlock) return;

        if (node.type === 'heading') {
            const lvl = Math.max(1, Math.min(6, Number((node.content && node.content.heading_level) || 2)));
            while (headingStack.length > 0 && headingStack[headingStack.length - 1].level >= lvl) {
                headingStack.pop();
            }
            headingStack.push({ level: lvl, title: text.replace(/\s+/g, ' ').trim() });
        }

        const headingPath = headingStack.map(h => h.title);
        mdSections.push(mdBlock);
        blocks.push({
            order: idx + 1,
            node_id: node.node_id,
            page: nodePage,
            type: node.type || 'paragraph',
            markdown: mdBlock,
            text
        });

        chunks.push({
            chunk_index: chunks.length + 1,
            node_id: node.node_id,
            page: nodePage,
            type: node.type || 'paragraph',
            heading_path: headingPath,
            text: mdBlock,
            char_count: mdBlock.length,
            token_estimate: Math.max(1, Math.ceil(mdBlock.split(/\s+/).filter(Boolean).length * 1.3))
        });
    });

    return {
        fullMarkdown: mdSections.join('\n\n'),
        blocks,
        chunks
    };
}

/**
 * Sets view mode for the Live Output panel ('split' | 'markdown' | 'chunks').
 *
 * @param {string} mode - Display mode.
 */
function setLiveOutputViewMode(mode) {
    liveOutputViewMode = mode || 'split';
    renderLiveOutput();
}

/**
 * Toggles filtering Live Output to active page vs full document.
 *
 * @param {boolean} pageOnly - True to show current page only.
 */
function toggleLiveOutputPageFilter(pageOnly) {
    liveOutputPageOnly = !!pageOnly;
    renderLiveOutput();
}

/**
 * Copies the complete synchronous Markdown output to clipboard.
 */
function copyLiveOutputMarkdown() {
    const payload = buildLiveOutputPayload();
    if (!payload.fullMarkdown) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(payload.fullMarkdown).then(() => {
            if (typeof showStatusBanner === 'function') {
                showStatusBanner('Copied Live Markdown output to clipboard.', 'success', 2000);
            }
        });
    }
}

/**
 * Highlights or unhighlights a DOM bounding box polygon during Live Output hover.
 *
 * @param {string} nodeId - Target node identifier.
 * @param {boolean} isActive - Whether hover highlight is active.
 */
function highlightLiveOutputNode(nodeId, isActive) {
    hoveredLiveOutputNodeId = isActive ? nodeId : null;
    document.querySelectorAll('#svgOverlay .live-hover-highlight').forEach(el => {
        el.classList.remove('live-hover-highlight');
    });
    document.querySelectorAll('.live-output-block.is-hovered, .live-rag-chunk.is-hovered').forEach(el => {
        el.classList.remove('is-hovered');
    });
    if (!isActive || !nodeId) return;

    const poly = document.getElementById(`svg-${nodeId}`);
    if (poly) {
        poly.classList.add('live-hover-highlight');
    }
    document.querySelectorAll(`[data-live-node-id="${nodeId}"]`).forEach(el => {
        el.classList.add('is-hovered');
    });
}

/**
 * Navigates to and selects the clicked Live Output node on the visual canvas.
 *
 * @param {string} nodeId - Target node identifier.
 */
function selectLiveOutputNode(nodeId) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;
    const nodePage = typeof getNodePage === 'function' ? getNodePage(node) : 1;
    if (typeof currentPage !== 'undefined' && nodePage !== currentPage && typeof switchPage === 'function') {
        switchPage(nodePage);
    }
    if (typeof handleNodeClick === 'function') {
        handleNodeClick(null, nodeId);
    }
    highlightLiveOutputNode(nodeId, true);
}

/**
 * Renders the synchronous Markdown and RAG chunk preview into #liveOutputContainer.
 */
function renderLiveOutput() {
    const container = document.getElementById('liveOutputContainer');
    if (!container) return;

    const { blocks, chunks } = buildLiveOutputPayload();

    const mdHtml = blocks.length > 0
        ? blocks.map(b => `
            <div class="live-output-block live-type-${escapeHtml(b.type)} ${hoveredLiveOutputNodeId === b.node_id ? 'is-hovered' : ''}"
                 data-live-node-id="${escapeHtml(b.node_id)}"
                 onmouseenter="highlightLiveOutputNode('${escapeHtml(b.node_id)}', true)"
                 onmouseleave="highlightLiveOutputNode('${escapeHtml(b.node_id)}', false)"
                 onclick="selectLiveOutputNode('${escapeHtml(b.node_id)}')">
                <div class="live-output-block-meta">
                    <span class="badge-status">P${b.page} #${b.order}</span>
                    <span>${escapeHtml(b.node_id)}</span>
                    <span class="node-type type-${escapeHtml(b.type)}">${escapeHtml(b.type)}</span>
                </div>
                <pre class="live-output-pre">${escapeHtml(b.markdown)}</pre>
            </div>
        `).join('')
        : '<div class="empty-state">No Markdown blocks available for current selection.</div>';

    const chunksHtml = chunks.length > 0
        ? chunks.map(ch => {
            const pathText = ch.heading_path.length > 0 ? ch.heading_path.join(' > ') : 'Document Root';
            return `
                <div class="live-rag-chunk ${hoveredLiveOutputNodeId === ch.node_id ? 'is-hovered' : ''}"
                     data-live-node-id="${escapeHtml(ch.node_id)}"
                     onmouseenter="highlightLiveOutputNode('${escapeHtml(ch.node_id)}', true)"
                     onmouseleave="highlightLiveOutputNode('${escapeHtml(ch.node_id)}', false)"
                     onclick="selectLiveOutputNode('${escapeHtml(ch.node_id)}')">
                    <div class="live-rag-chunk-header">
                        <span>Chunk #${ch.chunk_index} (P${ch.page})</span>
                        <span>~${ch.token_estimate} tok</span>
                    </div>
                    <div class="live-rag-breadcrumb">${escapeHtml(pathText)}</div>
                    <div class="live-rag-body">${escapeHtml(ch.text)}</div>
                </div>
            `;
        }).join('')
        : '<div class="empty-state">No RAG chunks generated yet.</div>';

    const showMd = liveOutputViewMode === 'split' || liveOutputViewMode === 'markdown';
    const showChunks = liveOutputViewMode === 'split' || liveOutputViewMode === 'chunks';

    container.innerHTML = `
        <div class="live-output-toolbar">
            <div class="live-output-modes">
                <button type="button" class="action-btn action-btn-decollide-sm ${liveOutputViewMode === 'split' ? 'active' : ''}" onclick="setLiveOutputViewMode('split')">Split</button>
                <button type="button" class="action-btn action-btn-decollide-sm ${liveOutputViewMode === 'markdown' ? 'active' : ''}" onclick="setLiveOutputViewMode('markdown')">Markdown</button>
                <button type="button" class="action-btn action-btn-decollide-sm ${liveOutputViewMode === 'chunks' ? 'active' : ''}" onclick="setLiveOutputViewMode('chunks')">RAG Chunks (${chunks.length})</button>
            </div>
            <div class="live-output-tools">
                <label class="live-output-page-toggle">
                    <input type="checkbox" ${liveOutputPageOnly ? 'checked' : ''} onchange="toggleLiveOutputPageFilter(this.checked)" />
                    <span>Page ${typeof currentPage !== 'undefined' ? currentPage : 1} only</span>
                </label>
                <button type="button" class="action-btn action-btn-decollide-sm" onclick="copyLiveOutputMarkdown()">Copy MD</button>
            </div>
        </div>
        <div class="live-output-sections">
            ${showMd ? `<div class="live-output-section"><div class="live-section-heading">Synchronous Markdown Preview</div><div id="liveMarkdownPreview" class="live-md-list">${mdHtml}</div></div>` : ''}
            ${showChunks ? `<div class="live-output-section"><div class="live-section-heading">RAG Chunks (${chunks.length})</div><div id="liveRagChunksPreview" class="live-chunk-list">${chunksHtml}</div></div>` : ''}
        </div>
    `;
}
