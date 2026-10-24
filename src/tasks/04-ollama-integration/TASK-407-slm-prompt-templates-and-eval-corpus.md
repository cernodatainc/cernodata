# TASK-407: Prompt templates for small local models (1B-8B)

Small local models running in Ollama (`qwen2.5:1.5b`, `llama3.2:3b`, `phi3:mini`, `llava:7b`, `minicpm-v`) easily hallucinate or output broken JSON if prompts are vague. We need tested, concrete prompt templates for CernoData's four local-model tasks.

Create `src/schemas/examples/ollama_prompts/` with:

1. `slm_prompt_catalog.json` containing system prompts, few-shot examples, and JSON formatting instructions for:
   - `ocr_text_repair`: fixing character/spacing OCR mistakes without changing meaning or adding facts.
   - `vision_page_to_dom`: extracting headings, paragraphs, and Markdown tables from a page image.
   - `intent_to_assertion_suite`: turning plain-English validation requirements into `DocumentAssertionSuite` JSON.
   - `table_and_doc_summarizer`: describing numeric tables in plain sentences for RAG retrieval.
2. `README.md` noting which small models work best on CPU vs. 4-8GB GPU vs. 16GB GPU, recommended temperature settings (`0.0`), and examples of failure cases to avoid.
