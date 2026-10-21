# TASK-403: Ollama OCR text repair step

Depends on: TASK-401

When a node has minor OCR damage (flagged in `src/quality/violations.py`), a small local text model in Ollama (`qwen2.5:1.5b`, `llama3.2:1b`, `phi3`) can clean up broken character substitutions and spacing without running a heavy full-page vision model.

Create `src/pipeline/ollama_repair.py` and wire it into `run_ollama_ocr_repair_step` in `src/pipeline/pipeline_steps.py`:

- `repair_node_text(node: DOMNode, client: OllamaClient, model: str = "qwen2.5:1.5b") -> DOMNode`:
  - Prompts Ollama to fix only obvious OCR character/spacing errors without summarizing or adding facts.
  - Rejects the candidate repair if its character length differs from `raw_text` by more than 25% (to prevent hallucinations).
  - Saves the original string in `node.content["raw_text_before_ollama_repair"]` and updates `node.content["raw_text"]`.

Add unit tests in `src/tests/test_ollama_repair.py`.
