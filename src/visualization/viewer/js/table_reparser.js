/**
 * src/visualization/viewer/js/table_reparser.js
 *
 * Client-side table re-parsing utilities for custom header row selection,
 * title banner stripping, delimiter splitting, and alignment score computation.
 */

/**
 * Parses advanced table re-parsing flags (--delimiter, --header, --trim, --skip-empty, --align-score).
 *
 * @param {string} rawFlags - User-entered table flags string.
 * @returns {Object} Normalized flag object.
 */
function parseTableCustomFlags(rawFlags) {
    const out = {
        delimiter: null,
        headerIndex: null,
        trim: true,
        skipEmpty: false,
        alignThreshold: null,
        stripBanner: null
    };
    if (!rawFlags || typeof rawFlags !== 'string') return out;
    const tokens = rawFlags.trim().split(/\s+/).filter(Boolean);
    for (let i = 0; i < tokens.length; i++) {
        const tok = tokens[i];
        let key = tok;
        let val = null;
        if (tok.includes('=')) {
            const idx = tok.indexOf('=');
            key = tok.slice(0, idx);
            val = tok.slice(idx + 1);
        } else if (['--delimiter', '--header', '--align-score'].includes(tok) && i + 1 < tokens.length) {
            val = tokens[++i];
        }
        const normKey = key.replace(/^--/, '').toLowerCase();
        if (normKey === 'delimiter' && val !== null) {
            out.delimiter = val === '\\t' ? '\t' : val.replace(/^['"]|['"]$/g, '');
        } else if (normKey === 'header' && val !== null) {
            out.headerIndex = val;
        } else if (normKey === 'no-trim') {
            out.trim = false;
        } else if (normKey === 'trim') {
            out.trim = true;
        } else if (normKey === 'skip-empty') {
            out.skipEmpty = true;
        } else if (normKey === 'align-score' && val !== null) {
            const parsedScore = parseFloat(val);
            if (!Number.isNaN(parsedScore)) {
                out.alignThreshold = Math.max(0.0, Math.min(1.0, parsedScore));
            }
        } else if (normKey === 'strip-banner') {
            out.stripBanner = 'strip';
        } else if (normKey === 'keep-banner') {
            out.stripBanner = 'keep';
        }
    }
    return out;
}

/**
 * Re-parses raw text lines with a custom delimiter into matrix rows.
 *
 * @param {string} rawText - Markdown or delimited text.
 * @param {string} delimiter - Column delimiter character or string.
 * @param {boolean} trimCells - Whether to trim whitespace per cell.
 * @param {boolean} skipEmpty - Whether to omit completely blank rows.
 * @returns {string[][]} Parsed cell matrix.
 */
function _splitTextByDelimiter(rawText, delimiter, trimCells, skipEmpty) {
    if (!rawText || typeof rawText !== 'string') return [];
    const lines = rawText.split(/\r?\n/);
    const rows = [];
    for (const rawLine of lines) {
        let line = rawLine;
        if (delimiter === '|') {
            line = line.trim();
            if (!line.includes('|')) continue;
            if (line.startsWith('|')) line = line.slice(1);
            if (line.endsWith('|')) line = line.slice(0, -1);
        } else if (!line.trim()) {
            continue;
        }
        const rawCells = line.split(delimiter);
        const cells = rawCells.map(c => (trimCells ? c.trim() : c));
        if (delimiter === '|' && cells.length > 0 && cells.every(c => /^:?-+:?$/.test(c.trim()))) {
            continue;
        }
        if (skipEmpty && cells.every(c => !c.trim())) {
            continue;
        }
        if (cells.length > 0) {
            rows.push(cells);
        }
    }
    return rows;
}

/**
 * Mutates a table_grid node's content by re-parsing with custom header, banner, and delimiter flags.
 *
 * @param {Object} node - Target table_grid DOM node.
 * @param {string} hdrSelection - Header row option ('auto', '0', '1', '2').
 * @param {string} stripSelection - Banner handling ('strip' | 'keep').
 * @param {string} flagsVal - Custom CLI-style flags string.
 */
function applyTableReparseOptions(node, hdrSelection, stripSelection, flagsVal) {
    if (!node || !node.content) return;
    const parsedFlags = parseTableCustomFlags(flagsVal);
    const hdrVal = parsedFlags.headerIndex !== null ? parsedFlags.headerIndex : (hdrSelection || 'auto');
    const stripVal = parsedFlags.stripBanner !== null ? parsedFlags.stripBanner : (stripSelection || 'strip');

    const prevContentSnapshot = JSON.parse(JSON.stringify(node.content));
    const prevNodeState = {
        is_corrected: !!node.is_corrected,
        corrected_text: node.corrected_text || null,
        user_correction_note: node.user_correction_note || ''
    };

    if (node.content._raw_text_snapshot === undefined && typeof node.content.raw_text === 'string') {
        node.content._raw_text_snapshot = node.content.raw_text;
    }
    if (!Array.isArray(node.content._raw_rows_snapshot) && Array.isArray(node.content.rows) && node.content.rows.length > 0) {
        node.content._raw_rows_snapshot = JSON.parse(JSON.stringify(node.content.rows));
    }

    let sourceRows = [];
    if (parsedFlags.delimiter) {
        const textSource = node.content._raw_text_snapshot || node.content.raw_text || node.content.markdown_table || '';
        sourceRows = _splitTextByDelimiter(textSource, parsedFlags.delimiter, parsedFlags.trim, parsedFlags.skipEmpty);
    }
    if (sourceRows.length === 0) {
        const base = Array.isArray(node.content._raw_rows_snapshot)
            ? node.content._raw_rows_snapshot
            : (Array.isArray(node.content.rows) ? node.content.rows : []);
        sourceRows = base.map(r => (Array.isArray(r) ? r.map(c => (parsedFlags.trim ? String(c || '').trim() : String(c || ''))) : []));
        if (parsedFlags.skipEmpty) {
            sourceRows = sourceRows.filter(r => r.some(c => c.trim().length > 0));
        }
    }

    if (sourceRows.length === 0) {
        if (flagsVal) node.content.table_custom_flags = flagsVal;
        return;
    }

    let workingRows = sourceRows.map(r => [...r]);
    let resolvedHeaders = [];
    let resolvedTitle = '';
    let effectiveHdrIdx = 0;

    if (hdrVal === 'auto') {
        const r0Clean = workingRows[0].map(c => c.trim()).filter(Boolean);
        const hasBanner = r0Clean.length > 0 && new Set(r0Clean).size === 1 && workingRows.length > 1;
        if (hasBanner) {
            resolvedTitle = r0Clean[0];
            resolvedHeaders = [...workingRows[1]];
            if (stripVal === 'strip') {
                workingRows = workingRows.slice(1);
                effectiveHdrIdx = 0;
            } else {
                effectiveHdrIdx = 1;
            }
        } else {
            resolvedHeaders = [...workingRows[0]];
            effectiveHdrIdx = 0;
        }
    } else {
        const hdrIdx = Math.max(0, Math.min(parseInt(hdrVal, 10) || 0, workingRows.length - 1));
        if (hdrIdx > 0) {
            const r0Clean = workingRows[0].map(c => c.trim()).filter(Boolean);
            if (r0Clean.length > 0 && new Set(r0Clean).size === 1) {
                resolvedTitle = r0Clean[0];
            }
        }
        resolvedHeaders = [...workingRows[hdrIdx]];
        if (hdrIdx > 0 && stripVal === 'strip') {
            workingRows = workingRows.slice(hdrIdx);
            effectiveHdrIdx = 0;
        } else {
            effectiveHdrIdx = hdrIdx;
        }
    }

    const rowLengths = workingRows.map(r => r.length);
    const maxCols = Math.max(resolvedHeaders.length, ...rowLengths, 0);
    while (resolvedHeaders.length < maxCols) resolvedHeaders.push(`Col ${resolvedHeaders.length + 1}`);
    const normalizedRows = workingRows.map(r => {
        const padded = r.slice(0, maxCols);
        while (padded.length < maxCols) padded.push('');
        return padded;
    });

    const columns = [];
    for (let c = 0; c < maxCols; c++) columns.push(normalizedRows.map(r => r[c] || ''));

    const uniqueLengths = new Set(rowLengths);
    const modeCount = rowLengths.reduce((best, len) => Math.max(best, rowLengths.filter(x => x === len).length), 0);
    const alignmentScore = rowLengths.length > 0 ? Number((modeCount / rowLengths.length).toFixed(4)) : 1.0;
    const alignMin = parsedFlags.alignThreshold !== null ? parsedFlags.alignThreshold : 1.0;

    const mdLines = [
        `| ${resolvedHeaders.map(c => String(c || '').replace(/\|/g, '\\|')).join(' | ')} |`,
        `| ${resolvedHeaders.map(() => '---').join(' | ')} |`
    ];
    const bodyRows = normalizedRows.filter((row, idx) => {
        if (idx !== effectiveHdrIdx) return true;
        return !row.every((val, cIdx) => val === resolvedHeaders[cIdx]);
    });
    for (const row of bodyRows) mdLines.push(`| ${row.map(c => String(c || '').replace(/\|/g, '\\|')).join(' | ')} |`);

    const markdownTable = mdLines.join('\n');
    if (resolvedTitle) {
        node.content.title = resolvedTitle;
    } else {
        delete node.content.title;
    }
    node.content.headers = resolvedHeaders;
    node.content.rows = normalizedRows;
    node.content.columns = columns;
    node.content.num_rows = normalizedRows.length;
    node.content.num_cols = maxCols;
    node.content.cell_alignment_score = alignmentScore;
    node.content.is_consistent = uniqueLengths.size <= 1 || alignmentScore >= alignMin;
    node.content.markdown_table = markdownTable;
    node.content.raw_text = markdownTable;
    node.content.table_custom_flags = flagsVal;
    node.content.table_header_row_mode = hdrVal;
    node.content.table_strip_banner = stripVal;
    node.content.table_header_row_effective_idx = effectiveHdrIdx;
    node.user_correction_note = markdownTable;
    if (node.is_corrected || node.corrected_text) {
        node.corrected_text = markdownTable;
    }
    if (typeof userCorrections === 'object' && userCorrections !== null && userCorrections[node.node_id]) {
        userCorrections[node.node_id] = markdownTable;
    }

    if (typeof recordRunDiff === 'function') {
        recordRunDiff({
            action: 'reparse_table',
            description: `Re-parse table ${node.node_id} (header=${hdrVal})`,
            page: typeof getNodePage === 'function' ? getNodePage(node) : 1,
            meta: {
                node_id: node.node_id,
                before_content: prevContentSnapshot,
                after_content: JSON.parse(JSON.stringify(node.content)),
                before_node_state: prevNodeState,
                after_node_state: {
                    is_corrected: !!node.is_corrected,
                    corrected_text: node.corrected_text || null,
                    user_correction_note: node.user_correction_note || ''
                }
            }
        });
    }
}
