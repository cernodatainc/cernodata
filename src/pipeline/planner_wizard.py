"""
src/pipeline/planner_wizard.py

Interactive CLI wizard flow for inquiring document characteristics and system constraints.
"""

from typing import List, Tuple, Callable, Optional, Any
from src.pipeline.planner_models import DocumentPlan
from src.pipeline.planner_options import (
    TAXONOMY_OPTIONS,
    HARDWARE_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
)


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
    default_doc: Optional[str] = None
) -> DocumentPlan:
    """Guides user through interactive questionnaire, presents preset recommendations, and prompts for override."""
    print_func("=" * 68)
    print_func("cernodata Preset Planner & Pipeline Configuration Wizard")
    print_func("=" * 68)

    # 1. Document Path
    if default_doc:
        doc_in = input_func(f"[1/6] Input document path [{default_doc}]: ").strip()
        document_path = doc_in if doc_in else default_doc
    else:
        doc_in = input_func("[1/6] Input document path: ").strip()
        document_path = doc_in

    # 2. Document Taxonomy
    print_func("\n[2/6] Select Document Taxonomy:")
    for idx, (k, desc) in enumerate(TAXONOMY_OPTIONS, 1):
        print_func(f"  {idx}) {k:<22} - {desc}")
    tax_choice = input_func("Choose taxonomy [1-6, default 6 (general_text)]: ").strip()
    taxonomy = resolve_choice(tax_choice, TAXONOMY_OPTIONS, default="general_text")

    # 3. Hardware Profile
    print_func("\n[3/6] Select Hardware Profile:")
    for idx, (k, desc) in enumerate(HARDWARE_OPTIONS, 1):
        print_func(f"  {idx}) {k:<22} - {desc}")
    hw_choice = input_func("Choose hardware profile [1-3, default 1 (low_spec_cpu)]: ").strip()
    hardware = resolve_choice(hw_choice, HARDWARE_OPTIONS, default="low_spec_cpu")

    # 4. Target Quality vs Speed
    print_func("\n[4/6] Select Quality vs. Speed Target:")
    for idx, (k, desc) in enumerate(TARGET_OPTIONS, 1):
        print_func(f"  {idx}) {k:<24} - {desc}")
    tgt_choice = input_func("Choose target [1-2, default 2 (high_precision_structure)]: ").strip()
    target = resolve_choice(tgt_choice, TARGET_OPTIONS, default="high_precision_structure")

    # 5. Security Constraints
    print_func("\n[5/6] Select Security / Network Constraint:")
    for idx, (k, desc) in enumerate(SECURITY_OPTIONS, 1):
        print_func(f"  {idx}) {k:<22} - {desc}")
    sec_choice = input_func("Choose security mode [1-2, default 1 (air_gapped_local)]: ").strip()
    security = resolve_choice(sec_choice, SECURITY_OPTIONS, default="air_gapped_local")

    # 6. Language & Threshold
    lang_in = input_func("\n[6/6] Language hint code (e.g. 'en', 'pl', 'de') [default: 'en']: ").strip()
    language = lang_in if lang_in else "en"

    thresh_in = input_func("Target confidence threshold (0.0 - 1.0) [default: 0.82]: ").strip()
    try:
        target_threshold = float(thresh_in) if thresh_in else 0.82
    except ValueError:
        target_threshold = 0.82

    # Calculate Scores
    scores = planner.calculate_scores(taxonomy, hardware, target, security)
    suggested = planner.suggest_preset_order(scores)

    print_func("\n" + "-" * 68)
    print_func("Calculated Preset Suitability Scores:")
    for rank, p in enumerate(suggested, 1):
        tag = "[Primary Candidate]" if rank == 1 else f"[Fallback {rank - 1}]"
        print_func(f"  {rank}. {p:<20} Score: {scores[p]:.3f}  {tag}")
    print_func("-" * 68)

    # Prompt for Override
    prompt_msg = f"Accept suggested preset order ({' -> '.join(suggested)})? [Y/n/override]: "
    action = input_func(prompt_msg).strip().lower()

    override_order: Optional[List[str]] = None
    if action in ("n", "no", "override", "o"):
        print_func("\nAvailable presets: " + ", ".join(planner.weights.keys()))
        override_in = input_func("Enter custom preset order as comma-separated IDs (or press Enter to select primary only): ").strip()
        if override_in:
            custom_presets = [p.strip() for p in override_in.split(",") if p.strip() in planner.weights]
            if custom_presets:
                # Append any missing candidate presets at the end
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
        taxonomy=taxonomy,
        hardware=hardware,
        target=target,
        security=security,
        language=language,
        target_threshold=target_threshold,
        override_order=override_order
    )

    print_func("\nFinal Execution Plan Configured:")
    print_func(f"  Primary Preset:  {plan.primary_preset}")
    print_func(f"  Fallback Queue:  {', '.join(f['preset'] for f in plan.fallback_queue)}")
    print_func(f"  User Override:   {'YES' if plan.overridden else 'NO'}")
    print_func(f"  Target Threshold: {plan.target_threshold}")
    print_func(f"  Language Hint:   {plan.language}")

    return plan
