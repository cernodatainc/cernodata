# TASK-307: Visual guides for connecting pre-existing AI and knowledge tools

When CernoData recommends an export format in the Web Hub (`TASK-306`), it should link to a clear, step-by-step guide showing non-developers how to point their existing desktop or web tools at CernoData's exported files.

Create `docs/downstream_connection_guides.md` (under 200 lines) covering:

1. Desktop RAG & local chat apps (AnythingLLM, LM Studio, Jan): pointing their document folder at CernoData's watched folder export.
2. Web workspaces (OpenWebUI, Dify): uploading or syncing CernoData's `RAG Chunks (.jsonl)` or `Clean Markdown` into a Knowledge Collection.
3. Note-taking & knowledge bases (Obsidian, Logseq): connecting CernoData's watched folder export to an Obsidian vault while keeping headings and tables intact.
4. Cloud research assistants (NotebookLM, Claude Projects, ChatGPT): which export option to choose so multi-column tables and footnotes are preserved.
5. Fine-tuning web UIs (LLaMA-Factory WebUI, Unsloth notebooks): loading CernoData's filtered `SFT Dataset (.jsonl)`.
