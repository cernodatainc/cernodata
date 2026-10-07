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
    if (node.page !== undefined && node.page !== null) {
        return Number(node.page);
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
                        if (found.suppressed !== undefined) {
                            nv.suppressed = found.suppressed;
                            nv.accepted = found.accepted;
                        } else {
                            found.suppressed = nv.suppressed;
                            found.accepted = nv.accepted;
                        }
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
            const rawViols = (raw.violations || []).filter(v => isSuppressed(v)).map(v => v.violation_id || v.rule_type).sort();
            const currViols = (curr.violations || []).filter(v => isSuppressed(v)).map(v => v.violation_id || v.rule_type).sort();
            const violationsChanged = JSON.stringify(rawViols) !== JSON.stringify(currViols);

            if (boxChanged || textChanged || typeChanged || noteChanged || violationsChanged) {
                modified.push({
                    node_id: id,
                    raw: raw,
                    current: curr,
                    changes: { boxChanged, textChanged, typeChanged, noteChanged, violationsChanged }
                });
            }
        }
    }

    for (const [id, raw] of rawMap.entries()) {
        if (!currMap.has(id)) {
            removed.push(raw);
        }
    }

    const rawViolsList = (typeof extractViolationsList === 'function')
        ? extractViolationsList(rawViolationsData)
        : (Array.isArray(rawViolationsData) ? rawViolationsData : []);
    const currViolsList = (typeof extractViolationsList === 'function')
        ? extractViolationsList(violationsData)
        : (Array.isArray(violationsData) ? violationsData : []);

    const rawSuppressedMap = new Map();
    rawViolsList.forEach(v => {
        const vid = v.violation_id || `${v.node_id}_${v.rule_type}`;
        rawSuppressedMap.set(vid, isSuppressed(v));
    });

    const acceptedViolations = [];
    currViolsList.forEach(v => {
        const vid = v.violation_id || `${v.node_id}_${v.rule_type}`;
        const wasSuppressedInRaw = rawSuppressedMap.get(vid) || false;
        const isCurrentlySuppressed = isSuppressed(v);
        if (isCurrentlySuppressed && !wasSuppressedInRaw) {
            acceptedViolations.push({
                violation_id: v.violation_id,
                node_id: v.node_id,
                rule_type: v.rule_type || v.type,
                type: v.type,
                page: getViolationPage(v),
                detected_snippet: v.detected_snippet || '',
                accepted: true,
                suppressed: true
            });
        }
    });

    const rawOverall = (typeof rawDecisionData !== 'undefined' && rawDecisionData) ? rawDecisionData.overall_confidence : null;
    const currOverall = (typeof decisionData !== 'undefined' && decisionData) ? decisionData.overall_confidence : null;
    const scoreDelta = (rawOverall !== null && currOverall !== null)
        ? Math.round((currOverall - rawOverall) * 10000) / 10000
        : 0;

    return {
        added_count: added.length,
        modified_count: modified.length,
        removed_count: removed.length,
        accepted_violations_count: acceptedViolations.length,
        has_changes: (added.length > 0 || modified.length > 0 || removed.length > 0 || acceptedViolations.length > 0),
        added,
        modified,
        removed,
        accepted_violations: acceptedViolations,
        scoring: {
            raw_overall_confidence: rawOverall,
            current_overall_confidence: currOverall,
            score_delta: scoreDelta,
            status: (decisionData && decisionData.status) || 'ACCEPT'
        }
    };
}

function recalculateScoring() {
    if (!decisionData) return null;

    const viols = (typeof extractViolationsList === 'function')
        ? extractViolationsList(violationsData)
        : (Array.isArray(violationsData) ? violationsData : []);

    const rawDecision = (typeof rawDecisionData !== 'undefined' && rawDecisionData) ? rawDecisionData : decisionData;
    const rawPerPage = (rawDecision && rawDecision.per_page_confidence) || {};
    const rawAttempts = (rawDecision && rawDecision.attempts) || [];
    const rawAtt = rawAttempts[activePresetIndex] || rawAttempts[0] || {};
    const rawAttPerPage = rawAtt.per_page_confidence || {};

    const cleanMax = 1.0;
    const newPerPage = {};
    const numPages = totalPages || 1;

    for (let p = 1; p <= numPages; p++) {
        const pStr = String(p);
        const pViols = viols.filter(v => getViolationPage(v) === p);
        const totalPViols = pViols.length;
        const activePViols = pViols.filter(v => !v.is_fixed && !isSuppressed(v)).length;
        const resolvedPViols = totalPViols - activePViols;

        let rawScore = rawAttPerPage[pStr] ?? rawAttPerPage[p] ?? rawPerPage[pStr] ?? rawPerPage[p];
        if (rawScore === undefined || rawScore === null) {
            rawScore = rawAtt.overall_confidence ?? rawDecision.overall_confidence ?? 0.85;
        }
        rawScore = Number(rawScore);

        if (totalPViols === 0) {
            newPerPage[pStr] = rawScore;
        } else if (activePViols === 0) {
            newPerPage[pStr] = Math.max(cleanMax, rawScore);
        } else {
            const penalty = Math.max(0, cleanMax - rawScore);
            const recoveryRatio = resolvedPViols / totalPViols;
            const computed = rawScore + (penalty * recoveryRatio);
            newPerPage[pStr] = Math.min(cleanMax, Math.round(computed * 10000) / 10000);
        }
    }

    const pageScores = Object.values(newPerPage);
    const overallScore = Math.round((pageScores.reduce((a, b) => a + b, 0) / Math.max(1, pageScores.length)) * 10000) / 10000;

    const threshold = decisionData.target_confidence_threshold || 0.82;
    const isAccepted = overallScore >= threshold;
    const newStatus = isAccepted ? 'ACCEPT' : 'TRIGGER_FALLBACK';

    decisionData.per_page_confidence = newPerPage;
    decisionData.overall_confidence = overallScore;
    decisionData.is_accepted = isAccepted;
    decisionData.status = newStatus;

    const activePerPageViols = {};
    for (let p = 1; p <= numPages; p++) {
        const pViols = viols.filter(v => getViolationPage(v) === p && !v.is_fixed && !isSuppressed(v));
        activePerPageViols[String(p)] = pViols.length;
    }
    const totalActiveViolations = Object.values(activePerPageViols).reduce((a, b) => a + b, 0);

    if (decisionData.attempts && decisionData.attempts.length > 0) {
        const targetAttempt = decisionData.attempts[activePresetIndex] || decisionData.attempts[decisionData.attempts.length - 1];
        if (targetAttempt) {
            targetAttempt.overall_confidence = overallScore;
            targetAttempt.per_page_confidence = JSON.parse(JSON.stringify(newPerPage));
            targetAttempt.violations_count = totalActiveViolations;
            targetAttempt.per_page_violations = JSON.parse(JSON.stringify(activePerPageViols));
            targetAttempt.is_accepted = isAccepted;
            targetAttempt.status = newStatus;
        }
    }

    if (typeof updatePageScoreBadge === 'function') {
        updatePageScoreBadge();
    }
    if (typeof updatePresetUIState === 'function') {
        updatePresetUIState();
    }
    if (typeof renderTimelineButtons === 'function') {
        renderTimelineButtons();
    }
    if (typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }

    const targetAttempt = (decisionData && decisionData.attempts && decisionData.attempts[activePresetIndex]) || null;
    const currentPreset = (targetAttempt && targetAttempt.preset) || ((activePresetIndex === 1) ? 'docling_deep' : 'docling_fast');
    const targetStep = (targetAttempt && targetAttempt.step) || (activePresetIndex + 1);
    const outDir = (typeof outputDir !== 'undefined' && outputDir) ? outputDir : ((window.VIEWER_DATA && window.VIEWER_DATA.outputDir) || 'output');
    const updateMsg = {
        type: 'RUN_RESULT_UPDATED',
        outputDir: outDir,
        preset: currentPreset,
        activePresetIndex: activePresetIndex,
        runId: `${outDir}:step_${targetStep}`,
        overall_confidence: overallScore,
        status: newStatus,
        violationsCount: totalActiveViolations,
        perPageConfidence: newPerPage,
        perPageViolations: activePerPageViols,
        totalPages: numPages
    };

    if (typeof window !== 'undefined') {
        if (window.parent && window.parent !== window) {
            try {
                if (typeof window.parent.updateRunsGridLiveEntry === 'function') {
                    window.parent.updateRunsGridLiveEntry(updateMsg);
                }
                window.parent.postMessage(updateMsg, '*');
            } catch (e) {
                // Cross-origin fallback
            }
        }
        if (typeof updateViewerRunsGridLiveEntry === 'function') {
            updateViewerRunsGridLiveEntry(updateMsg);
        }
    }

    return {
        overall_confidence: overallScore,
        per_page_confidence: newPerPage,
        status: newStatus,
        is_accepted: isAccepted,
        active_violations_count: totalActiveViolations,
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
    const stepQuery = urlParams.get('step');

    if (stepQuery !== null && stepQuery !== undefined) {
        const parsedStep = parseInt(stepQuery, 10);
        if (!isNaN(parsedStep) && parsedStep >= 1) {
            activePresetIndex = parsedStep - 1;
        }
    } else if (data && data.activeStep) {
        activePresetIndex = data.activeStep - 1;
    } else if (decisionData.attempts && decisionData.attempts.length > 0 && decisionData.chosen_preset) {
        const matchIdx = decisionData.attempts.findIndex(a => a.preset === decisionData.chosen_preset);
        if (matchIdx >= 0) {
            activePresetIndex = matchIdx;
        } else {
            activePresetIndex = decisionData.attempts.length - 1;
        }
    }

    renderTimelineButtons();
    if (typeof updatePresetUIState === 'function') {
        updatePresetUIState();
    }
    initPageControls();
    switchPage(targetPage);
    renderDecisionLog();
    renderPlanTab();
}
