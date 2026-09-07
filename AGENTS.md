# AGENTS.md

Guidelines and behavioral rules for AI agents working on this codebase.

## 1. Strict Emoji Ban

- **Do NOT use emojis anywhere in this repository.**
- This ban applies strictly to:
  - Source code and inline comments
  - Commit messages and pull request descriptions
  - Markdown, documentation, and specifications
  - Terminal/CLI log output and exception messages
  - Generated web artifacts, HTML templates, and CSS/JS assets
- **Rationale**: Emojis cause character encoding failures in Windows console environments (`cp1252`), clutter git diffs, break deterministic parsing, and violate corporate engineering standards.

## 2. Style and Quality Standards

- Maintain strict Python 3.10+ type annotations (`typing`).
- Preserve documentation integrity; do not delete architectural decision trees without approval.
- Ensure all tests in `src/tests` pass before finalizing changes.
- Keep all explanations and user-facing communications succinct and direct.
