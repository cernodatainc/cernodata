# TASK-604: Corpus rebalancing and chunk weighting

Depends on: TASK-603, TASK-302

When the user tells CernoData that a dataset skew is accidental availability bias (`equalize_topic_weights` or `stratified_downsample` in `TASK-603`), the export pipeline needs to adjust how it packs and weights the documents so downstream RAG or fine-tuning isn't biased toward the dominant topic.

Create `src/pipeline/corpus/rebalancer.py` and connect it to `src/pipeline/exporters/rag_chunk_packer.py` (`TASK-302`):

- Stamp each `DocumentDOM` and exported RAG JSONL chunk with `"topic_id"` and `"sampling_weight"` ($w_t \propto 1 / N_t$) so downstream search or training loaders weight each topic equally.
- Pack minority-topic documents with smaller chunk steps/higher overlap so no detail is lost, while packing repetitive majority-topic documents with coarser `max_chars` chunks.
- When `stratified_downsample` is selected, cap majority-topic volume at `max_topic_ratio` by keeping the highest-confidence, most diverse documents first.

Add unit tests in `src/tests/test_corpus_rebalancer.py`.
