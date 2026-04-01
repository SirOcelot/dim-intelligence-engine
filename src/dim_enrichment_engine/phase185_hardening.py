from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


APP_VERSION = "0.18.5"
DEFAULT_OUTPUT_DIRNAME = "output"


class WarmindPipelineError(RuntimeError):
    pass


@dataclass
class PipelineResult:
    ok: bool
    action: str
    message: str
    output_files: list[str]
    payload: dict[str, Any]


def ensure_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise WarmindPipelineError(f"Required file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WarmindPipelineError(f"Invalid JSON in {path.name}: {exc}") from exc


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def validate_csv_inputs(weapons: str | Path, armor: str | Path, loadouts: str | Path | None = None) -> tuple[Path, Path, Path | None]:
    weapons_path = Path(weapons).expanduser().resolve()
    armor_path = Path(armor).expanduser().resolve()
    loadouts_path = Path(loadouts).expanduser().resolve() if loadouts else None

    missing = []
    if not weapons_path.exists():
        missing.append(f"Weapons CSV not found: {weapons_path}")
    if not armor_path.exists():
        missing.append(f"Armor CSV not found: {armor_path}")
    if loadouts_path and not loadouts_path.exists():
        missing.append(f"Loadouts CSV not found: {loadouts_path}")
    if missing:
        raise WarmindPipelineError("\n".join(missing))
    return weapons_path, armor_path, loadouts_path


def _invoke_phase(phase_main: Callable[[], None], argv: list[str]) -> None:
    import sys

    old_argv = sys.argv[:]
    try:
        sys.argv = argv
        phase_main()
    finally:
        sys.argv = old_argv


def _base_args(module_name: str, weapons: Path, armor: Path, output_dir: Path, loadouts: Path | None = None) -> list[str]:
    args = [module_name, "--weapons", str(weapons), "--armor", str(armor), "--output-dir", str(output_dir)]
    if loadouts:
        args.extend(["--loadouts", str(loadouts)])
    return args


def run_analysis(weapons: str | Path, armor: str | Path, output_dir: str | Path, loadouts: str | Path | None = None, question: str | None = None) -> PipelineResult:
    from dim_enrichment_engine.phase43_interactive import main as phase_main

    weapons_path, armor_path, loadouts_path = validate_csv_inputs(weapons, armor, loadouts)
    out = ensure_output_dir(output_dir)
    argv = _base_args("phase43_interactive", weapons_path, armor_path, out, loadouts_path)
    if question:
        argv.extend(["--question", question])
    _invoke_phase(phase_main, argv)

    files = [out / "Build QA.md", out / "Question Answer.txt", out / "qa_context.json"]
    return PipelineResult(
        ok=True,
        action="analysis",
        message="Analysis completed.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "build_qa": read_text_if_exists(out / "Build QA.md"),
            "answer": read_text_if_exists(out / "Question Answer.txt"),
            "qa_context": read_json(out / "qa_context.json") if (out / "qa_context.json").exists() else {},
        },
    )


def run_scoring(weapons: str | Path, armor: str | Path, output_dir: str | Path, loadouts: str | Path | None = None, question: str | None = None) -> PipelineResult:
    from dim_enrichment_engine.phase70_scoring import main as phase_main

    weapons_path, armor_path, loadouts_path = validate_csv_inputs(weapons, armor, loadouts)
    out = ensure_output_dir(output_dir)
    argv = _base_args("phase70_scoring", weapons_path, armor_path, out, loadouts_path)
    argv.extend(["--question", question or "score this build"])
    _invoke_phase(phase_main, argv)

    files = [out / "Scoring.md", out / "Scoring Answer.txt", out / "scoring_context.json"]
    return PipelineResult(
        ok=True,
        action="scoring",
        message="Scoring completed.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "scoring_md": read_text_if_exists(out / "Scoring.md"),
            "answer": read_text_if_exists(out / "Scoring Answer.txt"),
            "context": read_json(out / "scoring_context.json") if (out / "scoring_context.json").exists() else {},
        },
    )


def run_mode(weapons: str | Path, armor: str | Path, output_dir: str | Path, mode: str, loadouts: str | Path | None = None) -> PipelineResult:
    from dim_enrichment_engine.phase132_modes import main as phase_main

    weapons_path, armor_path, loadouts_path = validate_csv_inputs(weapons, armor, loadouts)
    out = ensure_output_dir(output_dir)
    argv = _base_args("phase132_modes", weapons_path, armor_path, out, loadouts_path)
    argv.extend(["--mode", mode])
    _invoke_phase(phase_main, argv)

    files = [out / "Phase132 Modes.md", out / "phase132_modes.json"]
    return PipelineResult(
        ok=True,
        action="mode",
        message=f"Mode adaptation '{mode}' completed.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "mode_md": read_text_if_exists(out / "Phase132 Modes.md"),
            "mode_json": read_json(out / "phase132_modes.json") if (out / "phase132_modes.json").exists() else {},
        },
    )


def run_feedback(weapons: str | Path, armor: str | Path, output_dir: str | Path, mode: str, feedback_result: str, loadouts: str | Path | None = None, feedback_store: str | Path | None = None) -> PipelineResult:
    from dim_enrichment_engine.phase133_feedback import main as phase_main

    weapons_path, armor_path, loadouts_path = validate_csv_inputs(weapons, armor, loadouts)
    out = ensure_output_dir(output_dir)
    store_path = Path(feedback_store).expanduser().resolve() if feedback_store else out / "phase133_feedback_store.json"
    argv = _base_args("phase133_feedback", weapons_path, armor_path, out, loadouts_path)
    argv.extend(["--mode", mode, "--feedback-result", feedback_result, "--feedback-store", str(store_path)])
    _invoke_phase(phase_main, argv)

    files = [out / "Phase133 Feedback.md", out / "phase133_feedback.json", store_path]
    return PipelineResult(
        ok=True,
        action="feedback",
        message=f"Feedback loop updated for mode '{mode}' with result '{feedback_result}'.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "feedback_md": read_text_if_exists(out / "Phase133 Feedback.md"),
            "feedback_json": read_json(out / "phase133_feedback.json") if (out / "phase133_feedback.json").exists() else {},
            "feedback_store": read_json(store_path) if store_path.exists() else {},
        },
    )


def run_refinement(weapons: str | Path, armor: str | Path, output_dir: str | Path, loadouts: str | Path | None = None) -> PipelineResult:
    from dim_enrichment_engine.phase115_refinement import main as phase_main

    weapons_path, armor_path, loadouts_path = validate_csv_inputs(weapons, armor, loadouts)
    out = ensure_output_dir(output_dir)
    argv = _base_args("phase115_refinement", weapons_path, armor_path, out, loadouts_path)
    _invoke_phase(phase_main, argv)

    files = [out / "Phase115 Refinement.md", out / "phase115_refinement.json"]
    return PipelineResult(
        ok=True,
        action="refinement",
        message="Item refinement completed.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "refinement_md": read_text_if_exists(out / "Phase115 Refinement.md"),
            "refinement_json": read_json(out / "phase115_refinement.json") if (out / "phase115_refinement.json").exists() else {},
        },
    )


def run_execute_preview(output_dir: str | Path, direct_equip: bool = False, confirm: bool = False) -> PipelineResult:
    from dim_enrichment_engine.phase120_execute import main as phase_main

    out = ensure_output_dir(output_dir)
    refinement_json = out / "phase115_refinement.json"
    if not refinement_json.exists():
        raise WarmindPipelineError("Execution preview requires phase115_refinement.json. Run refinement first.")

    argv = ["phase120_execute", "--output-dir", str(out)]
    if direct_equip:
        argv.append("--direct-equip")
    if confirm:
        argv.append("--confirm")
    _invoke_phase(phase_main, argv)

    files = [out / "Phase120 Diff.md", out / "phase120_result.json", out / "phase120_equip_plan.json"]
    return PipelineResult(
        ok=True,
        action="execute_preview",
        message="Execution preview completed.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "diff_md": read_text_if_exists(out / "Phase120 Diff.md"),
            "result_json": read_json(out / "phase120_result.json") if (out / "phase120_result.json").exists() else {},
            "equip_plan": read_json(out / "phase120_equip_plan.json") if (out / "phase120_equip_plan.json").exists() else {},
        },
    )


def run_workflow(output_dir: str | Path, workflow_mode: str = "preview") -> PipelineResult:
    from dim_enrichment_engine.phase170_workflow import main as phase_main

    out = ensure_output_dir(output_dir)
    argv = ["phase170_workflow", "--output-dir", str(out), "--workflow-mode", workflow_mode]
    _invoke_phase(phase_main, argv)

    files = [out / "Phase170 Workflow.md", out / "phase170_workflow.json", out / "phase170_dim_payload.json"]
    return PipelineResult(
        ok=True,
        action="workflow",
        message=f"Workflow integration completed in '{workflow_mode}' mode.",
        output_files=[str(f) for f in files if f.exists()],
        payload={
            "workflow_md": read_text_if_exists(out / "Phase170 Workflow.md"),
            "workflow_json": read_json(out / "phase170_workflow.json") if (out / "phase170_workflow.json").exists() else {},
            "dim_payload": read_json(out / "phase170_dim_payload.json") if (out / "phase170_dim_payload.json").exists() else {},
        },
    )


def run_guided_flow(weapons: str | Path, armor: str | Path, output_dir: str | Path, mode: str, loadouts: str | Path | None = None) -> PipelineResult:
    out = ensure_output_dir(output_dir)
    analysis = run_analysis(weapons, armor, out, loadouts=loadouts, question=None)
    mode_result = run_mode(weapons, armor, out, mode=mode, loadouts=loadouts)
    refinement = run_refinement(weapons, armor, out, loadouts=loadouts)
    workflow = run_workflow(out, workflow_mode="preview")
    return PipelineResult(
        ok=True,
        action="guided_flow",
        message=f"Guided flow completed for mode '{mode}'.",
        output_files=analysis.output_files + mode_result.output_files + refinement.output_files + workflow.output_files,
        payload={
            "analysis": analysis.payload,
            "mode": mode_result.payload,
            "refinement": refinement.payload,
            "workflow": workflow.payload,
        },
    )


def safe_run(action: Callable[..., PipelineResult], *args: Any, **kwargs: Any) -> PipelineResult:
    try:
        return action(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return PipelineResult(
            ok=False,
            action=getattr(action, "__name__", "unknown"),
            message=str(exc),
            output_files=[],
            payload={"error": str(exc), "traceback": traceback.format_exc()},
        )
