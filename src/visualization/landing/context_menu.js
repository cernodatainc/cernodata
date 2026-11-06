/**
 * src/visualization/landing/context_menu.js
 *
 * Context menu controller for workspace explorer files and parsing runs.
 * Supports file forgetting, run inspection, run removal, and quick navigation.
 */

let activeContextMenuTarget = null;

/**
 * Ensures the explorer context menu element exists in the DOM.
 * @returns {HTMLElement} Context menu DOM element.
 */
function getOrCreateExplorerContextMenu() {
    let menu = document.getElementById('explorerContextMenu');
    if (!menu) {
        menu = document.createElement('div');
        menu.id = 'explorerContextMenu';
        menu.className = 'explorer-context-menu';
        menu.setAttribute('role', 'menu');
        document.body.appendChild(menu);
    }
    return menu;
}

/**
 * Displays context menu for a document file.
 * @param {number} x - Client X coordinate.
 * @param {number} y - Client Y coordinate.
 * @param {string} docPath - Path to target document.
 */
function showExplorerFileContextMenu(x, y, docPath) {
    if (!docPath) return;
    activeContextMenuTarget = { type: 'file', docPath };
    const menu = getOrCreateExplorerContextMenu();
    const parts = docPath.replace(/\\/g, '/').split('/');
    const fileName = parts[parts.length - 1] || docPath;

    menu.innerHTML = `<div class="explorer-context-menu-header" title="${escapeHtml(docPath)}">${escapeHtml(fileName)}</div>`
        + `<button type="button" class="explorer-context-menu-item" onclick="onContextAction('explore')">`
        + `<span class="menu-action-label">Explore runs</span></button>`
        + `<button type="button" class="explorer-context-menu-item" onclick="onContextAction('plan')">`
        + `<span class="menu-action-label">Open planning</span></button>`
        + `<div class="explorer-context-menu-divider"></div>`
        + `<button type="button" class="explorer-context-menu-item danger-item" onclick="onContextAction('forget')">`
        + `<span class="menu-action-label">Forget file</span></button>`;

    positionContextMenu(menu, x, y);
}

/**
 * Displays context menu for a parsing run.
 * @param {number} x - Client X coordinate.
 * @param {number} y - Client Y coordinate.
 * @param {string} runId - Identifier of run.
 * @param {string} outputDir - Directory of run artifacts.
 * @param {string} docPath - Document path associated with run.
 */
function showExplorerRunContextMenu(x, y, runId, outputDir, docPath) {
    if (!runId && !outputDir) return;
    activeContextMenuTarget = { type: 'run', runId, outputDir, docPath };
    const menu = getOrCreateExplorerContextMenu();

    menu.innerHTML = `<div class="explorer-context-menu-header" title="${escapeHtml(runId || outputDir)}">Run: ${escapeHtml(runId || outputDir)}</div>`
        + `<button type="button" class="explorer-context-menu-item" onclick="onContextAction('inspect_run')">`
        + `<span class="menu-action-label">Inspect pages</span></button>`
        + `<button type="button" class="explorer-context-menu-item" onclick="onContextAction('copy_run_id')">`
        + `<span class="menu-action-label">Copy run ID</span></button>`
        + `<div class="explorer-context-menu-divider"></div>`
        + `<button type="button" class="explorer-context-menu-item danger-item" onclick="onContextAction('remove_run')">`
        + `<span class="menu-action-label">Remove run</span></button>`;

    positionContextMenu(menu, x, y);
}

/**
 * Positions menu within viewport boundaries.
 * @param {HTMLElement} menu - Context menu element.
 * @param {number} x - Target X coordinate.
 * @param {number} y - Target Y coordinate.
 */
function positionContextMenu(menu, x, y) {
    menu.classList.add('visible');
    menu.style.display = 'block';

    const menuRect = menu.getBoundingClientRect();
    const maxX = window.innerWidth - (menuRect.width || 170) - 8;
    const maxY = window.innerHeight - (menuRect.height || 120) - 8;

    const posX = Math.max(8, Math.min(x, maxX));
    const posY = Math.max(8, Math.min(y, maxY));

    menu.style.left = `${posX}px`;
    menu.style.top = `${posY}px`;
}

/** Hides the active explorer context menu. */
function hideExplorerContextMenu() {
    const menu = document.getElementById('explorerContextMenu');
    if (menu) {
        menu.classList.remove('visible');
        menu.style.display = 'none';
    }
    activeContextMenuTarget = null;
}

/**
 * Dispatches context action and closes menu.
 * @param {string} action - Action identifier.
 */
async function onContextAction(action) {
    const target = activeContextMenuTarget;
    hideExplorerContextMenu();
    if (!target) return;

    if (action === 'explore' && target.docPath) {
        selectExplorerDoc(target.docPath);
    } else if (action === 'plan' && target.docPath) {
        selectDocAndOpenPlanning(target.docPath);
    } else if (action === 'forget' && target.docPath) {
        await forgetExplorerFile(target.docPath);
    } else if (action === 'inspect_run' && target.runId) {
        selectExplorerRun(target.runId, target.outputDir, target.docPath);
    } else if (action === 'remove_run' && target.runId) {
        if (typeof removeExplorerRun === 'function') {
            await removeExplorerRun(target.runId, target.outputDir, target.docPath);
        }
    } else if (action === 'copy_run_id' && (target.runId || target.outputDir)) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(target.runId || target.outputDir);
        }
    }
}

/**
 * Sends request to backend to forget a file and refreshes explorer view.
 * @param {string} docPath - Path of document to forget.
 */
async function forgetExplorerFile(docPath) {
    if (!docPath) return;
    try {
        const resp = await fetch('/api/forget_file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: docPath, document_path: docPath }),
        });
        if (!resp.ok) {
            console.log('[WARN] Failed to forget file:', resp.statusText);
            return;
        }

        if (currentExplorerDoc === docPath) {
            currentExplorerDoc = '';
            currentExplorerRun = '';
        }
        await loadFileRunMappings();
    } catch (e) {
        console.log('[WARN] Error forgetting file:', e);
    }
}

/** Handles contextmenu on file elements. */
function handleExplorerFileContextMenu(event, docPath) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
        showExplorerFileContextMenu(event.clientX, event.clientY, docPath);
    }
}

/** Handles contextmenu on run elements. */
function handleExplorerRunContextMenu(event, runId, outputDir, docPath) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
        showExplorerRunContextMenu(event.clientX, event.clientY, runId, outputDir, docPath);
    }
}

// Global dismiss listeners
document.addEventListener('click', function(e) {
    const menu = document.getElementById('explorerContextMenu');
    if (menu && menu.classList.contains('visible') && !menu.contains(e.target)) {
        hideExplorerContextMenu();
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideExplorerContextMenu();
});

window.addEventListener('scroll', function() {
    hideExplorerContextMenu();
}, true);

// Delegated contextmenu listener
document.addEventListener('contextmenu', function(e) {
    const runRow = e.target.closest('[data-run-id], .run-row');
    if (runRow) {
        const runId = runRow.getAttribute('data-run-id');
        const docPath = runRow.getAttribute('data-doc-path');
        if (runId) {
            e.preventDefault();
            e.stopPropagation();
            showExplorerRunContextMenu(e.clientX, e.clientY, runId, runId, docPath);
            return;
        }
    }
    const fileRow = e.target.closest('[data-doc-path], .file-row, .tree-file-node');
    if (fileRow) {
        const docPath = fileRow.getAttribute('data-doc-path')
            || (fileRow.querySelector('[title]') ? fileRow.querySelector('[title]').getAttribute('title') : '');
        if (docPath) {
            e.preventDefault();
            e.stopPropagation();
            showExplorerFileContextMenu(e.clientX, e.clientY, docPath);
        }
    }
});
