/**
 * src/visualization/landing/navigation.js
 *
 * Tab navigation, active view section switching, document path selection,
 * and dynamic preset recommendation badges.
 */

let currentTab = 'input';

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

    if (tabName === 'results') {
        if (typeof refreshResultsData === 'function') refreshResultsData();
        const frame = document.getElementById('viewerFrame');
        if (frame && (!frame.src || frame.src === 'about:blank' || frame.src.endsWith('/'))) {
            if (typeof reloadViewerIframe === 'function') reloadViewerIframe();
        }
    } else if (tabName === 'runs') {
        if (typeof loadRunsGrid === 'function') loadRunsGrid();
    }
}

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
