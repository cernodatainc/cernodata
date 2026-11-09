/**
 * src/visualization/viewer/js/table_modal.js
 *
 * Interactive Table DOM Node Modal Viewer.
 * Displays tabular content with row and column awareness:
 * - Rendered HTML Grid view with sticky headers and cell values
 * - Row-by-row view (row awareness with cell values)
 * - Column-by-column view (column awareness with column values)
 * - Markdown table source view with copy support
 */

let activeTableModalNodeId = null;
let activeTableModalTab = 'grid';
let isTableModalAdvanced = false;

/**
 * Parses client-side markdown table string if rows and columns were not pre-extracted.
 *
 * @param {string} mdText - Raw markdown table text.
 * @returns {Object} Parsed table structure { headers, rows, columns, numRows, numCols }.
 */
function parseClientMarkdownTable(mdText) {
    if (!mdText || typeof mdText !== 'string') {
        return { headers: [], rows: [], columns: [], numRows: 0, numCols: 0 };
    }
    const lines = mdText.split('\n').map(l => l.trim()).filter(l => l.includes('|'));
    if (lines.length === 0) {
        return { headers: [], rows: [], columns: [], numRows: 0, numCols: 0 };
    }

    const rawRows = [];
    let sepIdx = -1;

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        if (line.startsWith('|')) line = line.substring(1);
        if (line.endsWith('|')) line = line.substring(0, line.length - 1);
        const cells = line.split('|').map(c => c.trim().replace(/\\\|/g, '|'));
        const isSep = cells.length > 0 && cells.every(c => /^:?-+:?$/.test(c));
        if (isSep && sepIdx === -1) {
            sepIdx = i;
            continue;
        }
        rawRows.push(cells);
    }

    if (rawRows.length === 0) {
        return { headers: [], rows: [], columns: [], numRows: 0, numCols: 0 };
    }

    const headers = (sepIdx > 0 || rawRows.length > 1) ? [...rawRows[0]] : [];
    const maxCols = Math.max(...rawRows.map(r => r.length), 0);
    const columns = [];
    for (let c = 0; c < maxCols; c++) {
        columns.push(rawRows.map(r => (c < r.length ? r[c] : '')));
    }

    return {
        headers,
        rows: rawRows,
        columns,
        numRows: rawRows.length,
        numCols: maxCols
    };
}

/**
 * Extracts normalized table representation from a target DOM node.
 *
 * @param {Object} node - Target DOM node.
 * @returns {Object} Normalized table payload.
 */
function extractNodeTableData(node) {
    const content = node.content || {};
    let rows = Array.isArray(content.rows) ? content.rows : [];
    let columns = Array.isArray(content.columns) ? content.columns : [];
    let headers = Array.isArray(content.headers) ? content.headers : [];
    let numRows = content.num_rows || rows.length;
    let numCols = content.num_cols || (columns.length || (rows[0] ? rows[0].length : 0));
    let markdownTable = content.markdown_table || '';
    let tableTitle = content.title || '';
    const score = (content.cell_alignment_score !== undefined) ? content.cell_alignment_score : 1.0;
    const isConsistent = (content.is_consistent !== undefined)
        ? content.is_consistent
        : (new Set(rows.map(r => (Array.isArray(r) ? r.length : 0))).size <= 1);

    if (rows.length === 0 && (markdownTable || content.raw_text)) {
        const text = markdownTable || content.raw_text;
        const parsed = parseClientMarkdownTable(text);
        if (parsed.rows.length > 0) {
            rows = parsed.rows;
            columns = parsed.columns;
            headers = parsed.headers;
            numRows = parsed.numRows;
            numCols = parsed.numCols;
        }
    }

    // Detect if headers represent a repeated spanning title banner across all columns
    const cleanHdrs = headers.map(h => (h || '').trim()).filter(Boolean);
    if (cleanHdrs.length > 1 && new Set(cleanHdrs).size === 1 && rows.length > 1) {
        if (!tableTitle) tableTitle = cleanHdrs[0];
        const r0Clean = (rows[0] || []).map(c => (c || '').trim()).filter(Boolean);
        if (r0Clean.length > 0 && new Set(r0Clean).size === 1 && r0Clean[0] === cleanHdrs[0] && rows.length > 1) {
            const r1Clean = (rows[1] || []).map(c => (c || '').trim()).filter(Boolean);
            if (new Set(r1Clean).size > 1) {
                headers = [...rows[1]];
                rows = rows.slice(1);
                numRows = rows.length;
                columns = [];
                for (let c = 0; c < numCols; c++) {
                    columns.push(rows.map(r => (c < r.length ? r[c] : '')));
                }
            }
        }
    }

    if (headers.length === 0 && rows.length > 0) {
        headers = rows[0].map((_, idx) => `Col ${idx + 1}`);
    }

    return { rows, columns, headers, numRows, numCols, markdownTable, score, isConsistent, tableTitle };
}

/**
 * Opens the Table Content Modal for a target DOM node.
 *
 * @param {string} nodeId - Target DOM node identifier.
 */
function openTableModal(nodeId) {
    if (!domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === nodeId);
    if (!node) return;

    activeTableModalNodeId = nodeId;
    activeTableModalTab = 'grid';

    let overlay = document.getElementById('tableModalOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'tableModalOverlay';
        overlay.className = 'table-modal-overlay';
        overlay.onclick = function(e) {
            if (e.target === overlay) {
                closeTableModal();
            }
        };
        document.body.appendChild(overlay);

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && activeTableModalNodeId) {
                closeTableModal();
            }
        });
    }

    renderTableModal(node);
    overlay.classList.remove('hidden');
    overlay.style.display = 'flex';
}

/**
 * Closes the Table Content Modal.
 */
function closeTableModal() {
    activeTableModalNodeId = null;
    const overlay = document.getElementById('tableModalOverlay');
    if (overlay) {
        overlay.classList.add('hidden');
        overlay.style.display = 'none';
    }
}

/**
 * Switches the active view tab inside the table modal.
 *
 * @param {string} tabName - 'grid' | 'rows' | 'columns' | 'markdown'
 */
function switchTableModalTab(tabName) {
    activeTableModalTab = tabName;
    if (!activeTableModalNodeId || !domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === activeTableModalNodeId);
    if (node) {
        renderTableModal(node);
    }
}

/**
 * Copies the raw markdown table text to the user clipboard.
 */
function copyTableModalMarkdown() {
    const codeEl = document.getElementById('tableModalMarkdownCode');
    const text = codeEl ? codeEl.innerText : '';
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            const btn = document.getElementById('btnCopyTableMarkdown');
            if (btn) {
                const prev = btn.innerText;
                btn.innerText = 'Copied to clipboard';
                setTimeout(() => { btn.innerText = prev; }, 2000);
            }
        });
    }
}

/**
 * Renders the complete table modal content into the overlay container.
 *
 * @param {Object} node - Target DOM node.
 */
function renderTableModal(node) {
    const overlay = document.getElementById('tableModalOverlay');
    if (!overlay) return;

    const data = extractNodeTableData(node);
    const { rows, columns, headers, numRows, numCols, markdownTable, score, isConsistent, tableTitle } = data;

    const tabs = [
        { id: 'grid', label: 'Grid View' },
        { id: 'rows', label: `Row View (${numRows})` },
        { id: 'columns', label: `Column View (${numCols})` },
        { id: 'markdown', label: 'Markdown Source' }
    ];

    const tabsHtml = tabs.map(t => {
        const activeCls = (t.id === activeTableModalTab) ? 'active' : '';
        return `<button class="table-modal-tab-btn ${activeCls}" onclick="switchTableModalTab('${t.id}')">${escapeHtml(t.label)}</button>`;
    }).join('');

    let bodyHtml = '';
    if (activeTableModalTab === 'grid') {
        bodyHtml = renderTableModalGridView(rows, headers, numCols);
    } else if (activeTableModalTab === 'rows') {
        bodyHtml = renderTableModalRowsView(rows, headers);
    } else if (activeTableModalTab === 'columns') {
        bodyHtml = renderTableModalColumnsView(columns, headers);
    } else {
        bodyHtml = renderTableModalMarkdownView(markdownTable);
    }

    const scoreColor = (score >= 0.80) ? 'var(--ui-green)' : (score >= 0.60 ? 'var(--ui-yellow)' : 'var(--ui-red)');
    const consistencyBadge = isConsistent
        ? '<span class="badge-status" style="background:var(--ui-green-bg); color:var(--ui-green); border-color:var(--ui-green-border);">Consistent</span>'
        : '<span class="badge-status" style="background:var(--ui-yellow-bg); color:var(--ui-yellow); border-color:var(--ui-yellow-border);">Ragged Columns</span>';

    const titleBannerHtml = tableTitle ? `
        <div class="table-modal-title-banner">
            <span class="table-modal-title-badge">Table Title</span>
            <span class="table-modal-title-text">${escapeHtml(tableTitle)}</span>
        </div>
    ` : '';

    const customFlagsVal = (node.content && node.content.table_custom_flags) ? String(node.content.table_custom_flags) : '';
    const advancedBarHtml = isTableModalAdvanced ? `
        <div class="table-modal-advanced-bar" id="tableModalAdvancedBar">
            <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-weight:600; color:var(--ui-text);">Header row:</span>
                <select id="selTableModalHeaderRow" style="font-size:11px; padding:2px 6px;">
                    <option value="auto">Auto-detect</option>
                    <option value="1">Row #1 (Column headers)</option>
                    <option value="0">Row #0 (Banner/Title)</option>
                    <option value="2">Row #2</option>
                </select>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-weight:600; color:var(--ui-text);">Banner:</span>
                <select id="selTableModalStripBanner" style="font-size:11px; padding:2px 6px;">
                    <option value="strip">Auto-strip title banner</option>
                    <option value="keep">Keep in data rows</option>
                </select>
            </div>
            <div style="display:flex; align-items:center; gap:6px; flex:1; min-width:160px;">
                <span style="font-weight:600; color:var(--ui-text);">Flags:</span>
                <input type="text" id="inpTableModalFlags" value="${escapeHtml(customFlagsVal)}" placeholder="e.g. --delimiter=| --align-score=0.85" style="flex:1; font-family:monospace; font-size:11px; padding:2px 6px; border:1px solid var(--ui-border); border-radius:3px;" />
            </div>
            <button class="action-btn action-btn-decollide-sm" onclick="reparseTableModal()" style="font-weight:600; background:var(--ui-text); color:#FFFFFF;">Re-parse Table</button>
        </div>
    ` : '';

    overlay.innerHTML = `
        <div class="table-modal-dialog">
            <div class="table-modal-header">
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span style="font-size:14px; font-weight:700; color:var(--ui-text);">Table: <span style="font-family:var(--font-mono); font-weight:500;">${escapeHtml(node.node_id)}</span></span>
                    <span class="badge-status" style="background:var(--ui-blue-bg); color:var(--ui-blue); border-color:var(--ui-blue-border);">P${node.global_page_index || 1}</span>
                    <span class="badge-status" style="background:var(--ui-bg-card); border-color:var(--ui-border); color:var(--ui-text);">${numRows} rows × ${numCols} cols</span>
                    <span class="badge-status" style="background:var(--ui-bg-card); border-color:var(--ui-border); color:${scoreColor};">Score: ${Number(score).toFixed(2)}</span>
                    ${consistencyBadge}
                </div>
                <button class="action-btn action-btn-decollide-sm" onclick="closeTableModal()" title="Close (Escape)">Close [X]</button>
            </div>
            <div class="table-modal-tabs">
                <div class="table-modal-tab-group">
                    ${tabsHtml}
                </div>
                <!-- TODO(TASK-707): Mirrored advanced mode table re-parsing with custom header index, delimiter, and layout flags. -->
                <label style="display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600; color:var(--ui-text); cursor:pointer;">
                    <input type="checkbox" id="chkTableModalAdvanced" ${isTableModalAdvanced ? 'checked' : ''} onchange="toggleTableModalAdvanced(this.checked)" />
                    <span>Advanced mode (table flags)</span>
                </label>
            </div>
            ${advancedBarHtml}
            <div class="table-modal-body">
                ${titleBannerHtml}
                ${bodyHtml}
            </div>
            <div class="table-modal-footer">
                <span style="font-size:11px; color:var(--ui-text-muted);">Total cells: ${numRows * numCols} | Alignment score: ${Number(score).toFixed(4)}</span>
                <button class="action-btn action-btn-decollide-sm" onclick="closeTableModal()">Close viewer</button>
            </div>
        </div>
    `;
}

/**
 * Toggles visibility of advanced mode table parsing options.
 */
function toggleTableModalAdvanced(checked) {
    isTableModalAdvanced = !!checked;
    if (!activeTableModalNodeId || !domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === activeTableModalNodeId);
    if (node) renderTableModal(node);
}

/**
 * Re-evaluates table structure using selected advanced options and custom flags.
 */
function reparseTableModal() {
    if (!activeTableModalNodeId || !domData || !domData.nodes) return;
    const node = domData.nodes.find(n => n.node_id === activeTableModalNodeId);
    if (!node || !node.content) return;
    const selHdr = document.getElementById('selTableModalHeaderRow');
    const selStrip = document.getElementById('selTableModalStripBanner');
    const inpFlags = document.getElementById('inpTableModalFlags');
    const hdrVal = selHdr ? selHdr.value : 'auto';
    const stripVal = selStrip ? selStrip.value : 'strip';
    const flagsVal = inpFlags ? inpFlags.value.trim() : '';

    let rows = Array.isArray(node.content.rows) ? [...node.content.rows] : [];
    if (rows.length > 0) {
        if (hdrVal === '1' && rows.length > 1) {
            const r0Clean = rows[0].map(c => (c || '').trim()).filter(Boolean);
            if (r0Clean.length > 0 && new Set(r0Clean).size === 1) {
                node.content.title = r0Clean[0];
            }
            node.content.headers = [...rows[1]];
            if (stripVal === 'strip') {
                node.content.rows = rows.slice(1);
                node.content.num_rows = node.content.rows.length;
            }
        } else if (hdrVal === '0') {
            node.content.headers = [...rows[0]];
        }
        if (flagsVal) {
            node.content.table_custom_flags = flagsVal;
        }
    }
    renderTableModal(node);
    renderSelectedEditor();
}

/**
 * Renders the interactive HTML table grid view.
 */
function renderTableModalGridView(rows, headers, numCols) {
    if (!rows || rows.length === 0) {
        return '<div class="table-empty-message">No table rows found in DOM node content.</div>';
    }

    const maxCols = Math.max(numCols, (headers ? headers.length : 0), ...rows.map(r => (Array.isArray(r) ? r.length : 0)));
    const headerCols = [];
    for (let c = 0; c < maxCols; c++) {
        const title = (headers && c < headers.length && headers[c]) ? headers[c] : `Column ${c + 1}`;
        headerCols.push(`<th>${escapeHtml(title)}</th>`);
    }

    const dataRows = (headers && rows.length > 1 && rows[0].every((val, idx) => val === headers[idx]))
        ? rows.slice(1)
        : rows;

    const rowTrs = dataRows.map((r, rIdx) => {
        const cells = [];
        for (let c = 0; c < maxCols; c++) {
            const val = (Array.isArray(r) && c < r.length) ? r[c] : '';
            cells.push(`<td>${escapeHtml(val)}</td>`);
        }
        return `<tr><td class="table-modal-row-idx">#${rIdx + 1}</td>${cells.join('')}</tr>`;
    }).join('');

    return `
        <div class="table-modal-grid-container">
            <table class="table-modal-grid-table">
                <thead>
                    <tr>
                        <th class="table-modal-row-idx">#</th>
                        ${headerCols.join('')}
                    </tr>
                </thead>
                <tbody>
                    ${rowTrs}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Renders the row-oriented view.
 */
function renderTableModalRowsView(rows, headers) {
    if (!rows || rows.length === 0) {
        return '<div class="table-empty-message">No table rows available.</div>';
    }

    return rows.map((r, rIdx) => {
        const rowCells = Array.isArray(r) ? r : [];
        const isHeader = (rIdx === 0 && headers && headers.length > 0 && rowCells.every((val, idx) => val === headers[idx]));
        const cellsHtml = rowCells.map((val, cIdx) => {
            const colName = (headers && cIdx < headers.length) ? headers[cIdx] : `Col ${cIdx + 1}`;
            return `
                <div class="table-modal-cell-pill">
                    <span class="table-modal-cell-col-label">${escapeHtml(colName)}</span>
                    <span class="table-modal-cell-value">${escapeHtml(val || '(empty)')}</span>
                </div>
            `;
        }).join('');

        return `
            <div class="table-modal-row-card ${isHeader ? 'is-header-card' : ''}">
                <div class="table-modal-row-card-header">
                    <span>Row #${rIdx + 1} ${isHeader ? '(Header Row)' : ''}</span>
                    <span style="font-size:11px; color:var(--ui-text-muted);">${rowCells.length} cells</span>
                </div>
                <div class="table-modal-row-card-cells">
                    ${cellsHtml}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Renders the column-oriented view.
 */
function renderTableModalColumnsView(columns, headers) {
    if (!columns || columns.length === 0) {
        return '<div class="table-empty-message">No table columns available.</div>';
    }

    return columns.map((col, cIdx) => {
        const colVals = Array.isArray(col) ? col : [];
        const colTitle = (headers && cIdx < headers.length) ? headers[cIdx] : `Column ${cIdx + 1}`;
        const itemsHtml = colVals.map((val, rIdx) => `
            <div class="table-modal-col-val-item">
                <span class="table-modal-col-val-row-idx">R${rIdx + 1}</span>
                <span class="table-modal-col-val-text">${escapeHtml(val || '(empty)')}</span>
            </div>
        `).join('');

        return `
            <div class="table-modal-col-card">
                <div class="table-modal-col-card-header">
                    <span>Column #${cIdx + 1}: ${escapeHtml(colTitle)}</span>
                    <span style="font-size:11px; color:var(--ui-text-muted);">${colVals.length} values</span>
                </div>
                <div class="table-modal-col-card-body">
                    ${itemsHtml}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Renders the markdown source view.
 */
function renderTableModalMarkdownView(markdownTable) {
    if (!markdownTable) {
        return '<div class="table-empty-message">No markdown representation available for this table.</div>';
    }

    return `
        <div style="display:flex; justify-content:flex-end; margin-bottom:8px;">
            <button class="action-btn action-btn-decollide-sm" id="btnCopyTableMarkdown" onclick="copyTableModalMarkdown()">Copy markdown</button>
        </div>
        <pre class="table-modal-code-block"><code id="tableModalMarkdownCode">${escapeHtml(markdownTable)}</code></pre>
    `;
}
