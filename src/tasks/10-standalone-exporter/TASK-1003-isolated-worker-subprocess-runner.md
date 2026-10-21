# TASK-1003: Subprocess isolation for heavy parser presets

Heavy layout and OCR models (Docling deep table recognition, C++ PDF/OCR bindings, local vision models) can leak memory or crash on malformed PDFs (`Architecture_Specification.md` Section 9.2). Right now parsers run directly inside the main HTTP server process, so an OOM or segfault brings down the whole Web Hub.

Create `src/pipeline/isolated_runner.py` and wire it into `_execute_isolated_attempt` in `src/pipeline/fallback_handler.py`:

- Spawn `sys.executable -m src.pipeline.isolated_runner` via `subprocess.run(..., shell=False, timeout=timeout_sec)` to run the parser in a child process and write the resulting `DocumentDOM` to a temporary JSON file.
- If the child process times out (`subprocess.TimeoutExpired`) or exits non-zero, catch the failure cleanly and return a structured error in the attempt log so the Web Hub stays up and can move to the next fallback or flag the document for review.

Add unit tests in `src/tests/test_isolated_runner.py`.
