# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-21

### Added

- Setup wizard, available in the browser and the terminal, that builds a ranked execution plan based on document type, hardware, speed and precision priorities, and security constraints.
- Parsing presets based on Docling, pypdfium2 and RapidOCR.
- Tiered quality checks: garbage text detection, language and dictionary scoring, and text skew analysis.
- Language configurations for English, Polish, German, Spanish and French.
- Automatic fallback that switches to the next preset or retries with adjusted parameters when confidence drops below the target threshold.
- Page-level reprocessing of problematic pages without reprocessing the entire document.
- Document DOM with bounding boxes for every extracted element.
- Interactive HTML viewer with visual overlays and markers for quality violations.
- Command-line interface for plan creation, plan-driven execution and live server preview.
