/**
 * src/visualization/data_shape/app.js
 *
 * Data shape wizard application bootstrap and DOMContentLoaded lifecycle handler.
 */

window.addEventListener("DOMContentLoaded", async () => {
    // Check if backend provides prefilled runtime defaults
    try {
        const res = await fetch("/api/config");
        if (res.ok) {
            const cfg = await res.json();
            if (cfg.default_doc) {
                document.getElementById("docPath").value = cfg.default_doc;
            }
            if (cfg.default_lang) {
                document.getElementById("enableLangHint").checked = true;
                const langSelect = document.getElementById("langCode");
                langSelect.value = cfg.default_lang;
                langSelect.disabled = false;
                langSelect.style.opacity = "1";
            }
            if (cfg.previous_runs && cfg.previous_runs.length > 0) {
                populatePreviousRunsDropdown(cfg.previous_runs);
            }
        }
    } catch (e) {
        // Standalone offline fallback
    }

    // Also attempt loading previous runs if not already loaded from config
    if (availablePreviousRuns.length === 0) {
        try {
            const rRes = await fetch("/api/previous_runs");
            if (rRes.ok) {
                const rData = await rRes.json();
                if (rData.runs && rData.runs.length > 0) {
                    populatePreviousRunsDropdown(rData.runs);
                }
            }
        } catch (e) {
            // Ignore offline errors
        }
    }

    renderOptionGrid("taxonomyGrid", TAXONOMY_OPTIONS, selectedTaxonomy, val => selectedTaxonomy = val);
    renderOptionGrid("targetGrid", TARGET_OPTIONS, selectedTarget, val => selectedTarget = val);
    renderOptionGrid("securityGrid", SECURITY_OPTIONS, selectedSecurity, val => selectedSecurity = val);

    recalculate();
});
