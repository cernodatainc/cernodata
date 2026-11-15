/**
 * src/visualization/viewer/js/workspace_dock.js
 *
 * Dockable, foldable, and draggable floating panels for the Node Viewer
 * (inspector pane) and top toolboxes, plus the keystroke hint badge overlay.
 */

let _activeFloatingDrag = null;
let _floatingZCounter = 1120;

/**
 * Brings a floating panel or toolbox to the front of the z-order stack.
 *
 * @param {HTMLElement|null} el - Floating DOM element.
 */
function _bringFloatingToFront(el) {
    if (!el) return;
    _floatingZCounter += 1;
    el.style.zIndex = String(_floatingZCounter);
}

/**
 * Toggles folded (collapsed) state of the Node Viewer (#inspectorPane).
 *
 * @param {boolean|null} [force=null] - Optional explicit folded state.
 * @returns {boolean} Updated folded state.
 */
function toggleInspectorFold(force = null) {
    const pane = document.getElementById('inspectorPane');
    const btn = document.getElementById('btnFoldInspector');
    if (!pane) return false;

    const nextFolded = (force !== null) ? Boolean(force) : !pane.classList.contains('folded');
    pane.classList.toggle('folded', nextFolded);

    if (btn) {
        btn.textContent = nextFolded ? 'Unfold' : 'Fold';
        btn.title = nextFolded ? 'Unfold node viewer' : 'Fold node viewer';
    }
    return nextFolded;
}

/**
 * Toggles unanchored (floating/draggable) vs. docked state of the Node Viewer (#inspectorPane).
 *
 * @param {boolean|null} [force=null] - Optional explicit unanchored state.
 * @returns {boolean} Updated unanchored state.
 */
function toggleInspectorAnchor(force = null) {
    const pane = document.getElementById('inspectorPane');
    const btn = document.getElementById('btnAnchorInspector');
    if (!pane) return false;

    const nextUnanchored = (force !== null) ? Boolean(force) : !pane.classList.contains('unanchored');
    if (nextUnanchored) {
        const vw = window.innerWidth || 1280;
        const vh = window.innerHeight || 800;
        const defaultWidth = Math.min(480, Math.max(320, Math.round(vw * 0.36)));
        const defaultHeight = Math.min(680, Math.max(320, vh - 140));
        const defaultLeft = Math.max(16, vw - defaultWidth - 20);
        const defaultTop = 108;

        pane.classList.add('unanchored');
        if (!pane.style.left) pane.style.left = `${defaultLeft}px`;
        if (!pane.style.top) pane.style.top = `${defaultTop}px`;
        if (!pane.style.width) pane.style.width = `${defaultWidth}px`;
        if (!pane.style.height) pane.style.height = `${defaultHeight}px`;
        _bringFloatingToFront(pane);
    } else {
        pane.classList.remove('unanchored');
        pane.style.left = '';
        pane.style.top = '';
        pane.style.width = '';
        pane.style.height = '';
        pane.style.zIndex = '';
    }

    if (btn) {
        btn.textContent = nextUnanchored ? 'Dock' : 'Unanchor';
        btn.title = nextUnanchored ? 'Dock node viewer back to side panel' : 'Unanchor and float node viewer';
    }
    return nextUnanchored;
}

/**
 * Toggles unanchored (floating/draggable) vs. docked state of a top toolbox.
 *
 * @param {string} toolboxId - DOM element ID of the target .toolbox.
 * @param {boolean|null} [force=null] - Optional explicit unanchored state.
 * @returns {boolean} Updated unanchored state.
 */
function toggleToolboxAnchor(toolboxId, force = null) {
    const toolbox = document.getElementById(toolboxId);
    if (!toolbox) return false;

    const nextUnanchored = (force !== null) ? Boolean(force) : !toolbox.classList.contains('unanchored');
    const btn = toolbox.querySelector('.toolbox-anchor-btn');

    if (nextUnanchored) {
        const rect = toolbox.getBoundingClientRect ? toolbox.getBoundingClientRect() : { left: 24, top: 72 };
        const parent = toolbox.parentNode;
        if (parent && !document.querySelector(`.toolbox-placeholder[data-placeholder-for="${toolboxId}"]`)) {
            const ph = document.createElement('span');
            ph.className = 'toolbox-placeholder';
            ph.setAttribute('data-placeholder-for', toolboxId);
            ph.style.display = 'none';
            parent.insertBefore(ph, toolbox);
        }

        toolbox.classList.add('unanchored');
        toolbox.style.left = `${Math.max(8, Math.round(rect.left))}px`;
        toolbox.style.top = `${Math.max(8, Math.round(rect.top))}px`;
        _bringFloatingToFront(toolbox);
    } else {
        toolbox.classList.remove('unanchored');
        toolbox.style.left = '';
        toolbox.style.top = '';
        toolbox.style.zIndex = '';

        const ph = document.querySelector(`.toolbox-placeholder[data-placeholder-for="${toolboxId}"]`);
        if (ph && ph.parentNode) {
            ph.parentNode.insertBefore(toolbox, ph);
            ph.parentNode.removeChild(ph);
        }
    }

    if (btn) {
        btn.textContent = nextUnanchored ? 'Dock' : 'Float';
        btn.title = nextUnanchored ? 'Dock toolbox back to top bar' : 'Unanchor toolbox to drag anywhere';
    }
    return nextUnanchored;
}

/**
 * Toggles the keystroke badge overlay across all tools that declare data-key-hint.
 *
 * @param {boolean|null} [force=null] - Optional explicit enabled state.
 * @returns {boolean} Updated key hints overlay visibility.
 */
function updateKeyHintsOverlay(force = null) {
    const chk = document.getElementById('toggleKeyHints');
    const enabled = (force !== null)
        ? Boolean(force)
        : (chk ? Boolean(chk.checked) : false);

    if (chk && force !== null) {
        chk.checked = enabled;
    }
    if (typeof document !== 'undefined' && document.body && document.body.classList) {
        document.body.classList.toggle('show-key-hints', enabled);
    }
    return enabled;
}

/**
 * Begins dragging a floating panel/toolbox when its header/handle is pressed.
 *
 * @param {MouseEvent} evt - MouseDown event.
 * @param {HTMLElement} targetEl - Floating element to move.
 */
function _startFloatingElementDrag(evt, targetEl) {
    if (!targetEl || !targetEl.classList || !targetEl.classList.contains('unanchored')) return;
    if (evt.target && evt.target.closest && evt.target.closest('button, input, select, textarea, a')) {
        return;
    }
    evt.preventDefault();
    const rect = targetEl.getBoundingClientRect();
    _bringFloatingToFront(targetEl);
    _activeFloatingDrag = {
        el: targetEl,
        offsetX: evt.clientX - rect.left,
        offsetY: evt.clientY - rect.top
    };
}

/**
 * Initializes pointer listeners for dragging floating inspector and toolboxes.
 */
function initWorkspaceDockDragHandlers() {
    if (typeof document === 'undefined' || typeof window === 'undefined') return;

    const inspectorHeader = document.getElementById('inspectorHeader');
    const inspectorPane = document.getElementById('inspectorPane');
    if (inspectorHeader && inspectorPane && !inspectorHeader._dockBound) {
        inspectorHeader._dockBound = true;
        inspectorHeader.addEventListener('mousedown', (evt) => {
            _startFloatingElementDrag(evt, inspectorPane);
        });
    }

    const toolboxes = document.querySelectorAll('.toolbox');
    toolboxes.forEach((tb) => {
        const header = tb.querySelector('.toolbox-header');
        if (header && !header._dockBound) {
            header._dockBound = true;
            header.addEventListener('mousedown', (evt) => {
                _startFloatingElementDrag(evt, tb);
            });
        }
    });

    if (!window._workspaceDockListenersBound) {
        window._workspaceDockListenersBound = true;
        window.addEventListener('mousemove', (evt) => {
            if (!_activeFloatingDrag || !_activeFloatingDrag.el) return;
            const el = _activeFloatingDrag.el;
            const vw = window.innerWidth || 1280;
            const vh = window.innerHeight || 800;
            const maxLeft = Math.max(0, vw - 80);
            const maxTop = Math.max(0, vh - 40);
            const nextLeft = Math.min(maxLeft, Math.max(0, Math.round(evt.clientX - _activeFloatingDrag.offsetX)));
            const nextTop = Math.min(maxTop, Math.max(0, Math.round(evt.clientY - _activeFloatingDrag.offsetY)));
            el.style.left = `${nextLeft}px`;
            el.style.top = `${nextTop}px`;
        });
        window.addEventListener('mouseup', () => {
            _activeFloatingDrag = null;
        });
    }
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWorkspaceDockDragHandlers);
    } else {
        initWorkspaceDockDragHandlers();
    }
}

/**
 * Jumps from a selected node in the DOM tab to its corresponding violation card
 * in the Violations tab, unfolding the inspector if needed.
 *
 * @param {string} nodeId - Target DOM node identifier.
 * @param {string|null} [violationId=null] - Optional specific violation ID.
 */
function jumpToViolationInTab(nodeId, violationId = null) {
    const pane = document.getElementById('inspectorPane');
    if (pane && pane.classList && pane.classList.contains('folded')) {
        toggleInspectorFold(false);
    }
    if (typeof showTab === 'function') {
        showTab(null, 'violTab');
    }
    if (typeof renderViolationsList === 'function') {
        renderViolationsList();
    }

    let targetCard = null;
    if (violationId) {
        targetCard = document.getElementById(`viol-card-${violationId}`);
    }
    if (!targetCard && nodeId) {
        targetCard = document.querySelector(`#violListContainer .viol-card[data-node-id="${nodeId}"]`)
            || document.getElementById(`viol-card-incorrect-${nodeId}`);
    }
    if (targetCard) {
        if (typeof targetCard.scrollIntoView === 'function') {
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (targetCard.classList) {
            targetCard.classList.add('viol-card-flash');
            setTimeout(() => {
                targetCard.classList.remove('viol-card-flash');
            }, 1500);
        }
    }
}
