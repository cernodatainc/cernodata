/**
 * src/visualization/landing/navigation.js
 *
 * Tab navigation, active view section switching, document path selection,
 * and dynamic preset recommendation badges.
 */

let currentTab = 'input';
let currentPlanningSubtab = 'simple';

/**
 * Switches the active tab and view section in the dashboard hub.
 *
 * @param {string} tabName - Target tab identifier ('input', 'plan', 'progress', 'results').
 */
function switchNavTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll('.hub-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(sec => sec.classList.remove('active'));

    const tabCapitalized = tabName.charAt(0).toUpperCase() + tabName.slice(1);
    const btn = document.getElementById('tabBtn' + tabCapitalized);
    const sec = document.getElementById('sec' + tabCapitalized);

    if (btn) btn.classList.add('active');
    if (sec) sec.classList.add('active');

    if (tabName === 'plan') {
        if (currentPlanningSubtab === 'complex') {
            const frame = document.getElementById('plannerFrame');
            if (frame && (!frame.src || frame.src === 'about:blank' || frame.src.endsWith('/'))) {
                frame.src = '/planner';
            }
        }
    } else if (tabName === 'results') {
        if (typeof refreshResultsData === 'function') refreshResultsData();
        const frame = document.getElementById('viewerFrame');
        if (frame && (!frame.src || frame.src === 'about:blank' || frame.src.endsWith('/'))) {
            if (typeof reloadViewerIframe === 'function') reloadViewerIframe();
        }
    }
}

/**
 * Switches between Simple (Preset Wizard) and Complex (Planner Wizard) subtabs
 * within the Planning hub view.
 *
 * @param {string} mode - Subtab mode ('simple' or 'complex').
 */
function switchPlanningSubtab(mode) {
    currentPlanningSubtab = mode;
    const isSimple = (mode === 'simple');
    const btnSimple = document.getElementById('subtabBtnPlanSimple');
    const btnComplex = document.getElementById('subtabBtnPlanComplex');
    const viewSimple = document.getElementById('planSubviewSimple');
    const viewComplex = document.getElementById('planSubviewComplex');
    const descEl = document.getElementById('planSubtabDesc');

    if (btnSimple) btnSimple.classList.toggle('active', isSimple);
    if (btnComplex) btnComplex.classList.toggle('active', !isSimple);
    if (viewSimple) viewSimple.classList.toggle('active', isSimple);
    if (viewComplex) viewComplex.classList.toggle('active', !isSimple);

    if (descEl) {
        descEl.textContent = isSimple
            ? 'Fast preset recommendation questionnaire'
            : 'Interactive criteria questionnaire and weighted score optimizer';
    }

    if (!isSimple) {
        const frame = document.getElementById('plannerFrame');
        if (frame && (!frame.src || frame.src === 'about:blank' || frame.src.endsWith('/'))) {
            frame.src = '/planner';
        }
    }
}

/**
 * Reloads the Planner Wizard iframe with the latest data shape configuration.
 */
function reloadPlannerIframe() {
    const frame = document.getElementById('plannerFrame');
    if (frame) frame.src = '/planner';
}

/**
 * Toggles the nested visual flow viewer iframe between embedded and full page display.
 */
function toggleViewerFullscreen() {
    const container = document.getElementById('viewerFrameContainer');
    const btn = document.getElementById('btnToggleViewerFull');
    if (!container) return;
    const isFull = container.classList.toggle('viewer-fullscreen');
    document.body.classList.toggle('viewer-open-fullscreen', isFull);
    if (btn) btn.textContent = isFull ? 'Exit full view' : 'Open full view';
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const container = document.getElementById('viewerFrameContainer');
        if (container && container.classList.contains('viewer-fullscreen')) {
            toggleViewerFullscreen();
        }
    }
});

/**
 * Sets the document path input value when a discovered document chip is clicked.
 *
 * @param {string} path - Selected document filesystem path.
 */
function selectDocPath(path) {
    const input = document.getElementById('inpPdfPath');
    if (input) input.value = path;
}

/**
 * Computes heuristic primary and fallback presets based on planning questionnaire
 * selections and updates UI badges.
 */
function updateSuggestedPlan() {
    const taxEl = document.getElementById('planTaxonomy');
    const latEl = document.getElementById('planLatency');
    if (!taxEl || !latEl) return;

    const tax = taxEl.value;
    const lat = latEl.value;

    let primary = 'docling_fast';
    let fallback = 'docling_deep';

    if (tax === 'scanned_archive' || tax === 'form_heavy' || lat === 'maximum_accuracy') {
        primary = 'docling_deep';
        fallback = 'pypdfium_rapidocr';
    } else if (lat === 'fast_low_cost') {
        primary = 'docling_fast';
        fallback = 'pypdfium_rapidocr';
    }

    const primaryBadge = document.getElementById('planPrimaryBadge');
    const fallbackBadge = document.getElementById('planFallbackBadge');
    if (primaryBadge) primaryBadge.textContent = primary;
    if (fallbackBadge) fallbackBadge.textContent = fallback;
}

/**
 * No-op UI hook for initializing the guided Custom OCR Preset Builder modal in the Web Hub.
 */
function initCustomPresetBuilderModal() {
    // TODO(TASK-207): Render the 'Add / Connect Custom OCR Preset' modal with the community OCR recipe
    // selector (TASK-208), local app / web service inputs, and 'Test Connection' button.
}

/**
 * No-op UI hook for initializing the interactive Document Cleanup & Postprocessing checklist card.
 */
function initPostprocessingChecklistCard() {
    // TODO(TASK-506): Bind visual checkboxes in the Web Hub for stripping company letterheads (TASK-502),
    // rejoining hyphenated line breaks (TASK-503), removing watermarks (TASK-504), and redacting PII (TASK-505).
}
