# TASK-208: Community OCR preset recipes

People working with non-English archives, scanned math papers, or dense Asian-language tables often use specialized OCR tools. We want a ready-made catalog of preset configurations so users can pick one from a dropdown in the Web UI (`TASK-207`) without figuring out CLI flags themselves.

Create `src/schemas/examples/custom_presets/` with:

1. `community_ocr_presets.json` containing entries for:
   - `tesseract_multilang`: Tesseract OCR with language parameter and `--psm` wiggle values (`3`, `6`, `11`).
   - `ocrmypdf_deskew`: `ocrmypdf --deskew --clean` for skewed office scans.
   - `marker_scientific_md`: `marker_single` for STEM PDFs with LaTeX equations.
   - `paddleocr_cjk_http`: HTTP endpoint template for Chinese/Japanese/Korean document tables.
   - `kraken_historical_handwriting`: Kraken OCR template for historical scripts and Fraktur fonts.
2. `README.md` explaining what kind of document each tool is best at and how to install the underlying program.
