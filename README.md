# Cernodata

> [!NOTE]
> The available code in this repository is a Proof of Concept (PoC) and might be subject to major rewrites as it does not yet fit the architecture as described in [`Architecture_Specification.md`](Architecture_Specification.md).

Cernodata is an open-source ETL framework for layout-aware PDF extraction, automated quality iteration, structural layout debugging, and dataset generation for RAG and LLM fine-tuning.

## Parsing PDFs for RAG is a guessing game

You point a parser at a PDF, cross your fingers, and hope the chunks come out usable. They don't. And when they finally do, the next file has two columns instead of one, or a table that turns out to be a photograph of a table, or it's in a language you didn't plan for. The code you wrote yesterday breaks today. So you write another parser. And then another one. It never ends, because there is always another document.

It doesn't have to work this way.

Cernodata is a guided pipeline that turns messy, irregular PDFs into structured data you can verify. Verifiable is the important word there. Most pipelines hand you data you merely hope is right.

## One framework instead of one parser per source

You don't hand-code a parser for each source anymore. You answer a few questions, and Cernodata picks the engine for you.

When a document doesn't parse cleanly, it doesn't hand the problem back to you. It switches presets, or wiggles the parameters like DPI, contrast, and table detection, and tries again until the output is right. That week of fragile glue code you used to write for every new source now happens on its own.

## Never guessing what broke

Quality isn't a black box here. Every document climbs a ladder of checks that you can see, tune, and turn on as you need them. Garbage characters at the bottom, then table-grid alignment, and at the top, real retrieval scores from a vector search. Whether the chunks can actually be found is, after all, the only question that matters.

When a document fails, you know which check failed, on which page, and why. And visual overlays draw the parse right on top of the page, so you catch a mis-merged column the way you catch a typo. You just look at it, instead of digging through a stack trace three days later.

## It runs on your machine without taking it hostage

Heavy OCR shouldn't freeze your laptop, or eat memory until something crashes while your local model is trying to run. So Cernodata caps concurrency, enforces hard memory ceilings, and does the heavy ML work in subprocesses that clean up after themselves. Ingestion ought to be like a print job: something running in the background that you can ignore. Not a fire drill.

## Built for the ugly ones

Demos are made of clean documents. Real work isn't.

If a 100-page file fails on page 42, Cernodata slices out page 42 and retries it with a heavier engine, instead of running all 100 again. ML workers that leak memory restart themselves. The hard parts are engineered for the large, messy, documents that quietly break everyone else's pipeline.
You'll still have ugly documents. You just won't have to write a parser for each one.

## This is the part where you decide to care

The README is the promise. The library is coming.

Want it the day it lands? And a say in what it becomes?

Leave your email.

→ [Join the waitlist](https://tally.so/r/mJZb4R) · takes 10 seconds, no spam, ever

## Architecture & Specification

The primary application architecture specification for this repository is located in:
- [`Architecture_Specification.md`](Architecture_Specification.md)

It details the 9 core architecture subsystems:
1. Preset Selection Decision Tree
2. Curated & User-Defined Presets
3. Automated Confidence-Guided Iteration Loop & Quality Checks
4. Page-Level PDF Subdivision
5. Structural Extraction, Bounding Box Visual Overlays & Template Hints
6. Downstream Evaluation Decision Tree & SLM Prompt Generation
7. Downstream Packing & Target Use-Case Decision Tree
8. Resource Protection & Work Dispatching Subsystem
9. Interactive Visual Web App & Audit-Friendly Standalone Script Exporter
