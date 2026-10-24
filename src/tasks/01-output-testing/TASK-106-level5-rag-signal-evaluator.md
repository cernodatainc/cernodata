# TASK-106: Retrieval test evaluator

Depends on: TASK-104, TASK-105

Connect `RetrievalTestSuite` (`TASK-104`) and `LexicalRetrievalSandbox` (`TASK-105`) so CernoData can check whether a parsed document or corpus answers the user's test questions.

Create `src/quality/retrieval_evaluator.py` and hook it into `_check_dataset_retrieval_violations` in `src/quality/violations.py`:

- Index the parsed `DocumentDOM` objects into `LexicalRetrievalSandbox`.
- For each `RetrievalQuestionCase`, query the top-`k` chunks and verify that all `expected_answer_substrings` are present, `expected_source_docs` (if set) appear in the top-`k` results, and `forbidden_substrings` are absent.
- When a question fails, return a violation record (`rule_type="rag_retrieval_recall_miss"`) naming the failed question and the missing expected text. If the missing answer substring exists inside a low-confidence node on a specific page, attach that node's `global_page_index` and `node_id` so the fallback loop knows which page needs re-parsing.

Add unit tests in `src/tests/test_retrieval_evaluator.py`.
