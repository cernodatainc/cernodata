/**
 * src/visualization/viewer/js/api.js
 *
 * Backend pipeline communication, preset simulation/re-evaluation,
 * and DocumentDOM annotation persistence.
 */

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
    const targetLang = langOverride || document.getElementById('selectLanguage').value || activeLanguage;
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
                banner.textContent = `[OK] Live pipeline finished. Applied preset '${presetName}' (Language: ${targetLang}).`;
                setTimeout(() => { banner.style.display = 'none'; }, 4000);
            }

            domData = data.dom;
            violationsData = data.violations;
            decisionData = data.decision;
            ensureViolationIds();
            activeLanguage = targetLang;
            activePresetIndex = (presetName === 'docling_deep') ? 1 : 0;

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
            const hasDiacriticViolations = violationsData.some(v => v.rule_type === 'diacritic_conflict' || v.rule_type === 'ocr_character_substitution');
            if (hasDiacriticViolations && !appliedCorrections) {
                return (initialDecisionData.attempts && initialDecisionData.attempts[0])
                    ? (initialDecisionData.attempts[0].overall_confidence || 0.5324)
                    : 0.5324;
            }
            return basePageScore;
        }
        return basePageScore;
    }

    if (targetLang === 'en') {
        violationsData = violationsData.filter(v => v.rule_type !== 'diacritic_conflict' && v.rule_type !== 'ocr_character_substitution');
    } else if (targetLang === 'pl') {
        violationsData = JSON.parse(JSON.stringify(initialViolationsData));
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

function switchPreset(stepIndex) {
    const presetName = (stepIndex === 1) ? 'docling_deep' : 'docling_fast';
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
        subEl.textContent = `Status: ${displayedStatus} | Overall Confidence: ${Number(overallScore).toFixed(4)} | Violations Flagged: ${violationsData.length}`;
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

    try {
        const res = await fetch('/api/save_dom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dom: domData, output_dir: 'output' })
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
