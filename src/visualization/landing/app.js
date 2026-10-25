/**
 * src/visualization/landing/app.js
 *
 * Dashboard application bootstrap, lifecycle initialization,
 * and initial data preloading on DOMContentLoaded.
 */

window.addEventListener('DOMContentLoaded', () => {
    if (typeof updateSuggestedPlan === 'function') updateSuggestedPlan();
    if (typeof loadAvailableDocuments === 'function') loadAvailableDocuments();
    if (typeof loadPreviousRunsList === 'function') loadPreviousRunsList();
    if (typeof loadFileRunMappings === 'function') loadFileRunMappings();
    if (typeof refreshResultsData === 'function') refreshResultsData();
    if (typeof loadRunsGrid === 'function') loadRunsGrid();

    const frame = document.getElementById('viewerFrame');
    if (frame) {
        function hideViewerHeader() {
            try {
                const doc = frame.contentDocument;
                if (!doc || !doc.head || doc.getElementById('embedOverrides')) return;
                const style = doc.createElement('style');
                style.id = 'embedOverrides';
                style.textContent = 'body > header { display: none !important; }';
                doc.head.appendChild(style);
            } catch (e) { }
        }
        frame.addEventListener('load', hideViewerHeader);
        hideViewerHeader();
    }
});
