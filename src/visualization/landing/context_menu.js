/**
 * src/visualization/landing/context_menu.js
 *
 * Context menu handler for workspace explorer items.
 * Allows forgetting a document by right-clicking on it in the file explorer,
 * causing it to disappear from the explorer without deleting historical parsing runs.
 */

let activeContextMenuDoc = '';

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
        menu.innerHTML = '<div class="explorer-context-menu-header" id="explorerContextMenuHeader">Document</div>'
            + '<button type="button" class="explorer-context-menu-item" id="btnForgetFile" onclick="onContextForgetClicked()">'
            + '<span class="menu-action-label">Forget file</span>'
            + '</button>';
        document.body.appendChild(menu);
    }
    return menu;
}

/**
 * Displays the context menu at specified viewport coordinates for a document path.
 * @param {number} x - Client X coordinate.
 * @param {number} y - Client Y coordinate.
 * @param {string} docPath - Path to target document.
 */
function showExplorerContextMenu(x, y, docPath) {
    if (!docPath) return;
    activeContextMenuDoc = docPath;
    const menu = getOrCreateExplorerContextMenu();
    const header = document.getElementById('explorerContextMenuHeader');
    if (header) {
        const parts = docPath.replace(/\\/g, '/').split('/');
        const fileName = parts[parts.length - 1] || docPath;
        header.textContent = fileName;
        header.title = docPath;
    }

    menu.classList.add('visible');
    menu.style.display = 'block';

    const menuRect = menu.getBoundingClientRect();
    const maxX = window.innerWidth - (menuRect.width || 160) - 8;
    const maxY = window.innerHeight - (menuRect.height || 80) - 8;

    const posX = Math.max(8, Math.min(x, maxX));
    const posY = Math.max(8, Math.min(y, maxY));

    menu.style.left = `${posX}px`;
    menu.style.top = `${posY}px`;
}

/**
 * Hides the active explorer context menu.
 */
function hideExplorerContextMenu() {
    const menu = document.getElementById('explorerContextMenu');
    if (menu) {
        menu.classList.remove('visible');
        menu.style.display = 'none';
    }
    activeContextMenuDoc = '';
}

/**
 * Invoked when user clicks "Forget file" from the context menu.
 */
async function onContextForgetClicked() {
    const docPath = activeContextMenuDoc;
    hideExplorerContextMenu();
    if (docPath) {
        await forgetExplorerFile(docPath);
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

/**
 * Handles contextmenu event on explorer file rows.
 * @param {MouseEvent} event - Native mouse event.
 * @param {string} docPath - Path to target document.
 */
function handleExplorerFileContextMenu(event, docPath) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
        showExplorerContextMenu(event.clientX, event.clientY, docPath);
    }
}

// Global dismiss listeners
document.addEventListener('click', function(e) {
    const menu = document.getElementById('explorerContextMenu');
    if (menu && menu.classList.contains('visible')) {
        if (!menu.contains(e.target)) {
            hideExplorerContextMenu();
        }
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideExplorerContextMenu();
    }
});

window.addEventListener('scroll', function() {
    hideExplorerContextMenu();
}, true);

// Delegated contextmenu listener across explorer container
document.addEventListener('contextmenu', function(e) {
    const fileRow = e.target.closest('[data-doc-path], .file-row, .tree-file-node');
    if (fileRow) {
        const docPath = fileRow.getAttribute('data-doc-path')
            || (fileRow.querySelector('[title]') ? fileRow.querySelector('[title]').getAttribute('title') : '');
        if (docPath) {
            e.preventDefault();
            e.stopPropagation();
            showExplorerContextMenu(e.clientX, e.clientY, docPath);
        }
    }
});
