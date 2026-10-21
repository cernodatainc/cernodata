# TASK-603: Dataset balance policy schema and planner wizard hook

Depends on: TASK-602

File counts alone cannot tell us why Topic B has 100x more documents than Topic A. Maybe Topic B is the main subject and should dominate retrieval, or maybe Topic B just happened to have 10,000 auto-generated logs while Topic A has 100 core manuals that shouldn't get drowned out.

Create `src/schemas/corpus_balance.py` and wire `_evaluate_corpus_topic_balance` in `src/pipeline/server/routes/planning.py`:

- `CorpusBalanceIntent` (`Enum`):
  - `"preserve_raw_distribution"` (keep as-is; the larger topic should be weighted more heavily)
  - `"equalize_topic_weights"` (balance topics equally so high-volume topics don't drown out smaller ones)
  - `"stratified_downsample"` (deduplicate and cap dominant topics for a balanced training set)
- `CorpusBalancePolicy`: `intent`, `max_topic_ratio: float = 3.0`, `deduplicate_dominant_topics: bool = True`, and `topic_weight_overrides: dict[str, float]`.
- Store the chosen policy on `DocumentPlan` (`src/pipeline/planner/models.py`).

Add unit tests in `src/tests/test_corpus_balance_schema.py`.
