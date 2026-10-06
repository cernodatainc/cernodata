/**
 * src/visualization/viewer/js/state.js
 *
 * Core state management, constants, data hydration, and utility helpers
 * for the interactive viewer.
 */

function extractViolationsList(val) {
    if (Array.isArray(val)) return val;
    if (val && typeof val === 'object' && Array.isArray(val.violations)) {
        return val.violations;
    }
    return [];
}

let initialDomData = (window.VIEWER_DATA && window.VIEWER_DATA.dom) ? window.VIEWER_DATA.dom : { nodes: [] };
let initialViolationsData = extractViolationsList(window.VIEWER_DATA && window.VIEWER_DATA.violations);
let initialDecisionData = (window.VIEWER_DATA && window.VIEWER_DATA.decision) ? window.VIEWER_DATA.decision : {};
let detectedLanguagesMap = (window.VIEWER_DATA && window.VIEWER_DATA.detectedLanguages) ? window.VIEWER_DATA.detectedLanguages : {};
let planData = (window.VIEWER_DATA && window.VIEWER_DATA.plan) ? window.VIEWER_DATA.plan : null;
let pdfSourceFile = (window.VIEWER_DATA && window.VIEWER_DATA.pdfSourceFile) ? window.VIEWER_DATA.pdfSourceFile : "";
let pageImages = (window.VIEWER_DATA && window.VIEWER_DATA.pageImages && window.VIEWER_DATA.pageImages.length > 0)
    ? window.VIEWER_DATA.pageImages
    : [(document.getElementById('pageImg') ? document.getElementById('pageImg').src : '')];
let pageDimensions = (window.VIEWER_DATA && window.VIEWER_DATA.pageDimensions) ? window.VIEWER_DATA.pageDimensions : [];
let totalPages = (window.VIEWER_DATA && window.VIEWER_DATA.totalPages) ? window.VIEWER_DATA.totalPages : (pageImages.length || 1);
let currentPage = 1;
let showAllDomNodes = false;
let showAllViolations = false;

let activePresetIndex = 0;
let appliedCorrections = false;
let activeLanguage = (window.VIEWER_DATA && window.VIEWER_DATA.activeLanguage) ? window.VIEWER_DATA.activeLanguage : "en";
let selectedNodeId = null;
let selectedNodeIds = [];
let isCutoutUnskewed = false;
let activeDrag = null;
let currentZoom = 1.0;

let domData = JSON.parse(JSON.stringify(initialDomData));
let violationsData = extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)));
let decisionData = JSON.parse(JSON.stringify(initialDecisionData));

let rawDomData = JSON.parse(JSON.stringify(initialDomData));
let rawViolationsData = extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)));
let rawDecisionData = JSON.parse(JSON.stringify(initialDecisionData));

const TEXTUAL_TYPES = ['paragraph', 'heading', 'header_footer', 'text'];

function isTextualType(type) {
    return TEXTUAL_TYPES.includes(type);
}

function isTextualNode(node) {
    if (!node) return false;
    if (isTextualType(node.type)) return true;
    const text = (node.content && node.content.raw_text) ? node.content.raw_text.trim() : '';
    return text.length > 0;
}

function getNodePage(node) {
    if (!node) return 1;
    if (node.global_page_index !== undefined && node.global_page_index !== null) {
        return Number(node.global_page_index);
    }
    if (node.temp_slice_index !== undefined && node.temp_slice_index !== null) {
        return Number(node.temp_slice_index);
    }
    return 1;
}

function getViolationPage(v) {
    if (!v) return 1;
    if (v.global_page_index !== undefined && v.global_page_index !== null) {
        return Number(v.global_page_index);
    }
    if (v.page !== undefined && v.page !== null) {
        return Number(v.page);
    }
    const node = domData.nodes.find(n => n.node_id === v.node_id);
    if (node && node.global_page_index) {
        return Number(node.global_page_index);
    }
    return 1;
}

function isSuppressed(v) {
    if (!v) return false;
    return String(v.suppressed).toLowerCase() === "true" || v.suppressed === true;
}

function ensureViolationIds() {
    if (!Array.isArray(violationsData)) {
        violationsData = extractViolationsList(violationsData);
    }
    violationsData.forEach((v, idx) => {
        if (!v.violation_id) {
            v.violation_id = `viol_auto_${v.node_id || idx}_${idx}`;
        }
        if (!v.type) {
            v.type = (v.rule_type === 'garbage_character_ratio') ? 'symbols' : 'diacritic';
        }
        if (v.suppressed === undefined || v.suppressed === null) {
            v.suppressed = "false";
        } else {
            v.suppressed = String(v.suppressed);
        }
    });
}

function syncDomAndViolations() {
    if (!Array.isArray(violationsData)) {
        violationsData = extractViolationsList(violationsData);
    }
    ensureViolationIds();
    if (domData && domData.nodes) {
        domData.nodes.forEach(node => {
            if (!node.violations) {
                node.violations = [];
            }
            if (node.violations.length === 0) {
                const matching = violationsData.filter(v => v.node_id === node.node_id);
                if (matching.length > 0) {
                    node.violations = JSON.parse(JSON.stringify(matching));
                }
            } else {
                node.violations.forEach(nv => {
                    if (!nv.type) {
                        nv.type = (nv.rule_type === 'garbage_character_ratio') ? 'symbols' : 'diacritic';
                    }
                    if (nv.suppressed === undefined || nv.suppressed === null) {
                        nv.suppressed = "false";
                    } else {
                        nv.suppressed = String(nv.suppressed);
                    }
                    const found = violationsData.find(v => (nv.violation_id && v.violation_id === nv.violation_id) || (v.node_id === node.node_id && v.rule_type === nv.rule_type));
                    if (found) {
                        found.suppressed = nv.suppressed;
                        found.type = nv.type;
                        if (nv.suggestion) found.suggestion = nv.suggestion;
                    }
                });
            }
        });
    }
}

function roundCoord(val) {
    return Math.round(val * 100) / 100;
}

function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function applyCorrectionsToNodeText(rawText) {
    let text = rawText;
    const viols = extractViolationsList(initialViolationsData);
    viols.forEach(v => {
        if (v.detected_snippet && v.suggested_correction) {
            text = text.replace(new RegExp(v.detected_snippet, 'g'), v.suggested_correction);
        }
    });
    return text;
}

function computeDomDiff() {
    const rawNodes = (rawDomData && rawDomData.nodes) || [];
    const currentNodes = (domData && domData.nodes) || [];
    const rawMap = new Map();
    rawNodes.forEach(n => { if (n && n.node_id) rawMap.set(n.node_id, n); });
    const currMap = new Map();
    currentNodes.forEach(n => { if (n && n.node_id) currMap.set(n.node_id, n); });

    const added = [];
    const modified = [];
    const removed = [];

    for (const [id, curr] of currMap.entries()) {
        const raw = rawMap.get(id);
        if (!raw) {
            added.push(curr);
        } else {
            const rawBox = raw.bounding_box || {};
            const currBox = curr.bounding_box || {};
            const boxChanged = (
                rawBox.x0 !== currBox.x0 ||
                rawBox.y0 !== currBox.y0 ||
                rawBox.x1 !== currBox.x1 ||
                rawBox.y1 !== currBox.y1
            );
            const textChanged = (
                ((raw.content && raw.content.raw_text) || '') !==
                ((curr.content && curr.content.raw_text) || '')
            );
            const typeChanged = raw.type !== curr.type;
            const noteChanged = (raw.user_correction_note || '') !== (curr.user_correction_note || '');
            if (boxChanged || textChanged || typeChanged || noteChanged) {
                modified.push({
                    node_id: id,
                    raw: raw,
                    current: curr,
                    changes: { boxChanged, textChanged, typeChanged, noteChanged }
                });
            }
        }
    }

    for (const [id, raw] of rawMap.entries()) {
        if (!currMap.has(id)) {
            removed.push(raw);
        }
    }

    return {
        added_count: added.length,
        modified_count: modified.length,
        removed_count: removed.length,
        has_changes: (added.length > 0 || modified.length > 0 || removed.length > 0),
        added,
        modified,
        removed
    };
}

function hydrateViewer(data, pageNum = null) {
    if (!data) return;
    window.VIEWER_DATA = data;
    initialDomData = data.dom || { nodes: [] };
    initialViolationsData = extractViolationsList(data.violations);
    initialDecisionData = data.decision || {};
    detectedLanguagesMap = data.detectedLanguages || {};
    planData = data.plan || null;
    pdfSourceFile = data.pdfSourceFile || "";
    if (data.pageImages && data.pageImages.length > 0) {
        pageImages = data.pageImages;
    }
    pageDimensions = data.pageDimensions || [];
    totalPages = data.totalPages || pageImages.length || 1;
    activeLanguage = data.activeLanguage || "en";

    // Preserve pristine raw result alongside working state
    rawDomData = JSON.parse(JSON.stringify(initialDomData));
    rawViolationsData = extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)));
    rawDecisionData = JSON.parse(JSON.stringify(initialDecisionData));

    domData = JSON.parse(JSON.stringify(initialDomData));
    violationsData = extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)));
    decisionData = JSON.parse(JSON.stringify(initialDecisionData));

    if (typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }

    syncDomAndViolations();

    const docEl = document.getElementById('domSourceFilename');
    if (docEl && (domData.source_filename || pdfSourceFile)) {
        docEl.textContent = domData.source_filename || pdfSourceFile;
    }
    const idEl = document.getElementById('domDocId');
    if (idEl && domData.document_id) {
        idEl.textContent = domData.document_id;
    }
    const totEl = document.getElementById('totalPagesNum');
    if (totEl) {
        totEl.textContent = String(totalPages);
    }

    const detBadge = document.getElementById('detectedLangBadge');
    if (detBadge) {
        detBadge.textContent = `P${currentPage}: ${decisionData.primary_detected_language || 'pl'} (Active: ${activeLanguage})`;
    }

    const selLang = document.getElementById('selectLanguage');
    if (selLang && activeLanguage) {
        selLang.value = activeLanguage;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const targetPage = pageNum || parseInt(urlParams.get('page') || '1', 10) || 1;

    renderTimelineButtons();
    initPageControls();
    switchPage(targetPage);
    renderDecisionLog();
    renderPlanTab();
}
