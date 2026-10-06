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
    if (typeof refreshResultsData === 'function') refreshResultsData();
    if (typeof loadRunsGrid === 'function') loadRunsGrid();
});
