from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dim_enrichment_engine.phase185_hardening import (
    safe_run,
    run_analysis,
    run_execute_preview,
    run_feedback,
    run_guided_flow,
    run_mode,
    run_refinement,
    run_scoring,
    run_workflow,
)
from dim_enrichment_engine.phase190_dim_live import main as live_equip_main
from dim_enrichment_engine.phase200_encounter_library import main as encounter_library_main
from dim_enrichment_engine.phase210_multistage import main as multistage_main


def _invoke(main_func, argv: list[str]) -> None:
    import sys

    old = sys.argv[:]
    try:
        sys.argv = argv
        main_func()
    finally:
        sys.argv = old


def _csv_kwargs(args) -> dict[str, str | None]:
    return {
        "weapons": args.weapons,
        "armor": args.armor,
        "loadouts": args.loadouts,
        "output_dir": args.output_dir,
    }


def _result_dict(result) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "action": result.action,
        "message": result.message,
        "output_files": result.output_files,
        "payload": result.payload,
    }


def run_preset(args) -> dict[str, Any]:
    argv = [
        "phase200_encounter_library",
        "--weapons", args.weapons,
        "--armor", args.armor,
        "--output-dir", args.output_dir,
        "--auth-dir", args.auth_dir,
        "--preset", args.preset,
    ]
    if args.loadouts:
        argv.extend(["--loadouts", args.loadouts])
    if args.membership_type is not None:
        argv.extend(["--membership-type", str(args.membership_type)])
    if args.membership_id:
        argv.extend(["--membership-id", args.membership_id])
    if args.character_id:
        argv.extend(["--character-id", args.character_id])
    if args.dry_run:
        argv.append("--dry-run")
    _invoke(encounter_library_main, argv)
    result_path = Path(args.output_dir) / "phase200_encounter_library.json"
    return json.loads(result_path.read_text(encoding="utf-8"))


def run_plan(args) -> dict[str, Any]:
    argv = [
        "phase210_multistage",
        "--weapons", args.weapons,
        "--armor", args.armor,
        "--output-dir", args.output_dir,
        "--auth-dir", args.auth_dir,
        "--plan", args.plan,
    ]
    if args.loadouts:
        argv.extend(["--loadouts", args.loadouts])
    if args.membership_type is not None:
        argv.extend(["--membership-type", str(args.membership_type)])
    if args.membership_id:
        argv.extend(["--membership-id", args.membership_id])
    if args.character_id:
        argv.extend(["--character-id", args.character_id])
    if args.dry_run:
        argv.append("--dry-run")
    _invoke(multistage_main, argv)
    result_path = Path(args.output_dir) / "phase210_multistage.json"
    return json.loads(result_path.read_text(encoding="utf-8"))


def run_live_equip(args) -> dict[str, Any]:
    argv = [
        "phase190_dim_live",
        "--output-dir", args.output_dir,
        "--auth-dir", args.auth_dir,
    ]
    if args.membership_type is not None:
        argv.extend(["--membership-type", str(args.membership_type)])
    if args.membership_id:
        argv.extend(["--membership-id", args.membership_id])
    if args.character_id:
        argv.extend(["--character-id", args.character_id])
    if args.dry_run:
        argv.append("--dry-run")
    _invoke(live_equip_main, argv)
    result_path = Path(args.output_dir) / "phase190_live_equip.json"
    return json.loads(result_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind complete unified orchestration")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--auth-dir", default="auth")
    parser.add_argument("--question", required=False)
    parser.add_argument("--mode", choices=["safe", "aggressive", "comfort", "anti-champion", "economy"], default="safe")
    parser.add_argument("--feedback-result", choices=["better", "same", "still_bad"], default="better")
    parser.add_argument("--workflow-mode", choices=["preview", "direct"], default="preview")
    parser.add_argument("--preset", required=False)
    parser.add_argument("--plan", required=False)
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--character-id", required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--run",
        nargs="+",
        required=True,
        choices=[
            "analysis",
            "scoring",
            "mode",
            "feedback",
            "refinement",
            "workflow",
            "guided",
            "execute_preview",
            "live_equip",
            "preset",
            "plan",
        ],
        help="One or more actions to run in order.",
    )
    args = parser.parse_args()

    output: dict[str, Any] = {"actions": []}

    for action in args.run:
        if action == "analysis":
            result = safe_run(run_analysis, **_csv_kwargs(args), question=args.question)
            output["actions"].append(_result_dict(result))
        elif action == "scoring":
            result = safe_run(run_scoring, **_csv_kwargs(args), question=args.question or "score this build")
            output["actions"].append(_result_dict(result))
        elif action == "mode":
            result = safe_run(run_mode, **_csv_kwargs(args), mode=args.mode)
            output["actions"].append(_result_dict(result))
        elif action == "feedback":
            result = safe_run(run_feedback, **_csv_kwargs(args), mode=args.mode, feedback_result=args.feedback_result)
            output["actions"].append(_result_dict(result))
        elif action == "refinement":
            result = safe_run(run_refinement, **_csv_kwargs(args))
            output["actions"].append(_result_dict(result))
        elif action == "workflow":
            result = safe_run(run_workflow, output_dir=args.output_dir, workflow_mode=args.workflow_mode)
            output["actions"].append(_result_dict(result))
        elif action == "guided":
            result = safe_run(run_guided_flow, **_csv_kwargs(args), mode=args.mode)
            output["actions"].append(_result_dict(result))
        elif action == "execute_preview":
            result = safe_run(run_execute_preview, output_dir=args.output_dir, direct_equip=args.workflow_mode == "direct", confirm=args.workflow_mode == "direct")
            output["actions"].append(_result_dict(result))
        elif action == "live_equip":
            output["actions"].append({"ok": True, "action": "live_equip", "payload": run_live_equip(args)})
        elif action == "preset":
            if not args.preset:
                raise SystemExit("--preset is required when using --run preset")
            output["actions"].append({"ok": True, "action": "preset", "payload": run_preset(args)})
        elif action == "plan":
            if not args.plan:
                raise SystemExit("--plan is required when using --run plan")
            output["actions"].append({"ok": True, "action": "plan", "payload": run_plan(args)})

    result_path = Path(args.output_dir) / "warmind_complete_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
