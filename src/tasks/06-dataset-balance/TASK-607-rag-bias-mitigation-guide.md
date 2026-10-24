# TASK-607: Decision guide on dataset skew vs. availability bias in RAG and fine-tuning

Users putting together a knowledge base rarely have equal numbers of documents per topic. A folder might have 10,000 routine tickets or logs on Topic B and only 100 core engineering specs on Topic A. If all 10,100 documents are embedded into a vector database or fine-tuning set without adjustment, top-$k$ retrieval gets crowded out by Topic B and fine-tuned models overfit to Topic B's style.

Create `docs/corpus_balance_decision_tree.md` (under 190 lines, matching the format of `data_storage_decision_tree.md`) covering:

1. How to tell whether a skewed document count reflects intentional priority, historical logging/availability bias, or template duplication.
2. How severe topic skew affects vector cosine search, BM25 lexical search, and SFT training differently.
3. When to use each mitigation option in CernoData: inverse-frequency `sampling_weight` metadata, asymmetric chunk sizes, shingle deduplication, or synthetic query/summary augmentation for the smaller topic.
