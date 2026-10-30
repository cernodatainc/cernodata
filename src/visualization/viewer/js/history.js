/**
 * src/visualization/viewer/js/history.js
 *
 * Diff-list and cursor-managed undo/redo state management for interactive document annotations.
 * Instead of retaining deep clones of entire DOM trees, changes are recorded as atomic,
 * reversible diff entries appended to a diff list. Undo/redo maintains an integer cursor
 * over this list, applying inverse or forward changes in-place.
 */

let _bannerTimer = null;

/**
 * Displays a standardized floating notification banner with severity styling.
 *
 * @param {string} message - Notification text.
 * @param {'info'|'success'|'warn'|'error'} [type='info'] - Severity level.
 * @param {number} [duration=3500] - Display duration in milliseconds (0 for persistent).
 */
function showStatusBanner(message, type = 'info', duration = 3500) {
    const banner = document.getElementById('statusBanner');
    if (!banner) return;

    if (_bannerTimer) {
        clearTimeout(_bannerTimer);
        _bannerTimer = null;
    }

    banner.className = `status-banner status-${type}`;
    banner.textContent = message;
    banner.style.display = 'block';

    if (duration > 0) {
        _bannerTimer = setTimeout(() => {
            banner.style.display = 'none';
            _bannerTimer = null;
        }, duration);
    }
}

/**
 * Manages an ordered list of atomic run modification diffs and a playback cursor.
 */
class RunDiffManager {
    constructor(maxEntries = 100) {
        this.diffList = [];
        this.cursor = 0;
        this.maxEntries = maxEntries;
    }

    /**
     * Appends an atomic reversible diff entry to the run diff list.
     * Truncates any redo history beyond the current cursor position.
     *
     * @param {Object} entry - Diff entry descriptor.
     * @returns {Object} Normalized diff entry.
     */
    recordDiff(entry) {
        if (!entry) return null;

        if (this.cursor < this.diffList.length) {
            this.diffList = this.diffList.slice(0, this.cursor);
        }

        const normalized = {
            id: entry.id || `diff_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            timestamp: entry.timestamp || new Date().toISOString(),
            action: entry.action || 'modify',
            description: entry.description || 'Edit DOM',
            page: entry.page !== undefined ? entry.page : (typeof currentPage !== 'undefined' ? currentPage : 1),
            removed: Array.isArray(entry.removed) ? JSON.parse(JSON.stringify(entry.removed)) : [],
            inserted: Array.isArray(entry.inserted) ? JSON.parse(JSON.stringify(entry.inserted)) : [],
            beforeSelection: entry.beforeSelection
                ? JSON.parse(JSON.stringify(entry.beforeSelection))
                : { selectedNodeId: (typeof selectedNodeId !== 'undefined' ? selectedNodeId : null), selectedNodeIds: (typeof selectedNodeIds !== 'undefined' ? [...selectedNodeIds] : []) },
            afterSelection: entry.afterSelection
                ? JSON.parse(JSON.stringify(entry.afterSelection))
                : { selectedNodeId: (typeof selectedNodeId !== 'undefined' ? selectedNodeId : null), selectedNodeIds: (typeof selectedNodeIds !== 'undefined' ? [...selectedNodeIds] : []) },
            meta: entry.meta ? JSON.parse(JSON.stringify(entry.meta)) : {}
        };

        this.diffList.push(normalized);
        if (this.diffList.length > this.maxEntries) {
            this.diffList.shift();
        }
        this.cursor = this.diffList.length;
        this.updateButtons();
        return normalized;
    }

    /**
     * Backward-compatibility wrapper for legacy snapshot push requests.
     *
     * @param {string|Object} desc - Description or diff object.
     */
    pushSnapshot(desc) {
        if (typeof desc === 'object' && desc !== null) {
            return this.recordDiff(desc);
        }
        return this.recordDiff({
            action: 'modify',
            description: typeof desc === 'string' ? desc : 'User edit',
            removed: [],
            inserted: []
        });
    }

    /**
     * Applies inverse changes for a diff entry (undo).
     *
     * @param {Object} diff - Diff record to revert.
     */
    applyBackward(diff) {
        if (!diff || !domData || !Array.isArray(domData.nodes)) return;

        // 1. Remove nodes inserted by this forward action
        if (diff.inserted && diff.inserted.length > 0) {
            const insertedIds = new Set(diff.inserted.map(item => item.node && item.node.node_id).filter(Boolean));
            domData.nodes = domData.nodes.filter(n => !insertedIds.has(n.node_id));
        }

        // 2. Re-insert nodes removed by this forward action at their recorded indices
        if (diff.removed && diff.removed.length > 0) {
            const sortedRemoved = [...diff.removed].sort((a, b) => a.index - b.index);
            for (const item of sortedRemoved) {
                if (!item.node) continue;
                const idx = Math.min(Math.max(0, item.index), domData.nodes.length);
                domData.nodes.splice(idx, 0, JSON.parse(JSON.stringify(item.node)));
            }
        }

        // 3. Revert violation reassignments if present in metadata
        if (diff.meta && Array.isArray(diff.meta.violation_reassignments)) {
            const viols = typeof getViolationsList === 'function' ? getViolationsList() : [];
            diff.meta.violation_reassignments.forEach(r => {
                const v = viols.find(viol => viol.violation_id === r.violation_id);
                if (v) v.node_id = r.old_node_id;
            });
        }

        // 4. Restore page if different
        if (diff.page && typeof switchPage === 'function' && typeof currentPage !== 'undefined' && diff.page !== currentPage) {
            switchPage(diff.page);
        }

        // 5. Restore prior selection
        if (diff.beforeSelection) {
            selectedNodeId = diff.beforeSelection.selectedNodeId;
            selectedNodeIds = [...(diff.beforeSelection.selectedNodeIds || [])];
        }

        // 6. Refresh views
        this._refreshViews();
    }

    /**
     * Applies forward changes for a diff entry (redo).
     *
     * @param {Object} diff - Diff record to re-apply.
     */
    applyForward(diff) {
        if (!diff || !domData || !Array.isArray(domData.nodes)) return;

        // 1. Remove nodes specified in removed list
        if (diff.removed && diff.removed.length > 0) {
            const removedIds = new Set(diff.removed.map(item => item.node && item.node.node_id).filter(Boolean));
            domData.nodes = domData.nodes.filter(n => !removedIds.has(n.node_id));
        }

        // 2. Insert nodes specified in inserted list at their recorded indices
        if (diff.inserted && diff.inserted.length > 0) {
            const sortedInserted = [...diff.inserted].sort((a, b) => a.index - b.index);
            for (const item of sortedInserted) {
                if (!item.node) continue;
                const idx = Math.min(Math.max(0, item.index), domData.nodes.length);
                domData.nodes.splice(idx, 0, JSON.parse(JSON.stringify(item.node)));
            }
        }

        // 3. Apply violation reassignments
        if (diff.meta && Array.isArray(diff.meta.violation_reassignments)) {
            const viols = typeof getViolationsList === 'function' ? getViolationsList() : [];
            diff.meta.violation_reassignments.forEach(r => {
                const v = viols.find(viol => viol.violation_id === r.violation_id);
                if (v) v.node_id = r.new_node_id;
            });
        }

        // 4. Restore page if different
        if (diff.page && typeof switchPage === 'function' && typeof currentPage !== 'undefined' && diff.page !== currentPage) {
            switchPage(diff.page);
        }

        // 5. Restore target selection
        if (diff.afterSelection) {
            selectedNodeId = diff.afterSelection.selectedNodeId;
            selectedNodeIds = [...(diff.afterSelection.selectedNodeIds || [])];
        }

        // 6. Refresh views
        this._refreshViews();
    }

    /**
     * Triggers UI and tree re-rendering across the viewer.
     */
    _refreshViews() {
        if (typeof syncDomAndViolations === 'function') syncDomAndViolations();
        if (typeof recalculateScoring === 'function') recalculateScoring();
        if (typeof renderDOMTree === 'function') renderDOMTree();
        if (typeof renderSVGOverlays === 'function') renderSVGOverlays();
        if (typeof renderSelectedEditor === 'function') renderSelectedEditor();
        if (typeof renderViolationsList === 'function') renderViolationsList();
    }

    /**
     * Undoes the last modification by moving the cursor backward.
     *
     * @returns {boolean} True if an operation was undone.
     */
    undo() {
        if (!this.canUndo()) {
            showStatusBanner('Nothing to undo.', 'info', 2000);
            return false;
        }

        this.cursor--;
        const diff = this.diffList[this.cursor];
        this.applyBackward(diff);
        this.updateButtons();
        showStatusBanner(`Undo: ${diff.description}`, 'info', 2500);
        return true;
    }

    /**
     * Redoes the next modification by moving the cursor forward.
     *
     * @returns {boolean} True if an operation was redone.
     */
    redo() {
        if (!this.canRedo()) {
            showStatusBanner('Nothing to redo.', 'info', 2000);
            return false;
        }

        const diff = this.diffList[this.cursor];
        this.applyForward(diff);
        this.cursor++;
        this.updateButtons();
        showStatusBanner(`Redo: ${diff.description}`, 'info', 2500);
        return true;
    }

    canUndo() {
        return this.cursor > 0;
    }

    canRedo() {
        return this.cursor < this.diffList.length;
    }

    /**
     * Returns the active diff slice up to cursor position.
     *
     * @returns {Array<Object>} Applied diff list.
     */
    getActiveDiffs() {
        return this.diffList.slice(0, this.cursor);
    }

    /**
     * Returns full diff list including undone entries.
     *
     * @returns {Array<Object>} All recorded diffs.
     */
    getAllDiffs() {
        return [...this.diffList];
    }

    /**
     * Resets the diff list and cursor.
     */
    clear() {
        this.diffList = [];
        this.cursor = 0;
        this.updateButtons();
    }

    /**
     * Synchronizes toolbar button states and tooltips with current cursor.
     */
    updateButtons() {
        const btnUndo = document.getElementById('btnUndo');
        const btnRedo = document.getElementById('btnRedo');
        if (btnUndo) {
            btnUndo.disabled = !this.canUndo();
            btnUndo.title = this.canUndo()
                ? `Undo: ${this.diffList[this.cursor - 1].description} (Ctrl+Z)`
                : 'Nothing to undo (Ctrl+Z)';
        }
        if (btnRedo) {
            btnRedo.disabled = !this.canRedo();
            btnRedo.title = this.canRedo()
                ? `Redo: ${this.diffList[this.cursor].description} (Ctrl+Y)`
                : 'Nothing to redo (Ctrl+Y)';
        }
    }
}

window.RunDiffManager = RunDiffManager;
window.HistoryManager = RunDiffManager;
window.runDiffManager = new RunDiffManager();
window.historyManager = window.runDiffManager;

function undo() {
    return window.runDiffManager.undo();
}

function redo() {
    return window.runDiffManager.redo();
}

function recordRunDiff(entry) {
    return window.runDiffManager.recordDiff(entry);
}

function pushHistorySnapshot(desc) {
    return window.runDiffManager.pushSnapshot(desc);
}
