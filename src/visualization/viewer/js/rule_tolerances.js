/**
 * src/visualization/viewer/js/rule_tolerances.js
 *
 * Interactive "Rule Tolerances" sliding configuration drawer (TASK-710) allowing
 * real-time sensitivity adjustments and immediate score recalculation.
 */

const DEFAULT_RULE_TOLERANCES = {
    target_confidence_threshold: 0.82,
    penalty_weight: 1.0,
    min_table_alignment: 0.80,
    suppress_warnings: false,
    layers: {
        symbols: true,
        language: true,
        tables: true,
        reading_order: true
    }
};

let ruleTolerancesState = JSON.parse(JSON.stringify(DEFAULT_RULE_TOLERANCES));
let isRuleTolerancesOpen = false;

/**
 * Classifies a violation object into one of the configurable rule categories.
 *
 * @param {Object} viol - Violation record.
 * @returns {'symbols'|'language'|'tables'|'reading_order'} Category key.
 */
function _classifyViolationCategory(viol) {
    const raw = `${(viol && viol.rule_type) || ''} ${(viol && viol.type) || ''} ${(viol && viol.description) || ''}`.toLowerCase();
    if (raw.includes('table') || raw.includes('column') || raw.includes('cell')) return 'tables';
    if (raw.includes('order') || raw.includes('overlap') || raw.includes('layout')) return 'reading_order';
    if (raw.includes('diacritic') || raw.includes('lang') || raw.includes('spell')) return 'language';
    return 'symbols';
}

/**
 * Evaluates current violations against ruleTolerancesState and updates _tolerance_ignored.
 */
function _applyToleranceFiltersToViolations() {
    const viols = typeof getViolationsList === 'function' ? getViolationsList() : [];
    const domNodes = (typeof domData !== 'undefined' && domData && Array.isArray(domData.nodes)) ? domData.nodes : [];

    for (const viol of viols) {
        if (!viol) continue;
        const cat = _classifyViolationCategory(viol);
        let ignored = !ruleTolerancesState.layers[cat];

        if (!ignored && ruleTolerancesState.suppress_warnings) {
            const sev = String(viol.severity || 'WARNING').toUpperCase();
            if (sev !== 'ERROR' && sev !== 'CRITICAL') {
                ignored = true;
            }
        }

        if (!ignored && cat === 'tables') {
            const node = domNodes.find(n => n.node_id === viol.node_id);
            const score = node && node.content && node.content.cell_alignment_score !== undefined
                ? Number(node.content.cell_alignment_score)
                : null;
            if (score !== null && score >= ruleTolerancesState.min_table_alignment) {
                ignored = true;
            }
        }

        viol._tolerance_ignored = ignored;
    }
}

/**
 * Updates numeric tolerance value and triggers synchronous real-time score recalculation.
 *
 * @param {string} key - Rule tolerance parameter key.
 * @param {number|boolean} value - Updated threshold/weight/flag value.
 */
function updateRuleTolerance(key, value) {
    if (key === 'suppress_warnings') {
        ruleTolerancesState.suppress_warnings = !!value;
    } else if (key in ruleTolerancesState) {
        ruleTolerancesState[key] = Number(value);
    }
    applyRuleTolerances();
}

/**
 * Updates an individual verification layer toggle in the Rule Tolerances drawer.
 *
 * @param {string} layerKey - Layer identifier ('symbols'|'language'|'tables'|'reading_order').
 * @param {boolean} enabled - Whether layer violations remain active.
 */
function toggleRuleToleranceLayer(layerKey, enabled) {
    if (layerKey in ruleTolerancesState.layers) {
        ruleTolerancesState.layers[layerKey] = !!enabled;
    }
    applyRuleTolerances();
}

/**
 * Applies rule tolerances to decisionData, recalculates per-page/overall confidence,
 * and refreshes all viewer overlays and badges in real time.
 */
function applyRuleTolerances(forceRebuild = false) {
    if (typeof decisionData === 'object' && decisionData !== null) {
        decisionData.target_confidence_threshold = ruleTolerancesState.target_confidence_threshold;
        decisionData.rule_tolerances = JSON.parse(JSON.stringify(ruleTolerancesState));
    }

    _applyToleranceFiltersToViolations();

    const summary = typeof recalculateScoring === 'function' ? recalculateScoring() : null;
    if (!summary) {
        if (typeof renderViolationsList === 'function') renderViolationsList();
        if (typeof renderDOMTree === 'function') renderDOMTree();
        if (typeof renderSVGOverlays === 'function') renderSVGOverlays();
    }

    renderRuleTolerancesDrawer(forceRebuild);
}

/**
 * Resets all rule tolerance sliders and layer toggles to defaults.
 */
function resetRuleTolerances() {
    ruleTolerancesState = JSON.parse(JSON.stringify(DEFAULT_RULE_TOLERANCES));
    const viols = typeof getViolationsList === 'function' ? getViolationsList() : [];
    viols.forEach(v => {
        if (v) v._tolerance_ignored = false;
    });
    if (rawDecisionData && rawDecisionData.target_confidence_threshold !== undefined && rawDecisionData.target_confidence_threshold !== null) {
        ruleTolerancesState.target_confidence_threshold = Number(rawDecisionData.target_confidence_threshold);
    }
    applyRuleTolerances(true);
}

/**
 * Toggles the sliding Rule Tolerances configuration drawer open/closed.
 *
 * @param {boolean} [forceState] - Optional explicit open state.
 */
function toggleRuleTolerancesDrawer(forceState) {
    isRuleTolerancesOpen = (forceState !== undefined) ? !!forceState : !isRuleTolerancesOpen;
    const drawer = document.getElementById('ruleTolerancesDrawer');
    const btn = document.getElementById('btnRuleTolerances');
    if (drawer) {
        drawer.hidden = !isRuleTolerancesOpen;
        drawer.classList.toggle('open', isRuleTolerancesOpen);
    }
    if (btn) {
        btn.classList.toggle('active', isRuleTolerancesOpen);
    }
    if (isRuleTolerancesOpen) {
        renderRuleTolerancesDrawer(true);
    }
}

/**
 * Renders controls and live score telemetry inside #ruleTolerancesDrawer.
 *
 * @param {boolean} [forceRebuild=false] - Whether to rebuild all input elements.
 */
function renderRuleTolerancesDrawer(forceRebuild = false) {
    const drawer = document.getElementById('ruleTolerancesDrawer');
    if (!drawer) return;

    const viols = typeof getViolationsList === 'function' ? getViolationsList() : [];
    const activeCount = viols.filter(v => !v.is_fixed && !v._tolerance_ignored && (typeof isSuppressed === 'function' ? !isSuppressed(v) : !v.suppressed)).length;
    const toleratedCount = viols.filter(v => !!v._tolerance_ignored).length;
    const score = (typeof decisionData === 'object' && decisionData && decisionData.overall_confidence !== undefined)
        ? Number(decisionData.overall_confidence).toFixed(4)
        : '1.0000';
    const status = (typeof decisionData === 'object' && decisionData && decisionData.status) || 'ACCEPT';

    const existingSummary = drawer.querySelector('#tolerancesSummaryBar');
    if (!forceRebuild && existingSummary) {
        existingSummary.innerHTML = `
            <span class="badge-status ${status === 'ACCEPT' ? 'pass' : 'fail'}">${escapeHtml(status)} (${score})</span>
            <span>Active Violations: <strong>${activeCount}</strong></span>
            <span>Tolerated: <strong>${toleratedCount}</strong></span>
        `;
        const lblThresh = drawer.querySelector('#lblAcceptThreshold');
        if (lblThresh) lblThresh.textContent = ruleTolerancesState.target_confidence_threshold.toFixed(2);
        const lblPenalty = drawer.querySelector('#lblPenaltyWeight');
        if (lblPenalty) lblPenalty.textContent = `${ruleTolerancesState.penalty_weight.toFixed(1)}x`;
        const lblAlign = drawer.querySelector('#lblTableAlign');
        if (lblAlign) lblAlign.textContent = ruleTolerancesState.min_table_alignment.toFixed(2);
        return;
    }

    drawer.innerHTML = `
        <div class="tolerances-drawer-header">
            <span class="tolerances-drawer-title">Rule Tolerances & Real-Time Scoring</span>
            <button type="button" class="action-btn action-btn-decollide-sm" onclick="toggleRuleTolerancesDrawer(false)">Close</button>
        </div>
        <div class="tolerances-summary-bar" id="tolerancesSummaryBar">
            <span class="badge-status ${status === 'ACCEPT' ? 'pass' : 'fail'}">${escapeHtml(status)} (${score})</span>
            <span>Active Violations: <strong>${activeCount}</strong></span>
            <span>Tolerated: <strong>${toleratedCount}</strong></span>
        </div>
        <div class="tolerances-grid">
            <label class="tolerance-field">
                <span>Accept Confidence Threshold: <strong id="lblAcceptThreshold">${ruleTolerancesState.target_confidence_threshold.toFixed(2)}</strong></span>
                <input type="range" id="rngAcceptThreshold" min="0.50" max="0.99" step="0.01"
                       value="${ruleTolerancesState.target_confidence_threshold}"
                       oninput="updateRuleTolerance('target_confidence_threshold', this.value)" />
            </label>
            <label class="tolerance-field">
                <span>Violation Penalty Multiplier: <strong id="lblPenaltyWeight">${ruleTolerancesState.penalty_weight.toFixed(1)}x</strong></span>
                <input type="range" id="rngPenaltyWeight" min="0.0" max="2.0" step="0.1"
                       value="${ruleTolerancesState.penalty_weight}"
                       oninput="updateRuleTolerance('penalty_weight', this.value)" />
            </label>
            <label class="tolerance-field">
                <span>Min Table Alignment Tolerance: <strong id="lblTableAlign">${ruleTolerancesState.min_table_alignment.toFixed(2)}</strong></span>
                <input type="range" id="rngTableAlign" min="0.40" max="1.00" step="0.05"
                       value="${ruleTolerancesState.min_table_alignment}"
                       oninput="updateRuleTolerance('min_table_alignment', this.value)" />
            </label>
            <label class="tolerance-checkbox">
                <input type="checkbox" id="chkSuppressWarnings" ${ruleTolerancesState.suppress_warnings ? 'checked' : ''}
                       onchange="updateRuleTolerance('suppress_warnings', this.checked)" />
                <span>Ignore non-critical WARNING severity rules</span>
            </label>
            <div class="tolerance-layers">
                <div class="tolerance-layers-title">Active Rule Layers</div>
                <div class="tolerance-layers-list">
                    <label><input type="checkbox" ${ruleTolerancesState.layers.symbols ? 'checked' : ''} onchange="toggleRuleToleranceLayer('symbols', this.checked)" /> L1 Symbols</label>
                    <label><input type="checkbox" ${ruleTolerancesState.layers.language ? 'checked' : ''} onchange="toggleRuleToleranceLayer('language', this.checked)" /> L2 Language</label>
                    <label><input type="checkbox" ${ruleTolerancesState.layers.tables ? 'checked' : ''} onchange="toggleRuleToleranceLayer('tables', this.checked)" /> L3 Tables</label>
                    <label><input type="checkbox" ${ruleTolerancesState.layers.reading_order ? 'checked' : ''} onchange="toggleRuleToleranceLayer('reading_order', this.checked)" /> L4 Layout</label>
                </div>
            </div>
        </div>
        <div class="tolerances-drawer-footer">
            <button type="button" class="action-btn action-btn-decollide-sm" onclick="resetRuleTolerances()">Reset Defaults</button>
        </div>
    `;
}
