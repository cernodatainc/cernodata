"""
src/pipeline/parsers/cli_adapter.py

Parser preset adapter executing external CLI OCR tools via subprocess.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from src.dom import DocumentDOM
from src.pipeline.parsers.adapters import ParserExecutionOptions
from src.pipeline.parsers.custom_output import convert_raw_output_to_dom
from src.schemas.custom_preset import CustomPresetConfig, ParameterWiggleSpec, PresetBackendType

logger = logging.getLogger("cernodata.pipeline.parsers.cli_adapter")


def _output_filename_for_format(output_format: str) -> str:
    fmt = output_format.strip().lower()
    if fmt == "cernodata_dom_json":
        return "output.json"
    if fmt == "markdown":
        return "output.md"
    if fmt == "hocr":
        return "output.hocr"
    if fmt == "text":
        return "output.txt"
    raise ValueError(f"Unsupported output_format: {output_format!r}")


def _read_cli_output(output_path: str, stdout: str) -> str:
    """Reads subprocess output from output_path (or .txt sidecar / directory), falling back to stdout."""
    for cand in (output_path, f"{output_path}.txt"):
        if os.path.isfile(cand) and os.path.getsize(cand) > 0:
            with open(cand, "r", encoding="utf-8", errors="replace") as fp:
                return fp.read()

    if os.path.isdir(output_path):
        for fname in sorted(os.listdir(output_path)):
            fpath = os.path.join(output_path, fname)
            if os.path.isfile(fpath) and fname.lower().endswith((".json", ".md", ".txt", ".hocr")):
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
                if content.strip():
                    return content

    return stdout


def build_cli_command(
    command_template: Sequence[str],
    resolved_path: str,
    output_path: str,
    language: Optional[str] = "en",
    page_index: int = 1,
    wiggle_specs: Sequence[ParameterWiggleSpec] = (),
    extra_parameters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, str]]:
    """Substitutes template placeholders and injects wiggled parameters into CLI command tokens."""
    placeholders: Dict[str, str] = {
        "input_path": resolved_path,
        "output_path": output_path,
        "page_index": str(page_index),
        "language": str(language or "en"),
    }
    for spec in wiggle_specs:
        if spec.default_value is not None:
            placeholders[spec.name] = str(spec.default_value)

    extra = dict(extra_parameters) if extra_parameters else {}
    for key, val in extra.items():
        if val is not None:
            placeholders[str(key)] = str(val)

    substituted_keys: set[str] = set()
    cmd: List[str] = []
    for raw_tok in command_template:
        tok = str(raw_tok)
        for p_key, p_val in placeholders.items():
            marker = f"{{{p_key}}}"
            if marker in tok:
                tok = tok.replace(marker, p_val)
                substituted_keys.add(p_key)
        cmd.append(tok)

    for key, val in extra.items():
        if val is None or key in substituted_keys:
            continue
        flag_candidates = (key,) if key.startswith("-") else (f"--{key}", f"-{key}")
        updated = False
        for idx, token in enumerate(cmd):
            if token in flag_candidates and idx + 1 < len(cmd):
                cmd[idx + 1] = str(val)
                updated = True
                break
        if not updated:
            flag_tok = key if key.startswith("-") else f"--{key}"
            cmd.extend([flag_tok, str(val)])

    env = dict(os.environ)
    for key, val in extra.items():
        if val is not None:
            env_name = "CERNODATA_PARAM_" + str(key).upper().replace("-", "_")
            env[env_name] = str(val)

    return cmd, env


class SubprocessCliPresetAdapter:
    """Adapter executing standalone CLI OCR binaries or scripts and normalizing output to DocumentDOM."""

    def __init__(
        self,
        config: Union[CustomPresetConfig, str],
        command_template: Optional[Sequence[str]] = None,
        output_format: str = "text",
        timeout_sec: int = 120,
        wiggle_parameters: Optional[Sequence[ParameterWiggleSpec]] = None,
    ) -> None:
        if isinstance(config, CustomPresetConfig):
            if config.backend_type != PresetBackendType.CLI_SUBPROCESS:
                raise ValueError(
                    f"SubprocessCliPresetAdapter requires cli_subprocess backend, got '{config.backend_type.value}'."
                )
            if not config.command_template:
                raise ValueError(f"Custom preset '{config.preset_id}' is missing command_template.")
            self.config = config
            self.preset_id = config.preset_id
            self.command_template = list(config.command_template)
            self.output_format = config.output_format
            self.timeout_sec = config.timeout_sec
            self.wiggle_parameters = list(config.wiggle_parameters)
        else:
            if not command_template:
                raise ValueError("command_template is required when constructing SubprocessCliPresetAdapter by ID.")
            self.preset_id = str(config).strip()
            self.command_template = [str(t) for t in command_template]
            self.output_format = output_format
            self.timeout_sec = int(timeout_sec)
            self.wiggle_parameters = list(wiggle_parameters) if wiggle_parameters else []
            self.config = CustomPresetConfig(
                preset_id=self.preset_id,
                display_name=self.preset_id,
                backend_type=PresetBackendType.CLI_SUBPROCESS,
                command_template=self.command_template,
                output_format=self.output_format,
                timeout_sec=self.timeout_sec,
                wiggle_parameters=self.wiggle_parameters,
            )

    def can_handle(self, preset: str) -> bool:
        """Returns True only when the requested preset matches this adapter's preset_id."""
        return preset == self.preset_id

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        """Executes the configured CLI command in a temp directory and converts output to DocumentDOM."""
        with tempfile.TemporaryDirectory(prefix=f"cernodata_{self.preset_id}_") as tmp_dir:
            output_path = os.path.join(tmp_dir, _output_filename_for_format(self.output_format))
            cmd, env = build_cli_command(
                self.command_template,
                resolved_path=resolved_path,
                output_path=output_path,
                language=options.language,
                page_index=1,
                wiggle_specs=self.wiggle_parameters,
                extra_parameters=options.extra_parameters,
            )
            logger.info("Running CLI OCR preset '%s': %s", self.preset_id, " ".join(cmd))
            proc = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                env=env,
            )
            if proc.returncode != 0:
                stderr_msg = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(
                    f"CLI preset '{self.preset_id}' failed with exit code {proc.returncode}: {stderr_msg}"
                )

            raw_output = _read_cli_output(output_path, proc.stdout)
            return convert_raw_output_to_dom(
                raw_output=raw_output,
                resolved_path=resolved_path,
                output_format=self.output_format,
                preset_id=self.preset_id,
                page_index=1,
            )


__all__ = [
    "SubprocessCliPresetAdapter",
    "build_cli_command",
]
