"""
src/visualization/html_viewer.py

Interactive HTML Visual Flow App & Step-by-Step Preset Explorer.
"""

import os
import json
import base64
from typing import Dict, Any, List

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False

from src.dom import DocumentDOM


def _page_to_base64(pdf_path: str, page_index: int = 0, scale: float = 150/72.0) -> str:
    """Renders PDF page to PNG and converts to base64 data URI."""
    if HAS_PYPDFIUM and os.path.exists(pdf_path):
        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            if 0 <= page_index < len(pdf):
                pil_img = pdf[page_index].render(scale=scale).to_pil().convert("RGB")
                import io
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
        except Exception as e:
            print(f"[WARN] Base64 page render error: {e}")

    svg_canvas = '<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792" style="background:#111827;"></svg>'
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_canvas.encode('utf-8')).decode('utf-8')}"


def generate_interactive_html(
    pdf_path: str,
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    output_path: str = os.path.join("output", "interactive_viewer.html")
) -> str:
    """Generates a standalone, interactive HTML visual flow explorer file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img_data_uri = _page_to_base64(pdf_path, page_index=0)

    dom_json = json.dumps(dom.to_dict())
    violations_json = json.dumps(violations)
    decision_json = json.dumps(decision)
    is_acc = decision.get('is_accepted', True)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>cernodata | Interactive Visual Flow & Preset Simulator</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-main: #0B0F17; --bg-card: #111827; --bg-card-hover: #1F2937;
            --border-color: #374151; --accent-green: #00E676; --accent-red: #FF1744;
            --accent-blue: #1976D2; --accent-purple: #7B1FA2; --text-main: #F9FAFB; --text-muted: #9CA3AF;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background-color: var(--bg-main); color: var(--text-main); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
        header {{ background: linear-gradient(180deg, rgba(17,24,39,0.95) 0%, rgba(17,24,39,0.8) 100%); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; z-index: 100; flex-shrink: 0; }}
        .brand {{ display: flex; align-items: center; gap: 12px; }}
        .brand-logo {{ background: linear-gradient(135deg, #1976D2 0%, #7B1FA2 100%); width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 18px; box-shadow: 0 4px 12px rgba(25, 118, 210, 0.4); }}
        .brand-title {{ font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }}
        .timeline {{ display: flex; align-items: center; gap: 8px; background: rgba(31, 41, 55, 0.6); padding: 4px; border-radius: 20px; border: 1px solid var(--border-color); }}
        .step-btn {{ background: transparent; border: none; color: var(--text-muted); padding: 6px 16px; border-radius: 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 6px; }}
        .step-btn.active {{ background: #1976D2; color: #FFF; box-shadow: 0 2px 8px rgba(25, 118, 210, 0.4); }}
        .step-btn.fallback {{ opacity: 0.6; }}
        .badge-status {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }}
        .badge-status.pass {{ background: var(--accent-green); color: #000; }}
        .badge-status.fail {{ background: var(--accent-red); color: #FFF; }}
        .toolbar {{ background: var(--bg-card); border-bottom: 1px solid var(--border-color); padding: 8px 24px; display: flex; align-items: center; gap: 20px; font-size: 13px; flex-shrink: 0; }}
        .toggle-group label {{ cursor: pointer; user-select: none; display: flex; align-items: center; gap: 6px; color: var(--text-main); font-weight: 500; }}
        .toggle-group input[type="checkbox"] {{ accent-color: #1976D2; width: 16px; height: 16px; cursor: pointer; }}
        select.type-filter {{ background: #1F2937; color: var(--text-main); border: 1px solid var(--border-color); padding: 4px 10px; border-radius: 6px; font-size: 13px; cursor: pointer; }}
        .workspace {{ flex: 1; display: flex; overflow: hidden; min-height: 0; }}
        .visual-pane {{ flex: 1.2; background: #080C14; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; position: relative; overflow: auto; min-height: 0; }}
        .canvas-container {{ position: relative; box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6); border-radius: 8px; overflow: hidden; background: #1F2937; max-width: 100%; display: inline-block; }}
        .canvas-container img {{ display: block; max-width: 100%; max-height: calc(100vh - 150px); width: auto; height: auto; object-fit: contain; }}
        .svg-overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}
        .svg-overlay * {{ pointer-events: all; }}
        .node-bbox {{ fill: rgba(25, 118, 210, 0.08); stroke: #1976D2; stroke-width: 2px; cursor: pointer; transition: all 0.15s ease; }}
        .node-bbox:hover, .node-bbox.highlighted {{ fill: rgba(25, 118, 210, 0.25); stroke-width: 4px; filter: drop-shadow(0 0 6px rgba(25, 118, 210, 0.8)); }}
        .node-bbox.violation {{ stroke: #FF1744 !important; fill: rgba(255, 23, 68, 0.15) !important; stroke-width: 3px; }}
        .node-bbox.violation:hover, .node-bbox.violation.highlighted {{ fill: rgba(255, 23, 68, 0.35) !important; stroke-width: 4px; filter: drop-shadow(0 0 8px rgba(255, 23, 68, 0.9)); }}
        .viol-callout {{ fill: #D50000; stroke: #FFD600; stroke-width: 1px; cursor: pointer; }}
        .viol-text {{ fill: #FFFFFF; font-size: 11px; font-weight: 700; font-family: 'Inter', sans-serif; pointer-events: none; }}
        .score-badge-box {{ position: absolute; bottom: 24px; left: 24px; background: rgba(17, 24, 39, 0.92); backdrop-filter: blur(8px); border: 2px solid var(--accent-green); padding: 10px 16px; border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 50; }}
        .score-badge-box.fail {{ border-color: var(--accent-red); }}
        .score-title {{ font-size: 13px; font-weight: 700; color: #FFF; }}
        .score-sub {{ font-size: 11px; font-weight: 600; margin-top: 2px; }}
        .inspector-pane {{ flex: 0.8; background: var(--bg-card); border-left: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden; }}
        .tab-bar {{ display: flex; border-bottom: 1px solid var(--border-color); background: #192231; flex-shrink: 0; }}
        .tab-btn {{ flex: 1; padding: 12px; text-align: center; background: transparent; border: none; color: var(--text-muted); font-size: 13px; font-weight: 600; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }}
        .tab-btn.active {{ color: var(--text-main); border-bottom-color: #1976D2; background: var(--bg-card); }}
        .tab-content {{ flex: 1; padding: 16px; overflow-y: auto; display: none; }}
        .tab-content.active {{ display: block; }}
        .node-card {{ background: #1A2332; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s ease; }}
        .node-card:hover, .node-card.selected {{ border-color: #1976D2; background: #232F45; box-shadow: 0 4px 12px rgba(25, 118, 210, 0.2); }}
        .node-card.has-violation {{ border-left: 4px solid var(--accent-red); }}
        .node-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }}
        .node-id {{ font-size: 12px; font-weight: 700; color: #60A5FA; }}
        .node-type {{ padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; background: #374151; }}
        .node-text {{ font-size: 12px; color: #D1D5DB; line-height: 1.4; white-space: pre-wrap; word-break: break-word; }}
        .viol-card {{ background: #291217; border: 1px solid #7F1D1D; border-radius: 8px; padding: 12px; margin-bottom: 10px; cursor: pointer; }}
        .viol-card:hover {{ border-color: var(--accent-red); background: #3B171E; }}
        .viol-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
        .viol-title {{ font-size: 13px; font-weight: 700; color: #FCA5A5; }}
        .viol-desc {{ font-size: 12px; color: #FECACA; margin-top: 4px; }}
        .log-box {{ background: #0F172A; border: 1px solid var(--border-color); padding: 14px; border-radius: 8px; font-family: monospace; font-size: 12px; line-height: 1.5; color: #38BDF8; overflow: auto; }}
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-logo">C</div>
            <div>
                <div class="brand-title">cernodata Visual Flow & Preset Simulator</div>
                <div style="font-size: 11px; color: var(--text-muted);">Document: {dom.source_filename} | ID: {dom.document_id}</div>
            </div>
        </div>

        <div class="timeline">
            <button class="step-btn active" onclick="switchPreset(0)">
                <span>Step 1: {decision.get('chosen_preset', 'docling_fast')}</span>
                <span class="badge-status {'pass' if is_acc else 'fail'}">{'ACCEPT' if is_acc else 'REJECT'}</span>
            </button>
            <button class="step-btn fallback" onclick="switchPreset(1)">
                <span>Step 2: docling_deep</span>
                <span class="badge-status" style="background:#4B5563; color:#FFF;">Candidate</span>
            </button>
        </div>
    </header>

    <div class="toolbar">
        <div class="toggle-group"><label><input type="checkbox" id="toggleBbox" checked onchange="updateLayers()"> Bounding Boxes</label></div>
        <div class="toggle-group"><label><input type="checkbox" id="toggleViolations" checked onchange="updateLayers()"> Quality Violations</label></div>
        <div class="toggle-group"><label><input type="checkbox" id="toggleBadges" checked onchange="updateLayers()"> Node Badges</label></div>
        <div class="toggle-group"><label><input type="checkbox" id="toggleScore" checked onchange="updateLayers()"> Score Badge</label></div>
        <div style="display: flex; align-items: center; gap: 6px; margin-left: auto;">
            <span style="color: var(--text-muted);">Filter Type:</span>
            <select class="type-filter" id="typeFilter" onchange="updateLayers()">
                <option value="ALL">All Types</option>
                <option value="heading">Headings</option>
                <option value="paragraph">Paragraphs</option>
                <option value="table_grid">Tables</option>
                <option value="figure">Figures</option>
            </select>
        </div>
    </div>

    <div class="workspace">
        <div class="visual-pane">
            <div class="canvas-container" id="canvasContainer">
                <img src="{img_data_uri}" id="pageImg" alt="Page Canvas" />
                <svg class="svg-overlay" id="svgOverlay" viewBox="0 0 595.28 841.89" preserveAspectRatio="none"></svg>
            </div>

            <div class="score-badge-box {'fail' if not is_acc else ''}" id="scoreBadge">
                <div class="score-title">Page 1 Confidence Score: {decision.get('overall_confidence', 1.0):.3f}</div>
                <div class="score-sub" style="color: {'var(--accent-green)' if is_acc else 'var(--accent-red)'}">
                    Status: {decision.get('status', 'ACCEPT')} | Violations Flagged: {len(violations)}
                </div>
            </div>
        </div>

        <div class="inspector-pane">
            <div class="tab-bar">
                <button class="tab-btn active" onclick="showTab(event, 'domTab')">DOM Tree ({len(dom.nodes)})</button>
                <button class="tab-btn" onclick="showTab(event, 'violTab')">Violations ({len(violations)})</button>
                <button class="tab-btn" onclick="showTab(event, 'logTab')">Decision Log</button>
            </div>

            <div class="tab-content active" id="domTab"><div id="domListContainer"></div></div>
            <div class="tab-content" id="violTab"><div id="violListContainer"></div></div>
            <div class="tab-content" id="logTab"><div class="log-box"><pre id="logContent"></pre></div></div>
        </div>
    </div>

    <script>
        const domData = {dom_json};
        const violationsData = {violations_json};
        const decisionData = {decision_json};

        function createSvgElem(tag, attrs) {{
            const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
            for (let k in attrs) el.setAttribute(k, attrs[k]);
            return el;
        }}

        function renderDOMTree() {{
            const container = document.getElementById('domListContainer');
            container.innerHTML = '';
            domData.nodes.forEach(node => {{
                const hasViol = violationsData.some(v => v.node_id === node.node_id);
                const card = document.createElement('div');
                card.className = `node-card ${{hasViol ? 'has-violation' : ''}}`;
                card.id = `card-${{node.node_id}}`;
                card.onclick = () => selectNode(node.node_id);
                card.innerHTML = `
                    <div class="node-header">
                        <span class="node-id">${{node.node_id}}</span>
                        <span class="node-type">${{node.type}}</span>
                    </div>
                    <div class="node-text">${{escapeHtml(node.content.raw_text || '')}}</div>
                `;
                container.appendChild(card);
            }});
        }}

        function renderViolationsList() {{
            const container = document.getElementById('violListContainer');
            if (violationsData.length === 0) {{
                container.innerHTML = '<div style="color: var(--text-muted); text-align: center; margin-top: 20px;">No quality violations detected.</div>';
                return;
            }}
            container.innerHTML = '';
            violationsData.forEach(v => {{
                const card = document.createElement('div');
                card.className = 'viol-card';
                card.onclick = () => selectNode(v.node_id);
                card.innerHTML = `
                    <div class="viol-header">
                        <span class="viol-title">[!] ${{v.rule_type}}</span>
                        <span style="font-size: 10px; font-weight:700; color: #F87171;">${{v.severity}}</span>
                    </div>
                    <div style="font-size: 12px; font-family: monospace;">Snippet: '${{v.detected_snippet}}' -> '${{v.suggested_correction || ''}}'</div>
                    <div class="viol-desc">${{v.description}}</div>
                `;
                container.appendChild(card);
            }});
        }}

        function renderDecisionLog() {{
            document.getElementById('logContent').textContent = JSON.stringify(decisionData, null, 2);
        }}

        function renderSVGOverlays() {{
            const svg = document.getElementById('svgOverlay');
            svg.innerHTML = '';
            const showBbox = document.getElementById('toggleBbox').checked;
            const showViol = document.getElementById('toggleViolations').checked;
            const filterType = document.getElementById('typeFilter').value;

            domData.nodes.forEach(node => {{
                if (filterType !== 'ALL' && node.type !== filterType) return;
                const bbox = node.bounding_box;
                const hasViol = violationsData.some(v => v.node_id === node.node_id);
                const violItem = violationsData.find(v => v.node_id === node.node_id);

                if (showBbox) {{
                    const attrs = {{
                        x: bbox.x0, y: bbox.y0,
                        width: Math.max(15, bbox.x1 - bbox.x0), height: Math.max(10, bbox.y1 - bbox.y0),
                        class: `node-bbox ${{hasViol ? 'violation' : ''}}`, id: `svg-${{node.node_id}}`
                    }};
                    if (bbox.angle && bbox.angle !== 0) {{
                        const cx = (bbox.x0 + bbox.x1) / 2, cy = (bbox.y0 + bbox.y1) / 2;
                        attrs.transform = `rotate(${{bbox.angle}} ${{cx}} ${{cy}})`;
                    }}
                    const rect = createSvgElem('rect', attrs);
                    rect.onclick = () => selectNode(node.node_id);
                    svg.appendChild(rect);
                }}

                if (showViol && hasViol && violItem) {{
                    const g = createSvgElem('g', {{}});
                    const labelText = `[!] VIOLATION: '${{violItem.detected_snippet}}' -> '${{violItem.suggested_correction || ''}}'`;
                    const badgeBg = createSvgElem('rect', {{
                        x: bbox.x0, y: Math.max(0, bbox.y0 - 18),
                        width: Math.min(300, labelText.length * 7), height: 18, class: 'viol-callout'
                    }});
                    const badgeTxt = createSvgElem('text', {{
                        x: bbox.x0 + 4, y: Math.max(12, bbox.y0 - 4), class: 'viol-text'
                    }});
                    badgeTxt.textContent = labelText;
                    g.appendChild(badgeBg);
                    g.appendChild(badgeTxt);
                    svg.appendChild(g);
                }}
            }});
        }}

        function selectNode(nodeId) {{
            document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
            document.querySelectorAll('.node-bbox').forEach(b => b.classList.remove('highlighted'));
            const card = document.getElementById(`card-${{nodeId}}`);
            if (card) {{
                card.classList.add('selected');
                card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
            const svgElem = document.getElementById(`svg-${{nodeId}}`);
            if (svgElem) svgElem.classList.add('highlighted');
        }}

        function updateLayers() {{
            renderSVGOverlays();
            const showScore = document.getElementById('toggleScore').checked;
            document.getElementById('scoreBadge').style.display = showScore ? 'block' : 'none';
        }}

        function showTab(evt, tabId) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            evt.currentTarget.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }}

        function switchPreset(stepIndex) {{
            document.querySelectorAll('.step-btn').forEach((b, i) => {{
                b.classList.toggle('active', i === stepIndex);
            }});
        }}

        function escapeHtml(str) {{
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }}

        renderDOMTree();
        renderViolationsList();
        renderDecisionLog();
        renderSVGOverlays();
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
