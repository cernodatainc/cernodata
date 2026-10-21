# TASK-104: Dataset retrieval test schema

Individual documents can pass basic OCR checks while still failing the user's actual goal: being able to answer a specific question from the parsed document set. We need a schema for defining baseline question-and-answer checks across a document or batch of documents.

Add the following dataclasses to `src/schemas/test_suite.py`:

- `RetrievalQuestionCase`:
  - `question_id: str`
  - `question: str` (e.g. `"What is the maximum operating temperature of the pump?"`)
  - `expected_answer_substrings: list[str]` (e.g. `["125 C", "257 F"]`)
  - `expected_source_docs: Optional[list[str]] = None`
  - `forbidden_substrings: list[str] = field(default_factory=list)`
  - `top_k: int = 3`
- `RetrievalTestSuite`:
  - `suite_name: str`
  - `chunk_size_chars: int = 1000`
  - `chunk_overlap_chars: int = 150`
  - `min_pass_rate: float = 1.0`
  - `questions: list[RetrievalQuestionCase]`

Include `to_dict()` / `from_dict()` serialization and validation (`top_k >= 1`, `0.0 <= min_pass_rate <= 1.0`, `chunk_overlap_chars < chunk_size_chars`), with unit tests in `src/tests/test_retrieval_schema.py`.
