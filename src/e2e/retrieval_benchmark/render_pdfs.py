"""
src/e2e/retrieval_benchmark/render_pdfs.py

Renders the TASK-109 Markdown fixtures (src/tests/fixtures/retrieval_benchmark) into two PDFs each:
`<doc>.pdf` (clean digital text) and `<doc>_scan.pdf` (grayscale, slightly rotated raster, no text layer).

Needs Edge or Chrome for HTML-to-PDF printing. Run from the repo root:
    python -m src.e2e.retrieval_benchmark.render_pdfs
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from markdown_it import MarkdownIt  # installed with docling (via rich)
from PIL import Image

OUT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = OUT_DIR.parents[1] / "tests" / "fixtures" / "retrieval_benchmark"
BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "google-chrome", "chromium",
)
CSS = (
    "body{font:10.5pt Georgia,serif;margin:2cm}table{border-collapse:collapse;margin:8px 0}"
    "td,th{border:1px solid #444;padding:3px 6px}blockquote{border:1px solid #444;margin:8px 0;padding:4px 10px}"
)
SCAN_DPI = 150
SCAN_ROTATION_DEGREES = 0.7


def _find_browser() -> str:
    for candidate in BROWSERS:
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    raise RuntimeError("Edge or Chrome is required to print PDFs")


def _to_html(markdown: str) -> str:
    """Converts fixture Markdown to HTML, rendering [^n] footnotes as superscripts and separate paragraphs."""
    markdown = re.sub(r"^\[\^(\d+)\]:", r"\n<sup>\1</sup>", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"\[\^(\d+)\]", r"<sup>\1</sup>", markdown)
    body = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def _print_pdf(browser: str, html: str, target: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={target}", page.as_uri()],
            check=True, capture_output=True, timeout=60,
        )


def _rasterize(source: Path, target: Path) -> None:
    pdf = pdfium.PdfDocument(source)
    pages: list[Image.Image] = [
        page.render(scale=SCAN_DPI / 72).to_pil().convert("L").rotate(SCAN_ROTATION_DEGREES, expand=True, fillcolor=255)
        for page in pdf
    ]
    pdf.close()
    pages[0].save(target, save_all=True, append_images=pages[1:], resolution=SCAN_DPI)


def main() -> None:
    browser = _find_browser()
    for source in sorted(SOURCE_DIR.glob("*.md")):
        clean = OUT_DIR / f"{source.stem}.pdf"
        _print_pdf(browser, _to_html(source.read_text(encoding="utf-8")), clean)
        _rasterize(clean, OUT_DIR / f"{source.stem}_scan.pdf")
        print(f"Rendered {clean.name} and {source.stem}_scan.pdf")


if __name__ == "__main__":
    main()
