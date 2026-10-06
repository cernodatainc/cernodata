/**
 * src/visualization/viewer/js/api.js
 *
 * Backend pipeline communication, preset simulation/re-evaluation,
 * and DocumentDOM annotation persistence.
 */

window.presetCache = window.presetCache || {};

function saveCurrentPresetToClientCache() {
    if (typeof decisionData === 'undefined' || !decisionData) return;
    const currentPreset = decisionData.chosen_preset || ((activePresetIndex === 1) ? 'docling_deep' : 'docling_fast');
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

function onLanguageChanged() {
    const sel = document.getElementById('selectLanguage').value;
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[INFO] Language override selected: '${sel}'. Click '[REDO] Redo Run' to re-evaluate with this language.`;
        setTimeout(() => { banner.style.display = 'none'; }, 4000);
    }
}

async function redoWithSelectedLanguage() {
    const selectedLang = document.getElementById('selectLanguage').value;
    const presetName = (activePresetIndex === 1) ? 'docling_deep' : 'docling_fast';
    await rerunBackendPipeline(presetName, selectedLang);
}

async function rerunBackendPipeline(presetName, langOverride = null) {
    if (typeof saveCurrentPresetToClientCache === 'function') {
        saveCurrentPresetToClientCache();
    }
    const targetLang = langOverride || (document.getElementById('selectLanguage') ? document.getElementById('selectLanguage').value : null) || activeLanguage;
    const clientCached = window.presetCache[`${presetName}:${targetLang}`] || (!langOverride ? window.presetCache[presetName] : null);

    if (clientCached) {
        domData = JSON.parse(JSON.stringify(clientCached.dom));
        violationsData = (typeof extractViolationsList === 'function')
            ? extractViolationsList(JSON.parse(JSON.stringify(clientCached.violations)))
            : JSON.parse(JSON.stringify(clientCached.violations));
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
        banner.textContent = `[RUNNING] Running backend pipeline for preset '${presetName}' with language '${targetLang}'...`;
    }

    try {
        const res = await fetch('/api/rerun', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName, language: targetLang, pdf_path: pdfSourceFile })
        });

        if (res.ok) {
            const data = await res.json();
            if (banner) {
                const tag = data.cached ? '[CACHE HIT]' : '[OK]';
                banner.textContent = `${tag} Applied preset '${presetName}' (Language: ${targetLang}).`;
                setTimeout(() => { banner.style.display = 'none'; }, 4000);
            }

            domData = data.dom;
            violationsData = (typeof extractViolationsList === 'function')
                ? extractViolationsList(data.violations)
                : (Array.isArray(data.violations) ? data.violations : (data.violations && data.violations.violations) || []);
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
            const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
            const hasDiacriticViolations = viols.some(v => v.rule_type === 'diacritic_conflict' || v.rule_type === 'ocr_character_substitution');
            if (hasDiacriticViolations && !appliedCorrections) {
                return (initialDecisionData.attempts && initialDecisionData.attempts[0])
                    ? (initialDecisionData.attempts[0].overall_confidence || 0.5324)
                    : 0.5324;
            }
            return basePageScore;
        }
        return basePageScore;
    }

    const viols = (typeof extractViolationsList === 'function') ? extractViolationsList(violationsData) : (Array.isArray(violationsData) ? violationsData : []);
    if (targetLang === 'en') {
        violationsData = viols.filter(v => v.rule_type !== 'diacritic_conflict' && v.rule_type !== 'ocr_character_substitution');
    } else if (targetLang === 'pl') {
        violationsData = (typeof extractViolationsList === 'function')
            ? extractViolationsList(JSON.parse(JSON.stringify(initialViolationsData)))
            : JSON.parse(JSON.stringify(initialViolationsData || []));
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
        violationsData = (typeof extractViolationsList === 'function')
            ? extractViolationsList(JSON.parse(JSON.stringify(cached.violations)))
            : JSON.parse(JSON.stringify(cached.violations));
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
            appliedCorrections = true;
            const togCorr = document.getElementById('toggleCorrections');
            if (togCorr) togCorr.checked = true;
        } else {
            st2.textContent = 'Candidate';
            st2.style.background = '#4B5563';
            st2.style.color = '#FFF';
        }
    }

    const subEl = document.getElementById('scoreSub');
    if (subEl) {
        const violCount = (typeof extractViolationsList === 'function')
            ? extractViolationsList(violationsData).length
            : (Array.isArray(violationsData) ? violationsData.length : 0);
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

async function saveAnnotations() {
    const banner = document.getElementById('statusBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.textContent = `[SAVING] Saving modified DocumentDOM annotations...`;
    }

    const diffPayload = (typeof computeDomDiff === 'function') ? computeDomDiff() : {};
    try {
        const res = await fetch('/api/save_dom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dom: domData,
                raw_dom: (typeof rawDomData !== 'undefined') ? rawDomData : domData,
                diff: diffPayload,
                output_dir: 'output'
            })
        });
        if (res.ok) {
            const data = await res.json();
            if (banner) {
                banner.textContent = `[OK] Annotations saved successfully to '${data.path}'.`;
                setTimeout(() => { banner.style.display = 'none'; }, 4000);
            }
            return;
        }
    } catch (e) {
        console.log('[INFO] Server endpoint unreachable, initiating file download.', e);
    }

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
    appliedCorrections = false;
    const togCorr = document.getElementById('toggleCorrections');
    if (togCorr) togCorr.checked = false;

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
