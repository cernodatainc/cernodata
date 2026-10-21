# TASK-404: Local SLM test case and retrieval question generator

Depends on: TASK-401, TASK-101, TASK-104

Instead of making users write every test question by hand, CernoData can use a local Ollama model to suggest baseline structural assertions and retrieval questions from a sample parsed document (`testing_decision_tree.md` Section 5.1).

Create `src/quality/slm_test_generator.py`:

- `generate_assertions_from_intent(user_intent: str, sample_dom: Optional[DocumentDOM], client: OllamaClient, model: str = "qwen2.5:3b") -> DocumentAssertionSuite`: turns a plain-English requirement (e.g. `"Every invoice needs a tax table and vendor header"`) into a validated `DocumentAssertionSuite` (`TASK-101`).
- `generate_retrieval_questions_from_dom(dom: DocumentDOM, client: OllamaClient, model: str = "qwen2.5:3b", num_questions: int = 5) -> RetrievalTestSuite`: picks high-confidence sections and tables from `dom` and generates factual question + expected-substring pairs (`TASK-104`).

Add unit tests in `src/tests/test_slm_test_generator.py`.
