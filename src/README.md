# Cernodata Engine Execution Flow & Architecture

Overview of the planner, plan execution, OCR engine presets, parameter wiggling, and web visualization workflow.

## 1. MVP Scope Boundaries

- **Out of Scope (Container Orchestration)**:
  Managing Docker daemons, building container images, Docker Compose, and spinning up or orchestrating container clusters is explicitly out of scope for this tool, the planner, and the MVP. The engine does not manage container lifecycles.
- **In Scope (Hooking & External URIs)**:
  Connecting webhooks, passing remote service URIs / API endpoints, and hooking into external services or infrastructure that someone else runs remains in scope.
- **Primary Execution Mode**:
  Self-contained local workstation execution on CPU and CUDA GPUs, air-gapped local processing, and local OCR backends.

## 2. Presets & OCR Engine Support

The engine organizes document extraction through isolated presets combining layout analysis, OCR drivers, and post-processing:

### Docling Presets & OCR Backends
Docling pipelines are configured with interchangeable OCR engines and granular parameter adjustments:
- `docling_fast`: Docling layout parser paired with RapidOCR for high-throughput, low-compute processing.
- `docling_deep`: Docling layout parser with high-precision OCR configuration and dictionary-guided diacritic / ligature restoration.
- Supported OCR engines inside Docling:
  - `rapidocr`: Torch / ONNX CPU backend (locally installed and validated).
  - `tesseract` / `tesseract_cli`: Tesseract OCR backend.
  - `easyocr`: PyTorch EasyOCR backend.
  - `auto`: Automatic layout-guided engine selection.

### Presets Outside of Docling
- `pypdfium_rapidocr`: A lightweight standalone preset running completely outside of Docling:
  - Extracts native vector text and character bounding boxes directly via `pypdfium2` at high speed with zero ML model loading overhead.
  - Automatically identifies scanned or image-dominant pages (low or zero digital text density) and routes them to targeted `RapidOCR`.
  - Emits standard `DocumentDOM` structures identical to Docling outputs, offering an efficient alternative for digital PDFs and low-spec environments.

### Parameter Wiggling (Path B Fallback)
When parsed document confidence falls below the target threshold, the engine evaluates whether to wiggle parameters on the current preset before switching engines:
- `ocr_scale`: Adjusts rendering resolution scale factor (e.g., 2.0 to 3.5+, equivalent to 150 to 300+ DPI).
- `force_full_page_ocr`: Forces comprehensive optical character recognition across full page surfaces when degraded or fragmented PDF text layers are detected.
- `table_structure`: Adjusts table detection and cell boundary heuristics.

## 3. Execution Flow

```mermaid
flowchart LR
    A[Questionnaire / Config] --> B[Preset Ranking]
    B --> C[User Override]
    C --> D[plan.json]
    D --> E[Python Tool / Orchestrator]
    E --> F[Interactive Web App]
```

1. **Plan Generation (`--create-plan`)**:
   The planner evaluates document taxonomy, local hardware capabilities (`low_spec_cpu`, `workstation_cuda`), target quality, and security requirements. It calculates preset scores across `pypdfium_rapidocr`, `docling_fast`, and `docling_deep`, proposes an execution order, and records the plan to `output/plan.json`.

2. **Plan Execution (`--plan output/plan.json`)**:
   The orchestrator runs the primary preset. If quality heuristics fall below `target_confidence_threshold`, it initiates the confidence-guided fallback loop:
   - **Path B (Parameter Wiggling)**: Retries with enhanced OCR scale and forced full-page OCR.
   - **Path A (Preset Switch)**: Pulls the next candidate from the fallback queue if wiggling bounds are exhausted.

3. **Visual Inspection (`--view` / `--serve`)**:
   The interactive web viewer (`output/interactive_viewer.html`) displays bounding box overlays, detected quality violations, and step-by-step execution provenance. Use `--serve` to run a local server with interactive OCR inspection endpoints.
