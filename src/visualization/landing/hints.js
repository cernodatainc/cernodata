/**
 * src/visualization/landing/hints.js
 *
 * Contextual next-step hint layer guiding users through document discovery,
 * planning initial runs, and managing guidance preferences via localStorage.
 */

const HINTS_STORAGE_KEY = 'cernodata_hints_disabled';

/**
 * Checks if user has disabled next-step guidance hints via localStorage.
 *
 * @returns {boolean} True if hints are disabled.
 */
function areHintsDisabled() {
    try {
        return localStorage.getItem(HINTS_STORAGE_KEY) === 'true';
    } catch (e) {
        return false;
    }
}

/**
 * Persists user preference to disable next-step hint popups.
 */
function disableNextStepHints() {
    try {
        localStorage.setItem(HINTS_STORAGE_KEY, 'true');
    } catch (e) { }
    updateNextStepHints();
}

/**
 * Re-enables next-step hint popups in localStorage.
 */
function enableNextStepHints() {
    try {
        localStorage.removeItem(HINTS_STORAGE_KEY);
    } catch (e) { }
    updateNextStepHints();
}

/**
 * Toggles hints preference from the toolbar button.
 */
function toggleHintsFromToolbar() {
    if (areHintsDisabled()) {
        enableNextStepHints();
    } else {
        disableNextStepHints();
    }
}

/**
 * Updates the state label of the toolbar hints button.
 */
function updateHintToggleButton() {
    const btn = document.getElementById('btnToggleHints');
    if (!btn) return;
    const disabled = areHintsDisabled();
    btn.textContent = disabled ? 'Hints: Off' : 'Hints: On';
    btn.title = disabled
        ? 'Next-step hints are currently disabled. Click to enable.'
        : 'Next-step hints are active. Click to disable.';
}

/**
 * Evaluates workspace state and renders the appropriate next-step hint popup.
 * State 1: No documents discovered -> Guide towards file discovery.
 * State 2: Documents present, 0 runs -> Guide towards planning runs.
 * State 3: Runs exist or hints disabled -> Clear hint layer.
 */
function updateNextStepHints() {
    updateHintToggleButton();
    const container = document.getElementById('explorerHintContainer');
    if (!container) return;

    if (areHintsDisabled()) {
        container.innerHTML = '';
        return;
    }

    const data = window.explorerData;
    const totalDocs = data ? (data.total_documents || 0) : 0;
    const totalRuns = data ? (data.total_runs || 0) : 0;

    if (totalDocs === 0) {
        container.innerHTML = '<div class="hint-popup" id="nextStepHintPopup">'
            + '<div class="hint-popup-header">'
            + '<span class="hint-popup-tag">[NEXT STEP: FILE DISCOVERY]</span>'
            + '<button class="hint-popup-close-btn" onclick="disableNextStepHints()" title="Disable next-step hints">Disable hints</button>'
            + '</div>'
            + '<div class="hint-popup-body">'
            + '<div class="hint-popup-title">No documents discovered in workspace</div>'
            + '<div class="hint-popup-text">No PDF documents were found in the workspace or e2e directories. Add PDF files to your workspace or click below to scan for available documents.</div>'
            + '</div>'
            + '<div class="hint-popup-footer">'
            + '<button class="btn btn-primary btn-sm" onclick="triggerFileDiscoveryAction()">Scan for documents</button>'
            + '<button class="hint-disable-link" onclick="disableNextStepHints()">Don\'t show hints again</button>'
            + '</div>'
            + '</div>';
        return;
    }

    if (totalRuns === 0) {
        container.innerHTML = '<div class="hint-popup" id="nextStepHintPopup">'
            + '<div class="hint-popup-header">'
            + '<span class="hint-popup-tag">[NEXT STEP: PLAN RUNS]</span>'
            + '<button class="hint-popup-close-btn" onclick="disableNextStepHints()" title="Disable next-step hints">Disable hints</button>'
            + '</div>'
            + '<div class="hint-popup-body">'
            + '<div class="hint-popup-title">Workspace documents ready, no parsing runs yet</div>'
            + '<div class="hint-popup-text">Documents have been discovered in the workspace, but no parser execution runs have been generated yet. Open the Planner to select a document and configure your parsing run.</div>'
            + '</div>'
            + '<div class="hint-popup-footer">'
            + '<button class="btn btn-primary btn-sm" onclick="navigateToPlanningTab()">Go to Planning</button>'
            + '<button class="hint-disable-link" onclick="disableNextStepHints()">Don\'t show hints again</button>'
            + '</div>'
            + '</div>';
        return;
    }

    container.innerHTML = '';
}

/**
 * Triggers document discovery scan and reloads file run mappings.
 */
async function triggerFileDiscoveryAction() {
    if (typeof loadAvailableDocuments === 'function') await loadAvailableDocuments();
    if (typeof loadFileRunMappings === 'function') await loadFileRunMappings();
}

/**
 * Navigates directly to Planning tab to guide user into running presets.
 */
function navigateToPlanningTab() {
    if (typeof switchNavTab === 'function') {
        switchNavTab('plan');
    }
}
