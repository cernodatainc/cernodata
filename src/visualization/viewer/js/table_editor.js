/**
 * src/visualization/viewer/js/table_editor.js
 *
 * Inline interactive HTML table cell, row, and column editor mounted in the
 * inspector panel when the selected node has type === 'table_grid'.
 */

/**
 * Normalizes and extracts mutable headers and rows from a table_grid node.
 *
 * @param {Object} node - DOM node of type table_grid.
 * @returns {{ headers: string[], rows: string[][], numCols: number }} Normalized table state.
 */
function _getEditableTableState(node) {
    const content = node && node.content ? node.content : {};
    let rows = Array.isArray(content.rows)
        ? content.rows.map(r => (Array.isArray(r) ? r.map(c => String(c || '')) : []))
        : [];
    let headers = Array.isArray(content.headers)
        ? content.headers.map(h => String(h || ''))
        : [];

    if (rows.length === 0 && typeof parseClientMarkdownTable === 'function') {
        const mdSource = content.markdown_table || content.raw_text || '';
        const parsed = parseClientMarkdownTable(mdSource);
        if (parsed.rows.length > 0) {
            rows = parsed.rows.map(r => r.map(c => String(c || '')));
            if (headers.length === 0 && Array.isArray(parsed.headers)) {
                headers = parsed.headers.map(h => String(h || ''));
            }
        }
    }

    const numCols = Math.max(
        headers.length,
        rows.reduce((acc, r) => Math.max(acc, r.length), 0),
        1
    );

    if (headers.length === 0) {
        if (rows.length > 0) {
            headers = rows[0].slice();
        } else {
            headers = Array.from({ length: numCols }, (_, i) => `Col ${i + 1}`);
        }
    }
    while (headers.length < numCols) {
        headers.push(`Col ${headers.length + 1}`);
    }

    rows = rows.map(r => {
        const padded = r.slice(0, numCols);
        while (padded.length < numCols) padded.push('');
        return padded;
    });

    if (rows.length === 0) {
        rows = [headers.slice()];
    }

    return { headers, rows, numCols };
}

function _snapshotTableNode(node) {
    return {
        content: node && node.content ? JSON.parse(JSON.stringify(node.content)) : {},
        nodeState: {
            is_corrected: !!(node && node.is_corrected),
            corrected_text: (node && node.corrected_text) ? node.corrected_text : null,
            user_correction_note: (node && node.user_correction_note) ? node.user_correction_note : ''
        }
    };
}

/**
 * Serializes edited rows and headers into markdown and updates DOM node fields.
 *
 * @param {Object} node - DOM node to mutate.
 * @param {string[]} headers - Column headers.
 * @param {string[][]} rows - All table rows.
 * @param {Object|null} prevSnapshot - Snapshot prior to edit for undo stack.
 * @param {string} actionDesc - Description for undo diff history.
 */
function _commitTableEdit(node, headers, rows, prevSnapshot, actionDesc) {
    if (!node) return;
    if (!node.content || typeof node.content !== 'object') {
        node.content = {};
    }
    if (node.content._raw_text_snapshot === undefined && typeof node.content.raw_text === 'string') {
        node.content._raw_text_snapshot = node.content.raw_text;
    }

    const numCols = Math.max(
        headers.length,
        rows.reduce((acc, r) => Math.max(acc, r.length), 0),
        1
    );
    const normHeaders = headers.slice(0, numCols).map(h => String(h || ''));
    while (normHeaders.length < numCols) {
        normHeaders.push(`Col ${normHeaders.length + 1}`);
    }

    const normRows = rows.map(r => {
        const out = r.slice(0, numCols).map(c => String(c || ''));
        while (out.length < numCols) out.push('');
        return out;
    });

    const columns = [];
    for (let c = 0; c < numCols; c++) {
        columns.push(normRows.map(r => r[c] || ''));
    }

    const escapeCell = val => String(val || '').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
    const mdLines = [
        `| ${normHeaders.map(escapeCell).join(' | ')} |`,
        `| ${normHeaders.map(() => '---').join(' | ')} |`
    ];
    const skipFirst = normRows.length > 0 && normRows[0].every((val, idx) => val === normHeaders[idx]);
    const bodyRows = skipFirst ? normRows.slice(1) : normRows;
    for (const row of bodyRows) {
        mdLines.push(`| ${row.map(escapeCell).join(' | ')} |`);
    }
    const markdownTable = mdLines.join('\n');

    node.content.headers = normHeaders;
    node.content.rows = normRows;
    node.content.columns = columns;
    node.content.num_rows = normRows.length;
    node.content.num_cols = numCols;
    node.content.markdown_table = markdownTable;
    node.content.raw_text = markdownTable;
    node.content.cell_alignment_score = 1.0;
    node.content.is_consistent = true;
    node.is_corrected = true;
    node.corrected_text = markdownTable;
    node.user_correction_note = markdownTable;

    if (typeof userCorrections === 'object' && userCorrections !== null) {
        userCorrections[node.node_id] = markdownTable;
    }

    const prevContent = prevSnapshot && prevSnapshot.content !== undefined ? prevSnapshot.content : prevSnapshot;
    const prevNodeState = prevSnapshot && prevSnapshot.nodeState ? prevSnapshot.nodeState : null;
    if (prevContent && typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'table_edit',
            description: actionDesc || `Edit table ${node.node_id}`,
            page: typeof getNodePage === 'function' ? getNodePage(node) : 1,
            meta: {
                node_id: node.node_id,
                before_content: prevContent,
                after_content: JSON.parse(JSON.stringify(node.content)),
                before_node_state: prevNodeState,
                after_node_state: {
                    is_corrected: true,
                    corrected_text: markdownTable,
                    user_correction_note: markdownTable
                }
            }
        });
    }

    if (typeof renderDOMTree === 'function') renderDOMTree();
    if (typeof renderLiveOutput === 'function') renderLiveOutput();
    if (activeTableModalNodeId === node.node_id && typeof renderTableModal === 'function') {
        renderTableModal(node);
    }
    if (typeof saveAnnotations === 'function') saveAnnotations(true);
}

/**
 * Updates a single header cell value on a table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 * @param {number} colIdx - Column index.
 * @param {string} value - Updated header value.
 * @param {boolean} [rerender=false] - Whether to re-render the inspector.
 */
function updateTableHeaderCell(nodeId, colIdx, value, rerender = false) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows } = _getEditableTableState(node);
    if (colIdx < 0 || colIdx >= headers.length) return;

    const oldHeader = headers[colIdx];
    headers[colIdx] = String(value || '');
    if (rows.length > 0 && rows[0][colIdx] === oldHeader) {
        rows[0][colIdx] = String(value || '');
    }

    _commitTableEdit(node, headers, rows, prevSnap, `Edit table header (${nodeId} col ${colIdx + 1})`);
    if (rerender && typeof renderSelectedEditor === 'function') {
        renderSelectedEditor();
    } else {
        const noteEl = document.querySelector('#editorContent textarea.note-area');
        if (noteEl) noteEl.value = node.content.markdown_table || '';
    }
}

/**
 * Updates a body cell value on a table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 * @param {number} rowIdx - Row index in node.content.rows.
 * @param {number} colIdx - Column index.
 * @param {string} value - Updated cell text.
 */
function updateTableCell(nodeId, rowIdx, colIdx, value) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows } = _getEditableTableState(node);
    if (rowIdx < 0 || rowIdx >= rows.length || colIdx < 0 || colIdx >= headers.length) return;

    const isFirstRowHeader = rowIdx === 0
        && node.content
        && Array.isArray(node.content.headers)
        && node.content.headers.length === rows[0].length
        && rows[0].every((val, idx) => val === headers[idx]);

    rows[rowIdx][colIdx] = String(value || '');
    if (isFirstRowHeader) {
        headers[colIdx] = String(value || '');
    }

    _commitTableEdit(node, headers, rows, prevSnap, `Edit table cell (${nodeId} R${rowIdx + 1}C${colIdx + 1})`);
    const noteEl = document.querySelector('#editorContent textarea.note-area');
    if (noteEl) noteEl.value = node.content.markdown_table || '';
}

/**
 * Appends a new blank row to the table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 */
function addTableRow(nodeId) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows, numCols } = _getEditableTableState(node);
    rows.push(Array.from({ length: numCols }, () => ''));

    _commitTableEdit(node, headers, rows, prevSnap, `Add row to table ${nodeId}`);
    if (typeof renderSelectedEditor === 'function') renderSelectedEditor();
}

/**
 * Removes a row by index from the table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 * @param {number} rowIdx - Row index to remove.
 */
function deleteTableRow(nodeId, rowIdx) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows } = _getEditableTableState(node);
    if (rows.length <= 1) {
        if (typeof showStatusBanner === 'function') {
            showStatusBanner('Table must retain at least 1 row.', 'warning', 2000);
        }
        return;
    }
    if (rowIdx < 0 || rowIdx >= rows.length) return;
    rows.splice(rowIdx, 1);

    _commitTableEdit(node, headers, rows, prevSnap, `Delete row ${rowIdx + 1} from ${nodeId}`);
    if (typeof renderSelectedEditor === 'function') renderSelectedEditor();
}

/**
 * Appends a new column to the table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 */
function addTableColumn(nodeId) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows, numCols } = _getEditableTableState(node);
    const prevHeaderMatch = rows.length > 0 && rows[0].length === headers.length && rows[0].every((v, c) => v === headers[c]);
    const newHeader = `Col ${numCols + 1}`;
    headers.push(newHeader);
    const updatedRows = rows.map((r, idx) => [...r, idx === 0 && prevHeaderMatch ? newHeader : '']);

    _commitTableEdit(node, headers, updatedRows, prevSnap, `Add column to table ${nodeId}`);
    if (typeof renderSelectedEditor === 'function') renderSelectedEditor();
}

/**
 * Removes a column by index from the table_grid node.
 *
 * @param {string} nodeId - Target node identifier.
 * @param {number} colIdx - Column index to remove.
 */
function deleteTableColumn(nodeId, colIdx) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const prevSnap = _snapshotTableNode(node);
    const { headers, rows } = _getEditableTableState(node);
    if (headers.length <= 1) {
        if (typeof showStatusBanner === 'function') {
            showStatusBanner('Table must retain at least 1 column.', 'warning', 2000);
        }
        return;
    }
    if (colIdx < 0 || colIdx >= headers.length) return;
    headers.splice(colIdx, 1);
    const updatedRows = rows.map(r => {
        const copy = r.slice();
        copy.splice(colIdx, 1);
        return copy;
    });

    _commitTableEdit(node, headers, updatedRows, prevSnap, `Delete column ${colIdx + 1} from ${nodeId}`);
    if (typeof renderSelectedEditor === 'function') renderSelectedEditor();
}

/**
 * Renders an inline interactive HTML cell/row/column editor for table_grid nodes.
 *
 * @param {Object} node - Target table_grid DOM node.
 * @returns {string} HTML markup for the table editor widget.
 */
function renderTableEditorComponent(node) {
    if (!node || node.type !== 'table_grid') return '';

    const { headers, rows, numCols } = _getEditableTableState(node);
    const safeNodeId = escapeHtml(node.node_id);

    const headerCellsHtml = headers.map((hdr, cIdx) => `
        <th>
            <div class="table-editor-hdr-cell">
                <input type="text" class="table-editor-input table-editor-input-hdr"
                       value="${escapeHtml(hdr)}"
                       aria-label="Header column ${cIdx + 1}"
                       oninput="updateTableHeaderCell('${safeNodeId}', ${cIdx}, this.value)" />
                <button type="button" class="table-editor-del-btn"
                        onclick="deleteTableColumn('${safeNodeId}', ${cIdx})"
                        title="Delete column ${cIdx + 1}">x</button>
            </div>
        </th>
    `).join('');

    const bodyRowsHtml = rows.map((row, rIdx) => {
        const tds = [];
        for (let cIdx = 0; cIdx < numCols; cIdx++) {
            const val = (cIdx < row.length) ? row[cIdx] : '';
            tds.push(`
                <td>
                    <input type="text" class="table-editor-input"
                           value="${escapeHtml(val)}"
                           aria-label="Row ${rIdx + 1} Column ${cIdx + 1}"
                           oninput="updateTableCell('${safeNodeId}', ${rIdx}, ${cIdx}, this.value)" />
                </td>
            `);
        }
        return `
            <tr>
                <td class="table-editor-row-ctrl">
                    <span>#${rIdx + 1}</span>
                    <button type="button" class="table-editor-del-btn"
                            onclick="deleteTableRow('${safeNodeId}', ${rIdx})"
                            title="Delete row ${rIdx + 1}">x</button>
                </td>
                ${tds.join('')}
            </tr>
        `;
    }).join('');

    return `
        <div class="table-editor-panel" id="tableEditorPanel_${safeNodeId}">
            <div class="table-editor-toolbar">
                <span class="table-editor-title">Interactive Table Editor (${rows.length}x${numCols})</span>
                <div class="table-editor-actions">
                    <button type="button" class="action-btn action-btn-decollide-sm" onclick="addTableRow('${safeNodeId}')">+ Row</button>
                    <button type="button" class="action-btn action-btn-decollide-sm" onclick="addTableColumn('${safeNodeId}')">+ Col</button>
                </div>
            </div>
            <div class="table-editor-scroll">
                <table class="table-editor-grid">
                    <thead>
                        <tr>
                            <th class="table-editor-row-ctrl">#</th>
                            ${headerCellsHtml}
                        </tr>
                    </thead>
                    <tbody>
                        ${bodyRowsHtml}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}
