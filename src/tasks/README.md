# MVP Tasks (`src/tasks/`)

Granular tasks for bringing `cernodata` to an MVP. All user-facing workflows are built into the browser UI (`src/visualization/landing.html`, `src/visualization/data_shape_config.html`, and `src/visualization/viewer/`) so non-developers do not need CLI flags or terminal pipes.

Each task corresponds to an isolated no-op hook (`TODO(TASK-XXX)`) in `src/` so contributors can work in parallel without merge conflicts. Tasks with no `Depends on:` line at the top of their file can be started immediately.

## Tasks that do not require Python/JS coding

- `01-output-testing/TASK-108`: Starter domain assertion templates (academic, invoice, legal, datasheet, regulatory).
- `01-output-testing/TASK-109`: Sample documents and Q&A pairs for testing table, heading, and footnote retrieval failures.
- `02-custom-presets/TASK-208`: Community OCR preset recipes (Tesseract, OCRmyPDF, Marker, PaddleOCR, Kraken).
- `03-downstream-piping/TASK-307`: Step-by-step guides for connecting exported files to AnythingLLM, OpenWebUI, Obsidian, NotebookLM, and fine-tuning UIs.
- `04-ollama-integration/TASK-407`: Prompt templates and model notes for small 1B-8B local Ollama models.
- `05-postprocessing/TASK-507`: Regex and pattern catalog for company letterheads, watermarks, Bates stamps, and footers.
- `06-dataset-balance/TASK-607`: Decision guide on handling skewed document counts (intentional weighting vs. availability bias) in RAG and fine-tuning.
- `07-viewer-validation/TASK-708`: Colorblind-safe overlay palette and keyboard review shortcut specification for `/viewer`.
- `09-template-hints/TASK-905`: Starter spatial layout templates (commercial invoice, two-column academic paper, patent front page, blueprint title block).

## Task Index by Goal

### 01. Output Testing & Retrieval Evaluation (`01-output-testing/`)
- `TASK-101`: Single-document assertion schema (`DocumentAssertionSuite`)
- `TASK-102`: Structural and header spot-checker (depends on `101`)
- `TASK-103`: Real Markdown table grid validator (depends on `101`)
- `TASK-104`: Dataset retrieval test schema (`RetrievalTestSuite`)
- `TASK-105`: In-memory BM25 retrieval sandbox
- `TASK-106`: Retrieval test evaluator (depends on `104`, `105`)
- `TASK-107`: Web UI output test builder and Q&A sandbox (depends on `102`, `103`, `106`)
- `TASK-108`: Domain test suite templates
- `TASK-109`: Ground-truth Q&A benchmark pairs for retrieval testing

### 02. Custom Parsing & OCR Presets (`02-custom-presets/`)
- `TASK-201`: Custom preset manifest schema (`CustomPresetConfig`)
- `TASK-202`: Subprocess OCR engine adapter
- `TASK-203`: HTTP OCR engine adapter
- `TASK-204`: Fix catch-all Docling adapter and load custom presets into registry (depends on `201`, `202`, `203`)
- `TASK-205`: Include custom presets in `PresetPlanner` scoring (depends on `201`)
- `TASK-206`: Custom preset parameter wiggling in `FallbackLoopHandler` (depends on `204`, `205`)
- `TASK-207`: Web UI custom OCR preset builder and recipe loader (depends on `204`, `205`)
- `TASK-208`: Community OCR preset recipes

### 03. Connecting Outputs to Pre-Existing Setups (`03-downstream-piping/`)
- `TASK-301`: Visual downstream connection wizard in the Web Hub
- `TASK-302`: Hierarchical RAG chunk packer (`JSONL`)
- `TASK-303`: Clean Markdown and SFT JSONL exporters
- `TASK-304`: Watched folder and webhook output delivery (depends on `301`, `302`, `303`)
- `TASK-305`: Downstream setup recommendation advisor (depends on `302`, `303`)
- `TASK-306`: Web Hub downstream recommendation and export card (depends on `304`, `305`)
- `TASK-307`: Visual guides for connecting pre-existing AI and knowledge tools

### 04. Ollama Integration (`04-ollama-integration/`)
- `TASK-401`: Standard-library Ollama HTTP client
- `TASK-402`: `vision_llm_direct` preset adapter via Ollama VLM (depends on `401`)
- `TASK-403`: Ollama OCR text repair step (depends on `401`)
- `TASK-404`: Local SLM test case and retrieval question generator (depends on `401`, `101`, `104`)
- `TASK-405`: Ollama document summary and table metadata enrichment (depends on `401`)
- `TASK-406`: Viewer and Hub Ollama UI controls and endpoints (depends on `402`, `403`, `404`, `405`)
- `TASK-407`: Prompt templates for small local models (1B-8B)

### 05. DOM Postprocessing (`05-postprocessing/`)
- `TASK-501`: DOM postprocessor interface and chain runner
- `TASK-502`: Company letterhead and repeating header/footer stripper (depends on `501`)
- `TASK-503`: Hyphenation and line-break defragmenter (depends on `501`)
- `TASK-504`: Watermark and boilerplate stamp filter (depends on `501`)
- `TASK-505`: Regex replacement and PII redaction postprocessor (depends on `501`)
- `TASK-506`: Web UI postprocessing checklist and viewer preview (depends on `501`-`505`)
- `TASK-507`: Corporate letterhead, watermark, and boilerplate pattern catalog

### 06. Dataset Topic Balance (`06-dataset-balance/`)
- `TASK-601`: Multi-document corpus scanner and manifest
- `TASK-602`: Document topic profiler and skew detector (depends on `601`)
- `TASK-603`: Dataset balance policy schema and planner wizard hook (depends on `602`)
- `TASK-604`: Corpus rebalancing and chunk weighting (depends on `603`, `302`)
- `TASK-605`: Near-duplicate document deduplicator (depends on `601`)
- `TASK-606`: Web UI topic distribution chart and balance controls (depends on `602`, `603`, `604`)
- `TASK-607`: Decision guide on dataset skew vs. availability bias in RAG and fine-tuning

### 07. Viewer Manual Correction & Validation (`07-viewer-validation/`)
- `TASK-701`: Single-node type switcher in the viewer inspector
- `TASK-702`: Split merged nodes in the viewer
- `TASK-703`: Viewer undo and redo stack (`Ctrl+Z` / `Ctrl+Y`)
- `TASK-704`: DOM reading-order badges and reordering controls
- `TASK-705`: Interactive table grid editor in the viewer (depends on `701`)
- `TASK-706`: Keyboard violation jumping, node approval, and text search in the viewer
- `TASK-707`: Direct formatted export from the viewer toolbar (depends on `302`, `303`)
- `TASK-708`: Viewer accessibility, color palette, and keyboard workflow spec
- `TASK-709`: Live formatted output preview in the viewer (depends on `704`)
- `TASK-710`: In-viewer violation sensitivity and acceptance threshold tuner

### 08. Page-Level Subdivision & Reassembly (`08-page-subdivision/`)
- `TASK-801`: Single-page PDF slicer (`slice_pdf_pages`)
- `TASK-802`: DOM page reassembler (`merge_sliced_dom`)
- `TASK-803`: Wire page slicing into `FallbackLoopHandler` (depends on `801`, `802`)
- `TASK-804`: Re-parse single page with chosen preset in the viewer (depends on `803`)

### 09. Document Layout Template Hints (`09-template-hints/`)
- `TASK-901`: Document template hint schema
- `TASK-902`: Template misapplication detector (depends on `901`)
- `TASK-903`: Apply template zones and add Web Hub template selector (depends on `901`, `902`)
- `TASK-904`: Save current page layout as a template in the viewer (depends on `901`)
- `TASK-905`: Starter document layout templates

### 10. Standalone Exporter, Layout Preview & Subprocess Isolation (`10-standalone-exporter/`)
- `TASK-1001`: Export reproducible pipeline script from the Web UI
- `TASK-1002`: Instant layout preview (boxes only, skip OCR) in Web Hub and Viewer
- `TASK-1003`: Subprocess isolation for heavy parser presets
- `TASK-1004`: Calibrate `PresetPlanner` using observed run timings (depends on `1003`)
