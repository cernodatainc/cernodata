/**
 * src/visualization/viewer/js/app.js
 *
 * Viewer initialization, input layer mounting, image synchronization,
 * and runtime startup.
 */

// Initialize input layer architecture
if (window.viewerInputManager) {
    window.viewerInputManager.init();
}

/**
 * Initializes and starts the visual inspection viewer.
 * Hydrates state from window.VIEWER_DATA if injected, or fetches
 * asynchronously from /api/viewer_data using URL search parameters.
 */
async function startViewer() {
    if (window.viewerInputManager) {
        window.viewerInputManager.init();
    }

    const urlParams = new URLSearchParams(window.location.search);
    const outputDirParam = urlParams.get('output_dir');
    const targetPageParam = parseInt(urlParams.get('page') || '1', 10) || 1;
    const stepParam = urlParams.get('step');

    if (window.VIEWER_DATA && window.VIEWER_DATA.dom && window.VIEWER_DATA.dom.nodes && window.VIEWER_DATA.dom.nodes.length > 0) {
        hydrateViewer(window.VIEWER_DATA, targetPageParam);
        return;
    }

    try {
        let fetchUrl = '/api/viewer_data';
        const params = [];
        if (outputDirParam) params.push(`output_dir=${encodeURIComponent(outputDirParam)}`);
        if (stepParam) params.push(`step=${encodeURIComponent(stepParam)}`);
        if (params.length > 0) fetchUrl += `?${params.join('&')}`;

        const resp = await fetch(fetchUrl);
        if (resp.ok) {
            const data = await resp.json();
            hydrateViewer(data, targetPageParam);
            return;
        }
    } catch (e) {
        console.log('[INFO] Backend /api/viewer_data not reachable, using offline state.');
    }

    initPageControls();
    switchPage(targetPageParam);
}

const pageImgEl = document.getElementById('pageImg');
if (pageImgEl) {
    pageImgEl.addEventListener('load', () => {
        if (typeof updateSvgViewBox === 'function') {
            updateSvgViewBox();
        }
        if (typeof renderSVGOverlays === 'function') {
            renderSVGOverlays();
        }
    });
}

startViewer();
