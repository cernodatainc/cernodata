"""
src/pipeline/planner.py

Data-Driven Preset Planner.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
"""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Callable

DEFAULT_PRESET_WEIGHTS: Dict[str, Dict[str, float]] = {
    "docling_fast": {
        "low_spec_cpu": 0.90,
        "rapid_approximate": 0.80,
        "financial_report": 0.60,
        "scanned_form": 0.30,
        "air_gapped_local": 0.90,
        "hosted_vision_api": 0.50,
        "multicolumn_article": 0.70,
        "tabular_ledger": 0.60,
        "mixed_text_image": 0.50,
        "general_text": 0.85,
        "workstation_cuda": 0.60,
        "cloud_cluster": 0.50,
        "high_precision_structure": 0.50,
    },
    "docling_deep": {
        "workstation_cuda": 0.90,
        "cloud_cluster": 0.95,
        "high_precision_structure": 0.85,
        "financial_report": 0.85,
        "tabular_ledger": 0.90,
        "multicolumn_article": 0.85,
        "scanned_form": 0.75,
        "mixed_text_image": 0.70,
        "general_text": 0.80,
        "air_gapped_local": 0.85,
        "hosted_vision_api": 0.70,
        "low_spec_cpu": 0.40,
        "rapid_approximate": 0.40,
    },
    "vision_llm_direct": {
        "scanned_form": 0.95,
        "mixed_text_image": 0.90,
        "high_precision_structure": 0.90,
        "cloud_cluster": 0.90,
        "workstation_cuda": 0.75,
        "financial_report": 0.70,
        "tabular_ledger": 0.65,
        "multicolumn_article": 0.75,
        "general_text": 0.60,
        "low_spec_cpu": 0.10,
        "rapid_approximate": 0.30,
        "air_gapped_local": 0.30,
        "hosted_vision_api": 0.95,
    }
}

TAXONOMY_OPTIONS = [
    ("financial_report", "Dense numbers, tables, multi-page financial statements"),
    ("multicolumn_article", "Academic or corporate papers with 2+ text columns"),
    ("scanned_form", "Low-DPI scanned documents, hand-signed forms, low contrast"),
    ("tabular_ledger", "Spreadsheet-like grid structures"),
    ("mixed_text_image", "Marketing materials, slide decks, embedded graphics"),
    ("general_text", "Standard single or multi-page prose documents")
]

HARDWARE_OPTIONS = [
    ("low_spec_cpu", "Shared CPU/RAM, no discrete GPU (<= 4GB RAM)"),
    ("workstation_cuda", "Local CUDA-enabled GPU (NVIDIA RTX/Tesla)"),
    ("cloud_cluster", "Distributed cloud node / multi-GPU execution")
]

TARGET_OPTIONS = [
    ("rapid_approximate", "Fast throughput, acceptable minor structural drift"),
    ("high_precision_structure", "Maximum layout fidelity, exact bounding box extraction")
]

SECURITY_OPTIONS = [
    ("air_gapped_local", "Zero external network calls (strictly local models)"),
    ("hosted_vision_api", "Cloud multimodal APIs allowed (hosted vision models)")
]


@dataclass
class DocumentPlan:
    document_path: str
    taxonomy: str
    hardware: str
    target: str
    security: str
    language: str
    target_threshold: float
    primary_preset: str
    fallback_queue: List[Dict[str, Any]]
    preset_order: List[str]
    suggested_order: List[str]
    overridden: bool
    scores: Dict[str, float]
    created_at: str
    diacritic_hit: float = 0.20

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, output_path: str = os.path.join("output", "plan.json")) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentPlan":
        return cls(
            document_path=data.get("document_path", ""),
            taxonomy=data.get("taxonomy", "general_text"),
            hardware=data.get("hardware", "low_spec_cpu"),
            target=data.get("target", "high_precision_structure"),
            security=data.get("security", "air_gapped_local"),
            language=data.get("language", "en"),
            target_threshold=float(data.get("target_threshold", 0.82)),
            primary_preset=data.get("primary_preset", "docling_fast"),
            fallback_queue=data.get("fallback_queue", []),
            preset_order=data.get("preset_order", ["docling_fast"]),
            suggested_order=data.get("suggested_order", ["docling_fast"]),
            overridden=bool(data.get("overridden", False)),
            scores=data.get("scores", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            diacritic_hit=float(data.get("diacritic_hit", 0.20))
        )

    @classmethod
    def load(cls, file_path: str) -> "DocumentPlan":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class PresetPlanner:
    """Calculates preset confidence scores and generates pipeline execution plans."""

    def __init__(self, weights: Optional[Dict[str, Dict[str, float]]] = None):
        self.weights = weights or DEFAULT_PRESET_WEIGHTS

    def calculate_scores(self, taxonomy: str, hardware: str, target: str, security: str) -> Dict[str, float]:
        answers = [taxonomy, hardware, target, security]
        scores: Dict[str, float] = {}

        for preset_id, weight_map in self.weights.items():
            matched_weights = [weight_map.get(ans, 0.50) for ans in answers]
            score = sum(matched_weights) / len(matched_weights)
            scores[preset_id] = round(score, 3)

        return scores

    def suggest_preset_order(self, scores: Dict[str, float]) -> List[str]:
        return sorted(scores.keys(), key=lambda p: scores[p], reverse=True)

    def create_plan(
        self,
        document_path: str = "",
        taxonomy: str = "general_text",
        hardware: str = "low_spec_cpu",
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        language: str = "en",
        target_threshold: float = 0.82,
        override_order: Optional[List[str]] = None,
        override_primary: Optional[str] = None,
        diacritic_hit: float = 0.20
    ) -> DocumentPlan:
        scores = self.calculate_scores(taxonomy, hardware, target, security)
        suggested = self.suggest_preset_order(scores)

        overridden = False
        if override_order:
            order = list(override_order)
            overridden = (order != suggested)
        elif override_primary:
            order = [override_primary] + [p for p in suggested if p != override_primary]
            overridden = (order != suggested)
        else:
            order = list(suggested)

        primary_preset = order[0]
        fallback_queue = [{"preset": p, "score": scores.get(p, 0.50)} for p in order[1:]]

        return DocumentPlan(
            document_path=document_path,
            taxonomy=taxonomy,
            hardware=hardware,
            target=target,
            security=security,
            language=language,
            target_threshold=target_threshold,
            primary_preset=primary_preset,
            fallback_queue=fallback_queue,
            preset_order=order,
            suggested_order=suggested,
            overridden=overridden,
            scores=scores,
            created_at=datetime.now(timezone.utc).isoformat(),
            diacritic_hit=diacritic_hit
        )

    @staticmethod
    def _resolve_choice(choice: str, options: List[tuple[str, str]], default: str) -> str:
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

    def interactive_session(
        self,
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
        taxonomy = self._resolve_choice(tax_choice, TAXONOMY_OPTIONS, default="general_text")

        # 3. Hardware Profile
        print_func("\n[3/6] Select Hardware Profile:")
        for idx, (k, desc) in enumerate(HARDWARE_OPTIONS, 1):
            print_func(f"  {idx}) {k:<22} - {desc}")
        hw_choice = input_func("Choose hardware profile [1-3, default 1 (low_spec_cpu)]: ").strip()
        hardware = self._resolve_choice(hw_choice, HARDWARE_OPTIONS, default="low_spec_cpu")

        # 4. Target Quality vs Speed
        print_func("\n[4/6] Select Quality vs. Speed Target:")
        for idx, (k, desc) in enumerate(TARGET_OPTIONS, 1):
            print_func(f"  {idx}) {k:<24} - {desc}")
        tgt_choice = input_func("Choose target [1-2, default 2 (high_precision_structure)]: ").strip()
        target = self._resolve_choice(tgt_choice, TARGET_OPTIONS, default="high_precision_structure")

        # 5. Security Constraints
        print_func("\n[5/6] Select Security / Network Constraint:")
        for idx, (k, desc) in enumerate(SECURITY_OPTIONS, 1):
            print_func(f"  {idx}) {k:<22} - {desc}")
        sec_choice = input_func("Choose security mode [1-2, default 1 (air_gapped_local)]: ").strip()
        security = self._resolve_choice(sec_choice, SECURITY_OPTIONS, default="air_gapped_local")

        # 6. Language & Threshold
        lang_in = input_func("\n[6/6] Language hint code (e.g. 'en', 'pl', 'de') [default: 'en']: ").strip()
        language = lang_in if lang_in else "en"

        thresh_in = input_func("Target confidence threshold (0.0 - 1.0) [default: 0.82]: ").strip()
        try:
            target_threshold = float(thresh_in) if thresh_in else 0.82
        except ValueError:
            target_threshold = 0.82

        # Calculate Scores
        scores = self.calculate_scores(taxonomy, hardware, target, security)
        suggested = self.suggest_preset_order(scores)

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
            print_func("\nAvailable presets: " + ", ".join(self.weights.keys()))
            override_in = input_func("Enter custom preset order as comma-separated IDs (or press Enter to select primary only): ").strip()
            if override_in:
                custom_presets = [p.strip() for p in override_in.split(",") if p.strip() in self.weights]
                if custom_presets:
                    # Append any missing candidate presets at the end
                    for p in suggested:
                        if p not in custom_presets:
                            custom_presets.append(p)
                    override_order = custom_presets
            else:
                primary_in = input_func(f"Enter primary preset ID [{suggested[0]}]: ").strip()
                if primary_in in self.weights:
                    override_order = [primary_in] + [p for p in suggested if p != primary_in]

        plan = self.create_plan(
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
