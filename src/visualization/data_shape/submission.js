/**
 * src/visualization/data_shape/submission.js
 *
 * DocumentPlan compilation, payload validation, and server dispatch
 * via /api/submit_plan.
 */

/**
 * Validates wizard questionnaire answers and submits the compiled DocumentPlan to the backend.
 */
async function submitPlan() {
    const docPathEl = document.getElementById("docPath") || document.getElementById("inpPdfPath");
    const docPath = docPathEl ? docPathEl.value.trim() : "";
    const inpLang = document.getElementById("inpLanguage");
    const enableHint = document.getElementById("enableLangHint") ? document.getElementById("enableLangHint").checked : true;
    let language = null;
    if (inpLang) {
        language = (inpLang.value === "auto") ? null : inpLang.value;
    } else if (enableHint && document.getElementById("langCode")) {
        language = document.getElementById("langCode").value;
    }
    const threshEl = document.getElementById("inpThreshold") || document.getElementById("thresholdSlider");
    const threshold = threshEl ? parseFloat(threshEl.value) : 0.85;

    if (!docPath) {
        showBanner("Please specify a document file path before proceeding.", "error");
        document.getElementById("docPath").focus();
        return;
    }

    let effectiveOrder = [...suggestedOrder];
    if (overridePrimary && overridePrimary !== suggestedOrder[0]) {
        effectiveOrder = [overridePrimary, ...suggestedOrder.filter(p => p !== overridePrimary)];
    }

    const payload = {
        document_path: docPath,
        taxonomy: selectedTaxonomy,
        target: selectedTarget,
        security: selectedSecurity,
        language: language,
        target_threshold: threshold,
        override_primary: overridePrimary,
        override_order: effectiveOrder,
        scores: currentScores
    };

    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    submitBtn.textContent = "[SUBMITTING] Sending configuration...";

    try {
        const response = await fetch("/api/submit_plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            submitBtn.textContent = "[COMPLETED] Plan Active";
            const chosenPreset = overridePrimary || (effectiveOrder && effectiveOrder.length > 0 ? effectiveOrder[0] : "docling_fast");
            const targetDocName = docPath.split(/[/\\]/).pop().toLowerCase();
            const forceRerunEl = document.getElementById("inpForceRerun");
            const forceRerun = forceRerunEl ? forceRerunEl.checked : false;

            const allRuns = (typeof availablePreviousRuns !== "undefined" && availablePreviousRuns.length > 0)
                ? availablePreviousRuns
                : (typeof availableRuns !== "undefined" ? availableRuns : []);

            const existingRun = allRuns.find(r => {
                const docName = (r.document_name || r.document_path || "").split(/[/\\]/).pop().toLowerCase();
                const rPreset = (r.chosen_preset || "").toLowerCase();
                return docName === targetDocName && rPreset === chosenPreset.toLowerCase();
            });

            if (!forceRerun && existingRun) {
                const confStr = existingRun.overall_confidence !== undefined ? Number(existingRun.overall_confidence).toFixed(4) : "1.0000";
                showBanner(`[INFO] Run already completed for '${targetDocName}' with preset '${chosenPreset}' (Confidence: ${confStr}). Reusing existing result without rerun.`, "success");
                submitBtn.disabled = false;

                const inpPdf = document.getElementById("inpPdfPath");
                if (inpPdf) inpPdf.value = docPath;
                const inpPreset = document.getElementById("inpPreset");
                if (inpPreset) inpPreset.value = chosenPreset;

                if (typeof choosePreviousRun === "function") {
                    await choosePreviousRun(existingRun.dir_path || existingRun.run_id);
                }
                if (typeof switchNavTab === "function") {
                    setTimeout(() => switchNavTab("results"), 400);
                }
                return;
            }

            showBanner("[SUCCESS] Data shape plan configured successfully. Starting pipeline execution...", "success");
            if (typeof triggerRunPipeline === "function") {
                const inpPdf = document.getElementById("inpPdfPath");
                if (inpPdf && docPath) {
                    inpPdf.value = docPath;
                }
                const inpThresh = document.getElementById("inpThreshold");
                if (inpThresh && threshold) {
                    inpThresh.value = threshold;
                }
                const inpPreset = document.getElementById("inpPreset");
                if (inpPreset && chosenPreset) {
                    inpPreset.value = chosenPreset;
                }
                setTimeout(() => {
                    triggerRunPipeline(false);
                }, 600);
            }
        } else {
            const err = await response.json().catch(() => ({}));
            showBanner("[ERROR] " + (err.error || "Failed to submit plan to server."), "error");
            submitBtn.disabled = false;
            submitBtn.textContent = "[SUBMIT PLAN] Start Pipeline Execution";
        }
    } catch (e) {
        // Fallback for standalone/offline browser usage without local server process
        showBanner("[STANDALONE] Server connection offline. Generated plan JSON copied to console.", "success");
        console.log("DocumentPlan JSON:", JSON.stringify(payload, null, 2));
        submitBtn.disabled = false;
        submitBtn.textContent = "[SUBMIT PLAN] Start Pipeline Execution";
    }
}
