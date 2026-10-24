# TASK-605: Near-duplicate document deduplicator

Depends on: TASK-601

When one topic has 10,000 files and another has 100, the 10,000 files are often near-duplicates (daily exports, minor form revisions, or repeated boilerplate templates). Detecting near-duplicates lets us collapse redundant files before indexing.

Create `src/pipeline/corpus/deduplicator.py` using standard-library `hashlib.blake2b`:

- `compute_word_shingles(text: str, k: int = 5) -> set[int]`: 64-bit hashes of 5-word shingles.
- `jaccard_similarity(shingles_a: set[int], shingles_b: set[int]) -> float`.
- `find_near_duplicate_clusters(doms: dict[str, DocumentDOM], threshold: float = 0.85) -> list[list[str]]`: groups documents with Jaccard similarity $\ge \text{threshold}$ and picks the highest-confidence document in each cluster as the canonical copy.

Add unit tests in `src/tests/test_deduplicator.py`.
