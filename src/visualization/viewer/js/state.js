/**
 * src/visualization/viewer/js/state.js
 *
 * Core state management, constants, data hydration, and utility helpers
 * for the interactive viewer.
 */

let initialDomData = (window.VIEWER_DATA && window.VIEWER_DATA.dom) ? window.VIEWER_DATA.dom : { nodes: [] };
let initialViolationsData = (window.VIEWER_DATA && window.VIEWER_DATA.violations) ? window.VIEWER_DATA.violations : [];
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
let violationsData = JSON.parse(JSON.stringify(initialViolationsData));
let decisionData = JSON.parse(JSON.stringify(initialDecisionData));

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

function ensureViolationIds() {
    violationsData.forEach((v, idx) => {
        if (!v.violation_id) {
            v.violation_id = `viol_auto_${v.node_id || idx}_${idx}`;
        }
    });
}

function roundCoord(val) {
    return Math.round(val * 100) / 100;
}

function escapeHtml(str) {
    return String(str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function applyCorrectionsToNodeText(rawText) {
    let text = rawText;
    initialViolationsData.forEach(v => {
        if (v.detected_snippet && v.suggested_correction) {
            text = text.replace(new RegExp(v.detected_snippet, 'g'), v.suggested_correction);
        }
    });
    return text;
}

function hydrateViewer(data) {
    if (!data) return;
    window.VIEWER_DATA = data;
    initialDomData = data.dom || { nodes: [] };
    initialViolationsData = data.violations || [];
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

    domData = JSON.parse(JSON.stringify(initialDomData));
    violationsData = JSON.parse(JSON.stringify(initialViolationsData));
    decisionData = JSON.parse(JSON.stringify(initialDecisionData));

    ensureViolationIds();

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

    renderTimelineButtons();
    initPageControls();
    switchPage(1);
    renderDecisionLog();
    renderPlanTab();
}
