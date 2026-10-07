"""
src/pipeline/planner/wizard.py

Interactive CLI wizard flow for inquiring document characteristics and system constraints.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.pipeline.planner.models import DocumentPlan, PlannerCriteria
from src.pipeline.planner.options import WIZARD_DIMENSIONS


def resolve_choice(choice: str, options: List[Tuple[str, str]], default: str) -> str:
    """Resolves numeric or string-based option selection to internal choice key."""
    choice = choice.strip()
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(options):
            return options[idx - 1][0]
    choice_lower = choice.lower()
    for key, _ in options:
        if key.lower() == choice_lower:
            return key
    return default


def run_interactive_wizard(
    planner: Any,
    input_func: Callable[[str], str] = input,
    print_func: Callable[..., None] = print,
    default_doc: Optional[str] = None,
) -> DocumentPlan:
    """Guides user through interactive questionnaire, presents preset recommendations, and prompts for override."""
    print_func("=" * 68)
    print_func("cernodata Preset Planner & Pipeline Configuration Wizard")
    print_func("=" * 68)

    total_steps = len(WIZARD_DIMENSIONS) + 2

    # 1. Document Path
    if default_doc:
        doc_in = input_func(f"[1/{total_steps}] Input document path [{default_doc}]: ").strip()
        document_path = doc_in if doc_in else default_doc
    else:
        doc_in = input_func(f"[1/{total_steps}] Input document path: ").strip()
        document_path = doc_in

    # 2..N Dimensions driven by schema
    criteria_kwargs: Dict[str, str] = {}
    for step_num, dim in enumerate(WIZARD_DIMENSIONS, start=2):
        print_func(f"\n[{step_num}/{total_steps}] Select {dim.title}:")
        for idx, (k, desc) in enumerate(dim.options, 1):
            print_func(f"  {idx}) {k:<24} - {desc}")
        choice = input_func(f"Choose {dim.key} [1-{len(dim.options)}, default {dim.default}]: ").strip()
        resolved_key = resolve_choice(choice, dim.options, default=dim.default)
        criteria_kwargs[dim.key] = resolved_key

    criteria = PlannerCriteria.from_dict(criteria_kwargs)

    # Language Hint & Threshold
    final_step = total_steps
    lang_in = input_func(f"\n[{final_step}/{total_steps}] Language hint code (e.g. 'en', 'pl', 'de') [press Enter for none]: ").strip()
    language: Optional[str] = lang_in if lang_in and lang_in.lower() != "none" else None

    thresh_in = input_func("Target confidence threshold (0.0 - 1.0) [default: 0.82]: ").strip()
    try:
        target_threshold = float(thresh_in) if thresh_in else 0.82
    except ValueError:
        target_threshold = 0.82

    # Calculate Scores
    scores = planner.calculate_scores(criteria=criteria)
    suggested = planner.suggest_preset_order(scores)

    print_func("\n" + "-" * 68)
    print_func("Calculated Preset Suitability Scores:")
    for rank, p in enumerate(suggested, 1):
        tag = "[Primary Candidate]" if rank == 1 else f"[Fallback {rank - 1}]"
        score_val = scores.get(p, 0.0)
        print_func(f"  {rank}. {p:<20} Score: {score_val:.3f}  {tag}")
    print_func("-" * 68)

    # Prompt for Override
    suggested_chain = " -> ".join(suggested)
    prompt_msg = f"Accept suggested preset order ({suggested_chain})? [Y/n/override]: "
    action = input_func(prompt_msg).strip().lower()

    override_order: Optional[List[str]] = None
    if action in ("n", "no", "override", "o"):
        weights_keys = list(planner.weights.keys())
        print_func("\nAvailable presets: " + ", ".join(weights_keys))
        override_in = input_func("Enter custom preset order as comma-separated IDs (or press Enter to select primary only): ").strip()
        if override_in:
            custom_presets = [p.strip() for p in override_in.split(",") if p.strip() in planner.weights]
            if custom_presets:
                for p in suggested:
                    if p not in custom_presets:
                        custom_presets.append(p)
                override_order = custom_presets
        else:
            primary_in = input_func(f"Enter primary preset ID [{suggested[0]}]: ").strip()
            if primary_in in planner.weights:
                override_order = [primary_in] + [p for p in suggested if p != primary_in]

    plan = planner.create_plan(
        document_path=document_path,
        criteria=criteria,
        language=language,
        target_threshold=target_threshold,
        override_order=override_order,
    )

    fallback_str = ", ".join(f['preset'] for f in plan.fallback_queue)
    override_str = "YES" if plan.overridden else "NO"
    lang_str = plan.language if plan.language else "None (auto-detect)"

    print_func("\nFinal Execution Plan Configured:")
    print_func(f"  Primary Preset:  {plan.primary_preset}")
    print_func(f"  Fallback Queue:  {fallback_str}")
    print_func(f"  User Override:   {override_str}")
    print_func(f"  Target Threshold: {plan.target_threshold}")
    print_func(f"  Language Hint:   {lang_str}")

    return plan
