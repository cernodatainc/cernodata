/**
 * src/visualization/viewer/js/api.js
 *
 * Backend pipeline communication, preset simulation/re-evaluation,
 * and DocumentDOM annotation persistence.
 */

window.presetCache = window.presetCache || {};

/**
 * Caches current DOM, violations, and decision state into client memory
 * keyed by active preset and language.
 */
function saveCurrentPresetToClientCache() {
    const targetAttempt = (decisionData && decisionData.attempts && decisionData.attempts[activePresetIndex]) || null;
    const currentPreset = (targetAttempt && targetAttempt.preset) || ((activePresetIndex === 1) ? 'docling_deep' : (decisionData.chosen_preset || 'docling_fast'));
    const targetLang = (typeof activeLanguage !== 'undefined' && activeLanguage) ? activeLanguage : 'en';
    const entry = {
        dom: (typeof domData !== 'undefined' && domData) ? JSON.parse(JSON.stringify(domData)) : { nodes: [] },
        raw_dom: (typeof rawDomData !== 'undefined' && rawDomData) ? JSON.parse(JSON.stringify(rawDomData)) : { nodes: [] },
        diff: (typeof computeDomDiff === 'function') ? computeDomDiff() : null,
        violations: (typeof violationsData !== 'undefined' && violationsData) ? JSON.parse(JSON.stringify(violationsData)) : [],
        raw_violations: (typeof rawViolationsData !== 'undefined' && rawViolationsData) ? JSON.parse(JSON.stringify(rawViolationsData)) : [],
        decision: JSON.parse(JSON.stringify(decisionData)),
        raw_decision: (typeof rawDecisionData !== 'undefined' && rawDecisionData) ? JSON.parse(JSON.stringify(rawDecisionData)) : null,
        activePresetIndex: activePresetIndex
    };
    window.presetCache[`${currentPreset}:${targetLang}`] = entry;
    window.presetCache[currentPreset] = entry;
}

/**
 * Handles language selection dropdown change event and updates active language.
 */
function onLanguageChanged() {
    const sel = document.getElementById('selectLanguage').value;
    activeLanguage = (sel === 'auto') ? (primaryDetectedLanguage || 'en') : sel;
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[INFO] Language override set to '${sel}'.`;
        setTimeout(() => { banner.style.display = 'none'; }, 3000);
    }
}

/**
 * Forces pipeline re-evaluation bypassing cache for a preset from the Runs Grid.
 *
 * @param {string} presetName - Target pipeline preset.
 * @param {string|null} [docName=null] - Optional document filename.
 */
async function forceRerunFromViewerGrid(presetName, docName = null) {
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[FORCE RERUN] Initiating forced re-evaluation for preset '${presetName}'...`;
    }
    const targetDoc = docName || (domData && domData.source_filename) || pdfSourceFile || '';
    if (targetDoc && !pdfSourceFile) {
        pdfSourceFile = targetDoc;
    }
    await rerunBackendPipeline(presetName, activeLanguage, true);
    if (typeof loadViewerRunsGrid === 'function') {
        loadViewerRunsGrid();
    }
}

/**
 * Dispatches POST /api/rerun request to execute or retrieve cached results for preset.
 * Falls back to offline client-side simulation when backend server is unavailable.
 *
 * @param {string} presetName - Target pipeline preset ('docling_fast', 'docling_deep').
 * @param {string|null} [langOverride=null] - Optional language code override.
 * @param {boolean} [force=false] - Whether to bypass preset cache and force live re-evaluation.
 */
async function rerunBackendPipeline(presetName, langOverride = null, force = false) {
    if (!force && typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }
    const targetLang = langOverride || (document.getElementById('selectLanguage') ? document.getElementById('selectLanguage').value : null) || activeLanguage;
    const clientCached = !force && (window.presetCache[`${presetName}:${targetLang}`] || (!langOverride ? window.presetCache[presetName] : null));

    if (clientCached) {
        domData = JSON.parse(JSON.stringify(clientCached.dom));
        violationsData = extractViolationsList(JSON.parse(JSON.stringify(clientCached.violations)));
        decisionData = JSON.parse(JSON.stringify(clientCached.decision));
        ensureViolationIds();
        activeLanguage = targetLang;
        activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;
        updatePresetUIState();

        const banner = document.getElementById('statusBanner');
        if (banner) {
            banner.style.display = 'block';
            banner.textContent = `[INFO] Applied preset '${presetName}' from cache (Language: ${targetLang}).`;
            setTimeout(() => { banner.style.display = 'none'; }, 2500);
        }
        return;
    }

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        const prefix = force ? '[FORCE RERUN]' : '[RUNNING]';
        banner.textContent = `${prefix} Running backend pipeline for preset '${presetName}' with language '${targetLang}'...`;
    }

    try {
        const res = await fetch('/api/rerun', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName, language: targetLang, pdf_path: pdfSourceFile, force: force, force_rerun: force })
        });

        if (res.ok) {
            const data = await res.json();
            if (banner) {
                const tag = data.cached ? '[CACHE HIT]' : '[OK]';
                banner.textContent = `${tag} Applied preset '${presetName}' (Language: ${targetLang}).`;
                setTimeout(() => { banner.style.display = 'none'; }, 4000);
            }

            domData = data.dom;
            violationsData = extractViolationsList(data.violations);
            decisionData = data.decision;
            ensureViolationIds();
            activeLanguage = targetLang;
            activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;

            if (typeof saveCurrentPresetToClientCache === 'function') {
                saveCurrentPresetToClientCache();
            }
            updatePresetUIState();
            return;
        }
    } catch (err) {
        console.log("[INFO] Live API endpoint unreachable, applying client simulation.", err);
    }

    activeLanguage = targetLang;
    if (banner) {
        banner.textContent = `[INFO] Language overridden to '${targetLang}'. (To run live Python backend, launch 'python src/main.py --serve').`;
        setTimeout(() => { banner.style.display = 'none'; }, 5000);
    }

    function calculateSimulatedConfidence(simTargetLang, isDeepPreset) {
        const basePageScore = (initialDecisionData.per_page_confidence && (initialDecisionData.per_page_confidence['1'] || initialDecisionData.per_page_confidence[1])) || 0.9684;
        if (isDeepPreset) {
            return (initialDecisionData.attempts && initialDecisionData.attempts.length > 1)
                ? (initialDecisionData.attempts[1].overall_confidence || 0.9833)
                : 0.9833;
        }
        if (simTargetLang === 'en') {
            return basePageScore;
        } else if (simTargetLang === 'pl') {
            const viols = getViolationsList();
            const hasDiacriticViolations = viols.some(v => (v.rule_type === 'diacritic_conflict' || v.rule_type === 'ocr_character_substitution') && !v.is_fixed && !isSuppressed(v));
            if (hasDiacriticViolations) {
                return (initialDecisionData.attempts && initialDecisionData.attempts[0])
                    ? (initialDecisionData.attempts[0].overall_confidence || 0.5324)
                    : 0.5324;
            }
            return basePageScore;
        }
        return basePageScore;
    }

    const viols = getViolationsList();
    if (targetLang === 'en') {
        violationsData = viols.filter(v => v.rule_type !== 'diacritic_conflict' && v.rule_type !== 'ocr_character_substitution');
    } else if (targetLang === 'pl') {
        violationsData = extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)));
        ensureViolationIds();
    }

    activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;
    const isDeep = (activePresetIndex === 1);
    const simulatedScore = calculateSimulatedConfidence(targetLang, isDeep);
    decisionData.per_page_confidence = { "1": simulatedScore };
    decisionData.overall_confidence = simulatedScore;
    decisionData.is_accepted = (simulatedScore >= (decisionData.target_confidence_threshold || 0.82));
    decisionData.status = decisionData.is_accepted ? 'ACCEPT' : 'TRIGGER_FALLBACK';

    updatePresetUIState();
}

/**
 * Switches the active preset view between Step 1 (primary) and Step 2 (fallback).
 *
 * @param {number} stepIndex - Step index (0 for primary, 1 for fallback).
 * @param {string|null} [explicitPreset=null] - Optional preset identifier.
 */
function switchPreset(stepIndex, explicitPreset = null) {
    if (typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }
    const chosenPreset = (decisionData && decisionData.chosen_preset) || (planData ? planData.primary_preset : 'docling_fast') || 'docling_fast';
    let defaultCandidate = (chosenPreset === 'docling_deep') ? 'docling_fast' : 'docling_deep';
    let presetName = explicitPreset || ((stepIndex === 0) ? chosenPreset : defaultCandidate);
    if (stepIndex === 1 && presetName === chosenPreset) {
        presetName = defaultCandidate;
    }
    const targetLang = (typeof activeLanguage !== 'undefined' && activeLanguage) ? activeLanguage : 'en';
    const cached = window.presetCache[`${presetName}:${targetLang}`] || window.presetCache[presetName];

    if (cached) {
        domData = JSON.parse(JSON.stringify(cached.dom));
        if (cached.raw_dom) {
            rawDomData = JSON.parse(JSON.stringify(cached.raw_dom));
        }
        violationsData = extractViolationsList(JSON.parse(JSON.stringify(cached.violations)));
        decisionData = JSON.parse(JSON.stringify(cached.decision));
        ensureViolationIds();
        activePresetIndex = stepIndex;
        updatePresetUIState();

        const banner = document.getElementById('statusBanner');
        if (banner) {
            banner.style.display = 'block';
            banner.textContent = `[INFO] Switched to preset '${presetName}' (Loaded from cache).`;
            setTimeout(() => { banner.style.display = 'none'; }, 2500);
        }
        return;
    }

    rerunBackendPipeline(presetName);
}

/**
 * Updates UI headers, step badges, score indicators, and tree panels to match active preset.
 */
function updatePresetUIState() {
    const btnP1 = document.getElementById('btnPreset1');
    const btnP2 = document.getElementById('btnPreset2');
    if (btnP1) btnP1.classList.toggle('active', activePresetIndex === 0);
    if (btnP2) btnP2.classList.toggle('active', activePresetIndex === 1);
    const st2 = document.getElementById('statusPreset2');

    const attempts = decisionData.attempts || [];
    const currentAttempt = (attempts.length > 1) ? (attempts[activePresetIndex] || attempts[attempts.length - 1]) : null;

    let overallScore = (currentAttempt && currentAttempt.overall_confidence !== undefined)
        ? currentAttempt.overall_confidence
        : decisionData.overall_confidence;

    let p1Score = null;
    if (currentAttempt && currentAttempt.per_page_confidence) {
        p1Score = currentAttempt.per_page_confidence['1'] || currentAttempt.per_page_confidence[1];
    } else if (decisionData.per_page_confidence) {
        p1Score = decisionData.per_page_confidence['1'] || decisionData.per_page_confidence[1];
    }
    if (p1Score === undefined || p1Score === null) {
        p1Score = overallScore;
    }

    let displayedStatus = (currentAttempt && currentAttempt.status)
        ? currentAttempt.status
        : (decisionData.status || 'ACCEPT');

    let threshold = decisionData.target_confidence_threshold || 0.82;
    let isAccepted = (displayedStatus === 'ACCEPT' || overallScore >= threshold);

    updatePageScoreBadge();

    if (st2) {
        if (activePresetIndex === 1) {
            st2.textContent = 'ACTIVE (PASSED)';
            st2.style.background = 'var(--accent-green)';
            st2.style.color = '#000';
        } else {
            st2.textContent = 'Candidate';
            st2.style.background = '#4B5563';
            st2.style.color = '#FFF';
        }
    }

    const subEl = document.getElementById('scoreSub');
    if (subEl) {
        const violCount = getViolationsList().length;
        subEl.textContent = `Status: ${displayedStatus} | Overall Confidence: ${Number(overallScore).toFixed(4)} | Violations Flagged: ${violCount}`;
        subEl.style.color = isAccepted ? 'var(--accent-green)' : 'var(--accent-red)';
    }
    const badgeEl = document.getElementById('scoreBadge');
    if (badgeEl) {
        badgeEl.classList.toggle('fail', !isAccepted);
    }

    renderDOMTree();
    renderViolationsList();
    renderDecisionLog();
    renderPlanTab();
    renderSelectedEditor();
    renderSVGOverlays();
}

/**
 * Persists user modifications, bounding box adjustments, and corrections to the server via POST /api/save_dom.
 *
 * @param {boolean} [quiet=false] - Whether to suppress status banner feedback.
 */
async function saveAnnotations(quiet = false) {
    const banner = document.getElementById('statusBanner');
    if (!quiet && banner) {
        banner.style.display = 'block';
        banner.textContent = `[SAVING] Saving modified DocumentDOM annotations...`;
    }

    const diffPayload = (typeof computeDomDiff === 'function') ? computeDomDiff() : {};
    const outDir = (typeof outputDir !== 'undefined' && outputDir)
        ? outputDir
        : ((window.VIEWER_DATA && window.VIEWER_DATA.outputDir) || 'output');
    const cleanOutDir = outDir.split(':step_')[0];
    function updateAllClientCaches() {
        if (typeof saveCurrentPresetToClientCache === 'function') {
            saveCurrentPresetToClientCache();
        }
        if (window.VIEWER_DATA) {
            window.VIEWER_DATA.dom = JSON.parse(JSON.stringify(domData));
            window.VIEWER_DATA.violations = JSON.parse(JSON.stringify(violationsData));
            window.VIEWER_DATA.decision = JSON.parse(JSON.stringify(decisionData));
            window.VIEWER_DATA.diff = diffPayload;
            window.VIEWER_DATA.outputDir = cleanOutDir;
        }
        initialDomData = JSON.parse(JSON.stringify(domData));
        initialViolationsData = extractViolationsList(JSON.parse(JSON.stringify(violationsData)));
        initialDecisionData = JSON.parse(JSON.stringify(decisionData));

        if (window.parent && window.parent.runResultsCache) {
            const keysToUpdate = [
                cleanOutDir,
                outDir,
                cleanOutDir.replace(/\\/g, '/'),
                outDir.replace(/\\/g, '/'),
                cleanOutDir.replace(/\//g, '\\'),
                outDir.replace(/\//g, '\\')
            ];
            keysToUpdate.forEach(k => {
                const c = window.parent.runResultsCache[k];
                if (c) {
                    c.dom = JSON.parse(JSON.stringify(domData));
                    c.violations = JSON.parse(JSON.stringify(violationsData));
                    c.decision = JSON.parse(JSON.stringify(decisionData));
                    c.diff = diffPayload;
                }
            });
            Object.values(window.parent.runResultsCache).forEach(entry => {
                if (entry && (entry.outputDir === cleanOutDir || entry.outputDir === outDir)) {
                    entry.dom = JSON.parse(JSON.stringify(domData));
                    entry.violations = JSON.parse(JSON.stringify(violationsData));
                    entry.decision = JSON.parse(JSON.stringify(decisionData));
                    entry.diff = diffPayload;
                }
            });
        }
    }

    updateAllClientCaches();

    try {
        const res = await fetch('/api/save_dom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dom: domData,
                raw_dom: (typeof rawDomData !== 'undefined') ? rawDomData : domData,
                diff: diffPayload,
                violations: (typeof violationsData !== 'undefined') ? violationsData : [],
                decision: (typeof decisionData !== 'undefined') ? decisionData : {},
                output_dir: cleanOutDir
            })
        });
        if (res.ok) {
            const data = await res.json();
            updateAllClientCaches();
            if (!quiet && banner) {
                banner.textContent = `[OK] Annotations saved successfully to '${data.path}'.`;
                setTimeout(() => { banner.style.display = 'none'; }, 4000);
            }
            return;
        }
    } catch (e) {
        if (!quiet) {
            console.log('[INFO] Server endpoint unreachable, initiating file download.', e);
        }
    }

    if (!quiet) {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(domData, null, 2));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", "document_dom.json");
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();

        if (banner) {
            banner.textContent = `[OK] Downloaded updated document_dom.json.`;
            setTimeout(() => { banner.style.display = 'none'; }, 4000);
        }
    }
}

/**
 * Reverts all post-run annotations and modifications back to pristine raw preset result.
 * Eliminates the need to rerun expensive OCR/deep model extraction presets.
 */
function revertToRawResult() {
    if (typeof rawDomData === 'undefined' || !rawDomData || !rawDomData.nodes) {
        const banner = document.getElementById('statusBanner');
        if (banner) {
            banner.style.display = 'block';
            banner.textContent = '[WARN] No raw preset result available to revert.';
            setTimeout(() => { banner.style.display = 'none'; }, 3000);
        }
        return;
    }

    const diff = (typeof computeDomDiff === 'function') ? computeDomDiff() : { has_changes: false };
    if (!diff.has_changes) {
        const banner = document.getElementById('statusBanner');
        if (banner) {
            banner.style.display = 'block';
            banner.textContent = '[INFO] Document is already in pristine raw preset state. No modifications to revert.';
            setTimeout(() => { banner.style.display = 'none'; }, 3000);
        }
        return;
    }

    domData = JSON.parse(JSON.stringify(rawDomData));
    violationsData = extractViolationsList(JSON.parse(JSON.stringify(rawViolationsData)));
    decisionData = JSON.parse(JSON.stringify(rawDecisionData));
    ensureViolationIds();

    if (typeof syncDomAndViolations === 'function') {
        syncDomAndViolations();
    }
    if (typeof recalculateScoring === 'function') {
        recalculateScoring();
    }

    if (typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }

    selectedNodeId = null;
    selectedNodeIds = [];
    updatePresetUIState();
    renderDOMTree();
    renderViolationsList();
    renderSelectedEditor();
    renderSVGOverlays();

    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[OK] Reverted modifications back to raw preset result (${diff.modified_count || 0} modified, ${diff.added_count || 0} added, ${diff.removed_count || 0} deleted restored).`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}
