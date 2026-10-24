# TASK-602: Document topic profiler and skew detector

Depends on: TASK-601

When a user selects a folder of documents (`TASK-601`), we need a lightweight way to group documents into topics and detect whether one topic dominates the dataset (for example, 100 files on Topic A vs. 10,000 files on Topic B).

Create `src/pipeline/corpus/topic_profiler.py` using standard-library TF-IDF / heading keyword clustering (falling back to `subfolder_tag` or filename prefixes before full parsing):

- `TopicClusterSummary`: `topic_id`, `label`, `top_terms: list[str]`, `doc_count`, `char_volume`, and `share_of_corpus: float`.
- `TopicSkewReport`:
  - `clusters: list[TopicClusterSummary]`
  - `imbalance_ratio: float` (largest cluster size divided by smallest non-trivial cluster size)
  - `is_heavily_skewed: bool` (e.g. `imbalance_ratio >= 5.0`)
  - `summary_question: str` (plain-English question asking the user whether the ratio between the largest and smallest topic is intentional or just a side effect of what files were available).

Add unit tests in `src/tests/test_topic_profiler.py`.
