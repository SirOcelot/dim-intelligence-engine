from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dim_enrichment_engine.phase185_hardening import ensure_output_dir
from dim_enrichment_engine.phase200_encounter_library import ENCOUNTER_LIBRARY
from dim_enrichment_engine.phase191_live_swap import main as live_swap_main

MULTISTAGE_PLANS: dict[str, dict[str, Any]] = {
    "gm_full_run": {
        "label": "GM Full Run",
        "description": "Safe open, safer boss room, then cleanup/fallback stage.",
        "stages": [
            {"name": "Entry / Lanes", "preset": "gm_corridor", "purpose": "Stabilize early combat lanes and champion checks."},
            {"name": "Boss Room", "preset": "gm_boss_room", "purpose": "Shift into boss-room-safe pressure and coverage."},
            {"name": "Recovery / Cleanup", "preset": "seasonal_speedfarm", "purpose": "Fallback cleanup shell when pressure drops or for fast mop-up."},
        ],
    },
    "raid_damage_cycle": {
        "label": "Raid Damage Cycle",
        "description": "Mechanic phase to burst DPS phase to post-DPS stabilization.",
        "stages": [
            {"name": "Mechanics / Add Control", "preset": "raid_ad_clear", "purpose": "Lower friction while handling movement and mechanics."},
            {"name": "Boss DPS", "preset": "raid_boss_burst", "purpose": "Maximize burst during short damage windows."},
            {"name": "Extended Damage / Stabilize", "preset": "raid_boss_sustained", "purpose": "Transition to more stable sustained damage if needed."},
        ],
    },
    "solo_dungeon_full_run": {
        "label": "Solo Dungeon Full Run",
        "description": "Traversal safety into boss sustain into fallback stabilization.",
        "stages": [
            {"name": "Traversal", "preset": "solo_dungeon_traversal", "purpose": "Stay alive and conserve ammo between major encounters."},
            {"name": "Boss", "preset": "solo_dungeon_boss", "purpose": "Bias into sustain and self-preservation for long solo phases."},
            {"name": "Recovery", "preset": "seasonal_speedfarm", "purpose": "Fallback shell to clean up and reset without overcommitting."},
        ],
    },
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_stage(
    weapons: Path,
    armor: Path,
    loadouts: Path | None,
    output_dir: Path,
    auth_dir: Path,
    preset: dict[str, Any],
    membership_type: int | None,
    membership_id: str | None,
    character_id: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    import sys

    argv = [
        "phase191_live_swap",
        "--weapons", str(weapons),
        "--armor", str(armor),
        "--output-dir", str(output_dir),
        "--auth-dir", str(auth_dir),
        "--activity", preset["activity"],
        "--mode", preset["mode"],
        "--encounter", preset["encounter"],
        "--range", preset["range"],
        "--damage", preset["damage"],
        "--team-roles", ",".join(preset.get("team_roles", [])),
        "--team-champions", ",".join(preset.get("team_champions", [])),
        "--champions", ",".join(preset.get("champions", [])),
    ]
    if loadouts:
        argv.extend(["--loadouts", str(loadouts)])
    if membership_type is not None:
        argv.extend(["--membership-type", str(membership_type)])
    if membership_id:
        argv.extend(["--membership-id", membership_id])
    if character_id:
        argv.extend(["--character-id", character_id])
    if dry_run:
        argv.append("--dry-run")

    old = sys.argv[:]
    try:
        sys.argv = argv
        live_swap_main()
    finally:
        sys.argv = old

    return read_json(output_dir / "phase191_live_swap_result.json")


def stage_summary(stage_name: str, stage_purpose: str, preset_key: str, result: dict[str, Any]) -> dict[str, Any]:
    equip = result.get("equip_result", {})
    mode_payload = result.get("mode_payload", {}) or {}
    encounter_payload = result.get("encounter_payload", {}) or {}
    team_payload = result.get("team_payload", {}) or {}
    return {
        "stage_name": stage_name,
        "purpose": stage_purpose,
        "preset": preset_key,
        "equipped_count": equip.get("equipped_count", 0),
        "dry_run_count": equip.get("dry_run_count", 0),
        "failed_count": equip.get("failed_count", 0),
        "unresolved_count": equip.get("unresolved_count", 0),
        "mode_overall": mode_payload.get("after_scores", {}).get("overall"),
        "encounter_overall": encounter_payload.get("after_scores", {}).get("overall"),
        "team_role": team_payload.get("team_context", {}).get("recommended_role"),
        "character_id": result.get("character_id"),
        "resolved_items": result.get("resolved_items", []),
        "equip_result": equip,
    }


def render_md(plan_key: str, plan: dict[str, Any], stage_results: list[dict[str, Any]]) -> str:
    lines = [
        "# Warmind Multi-Stage Loadout Plan",
        "",
        f"- Plan: **{plan_key}**",
        f"- Label: **{plan['label']}**",
        f"- Description: **{plan['description']}**",
        "",
        "## Stage Timeline",
    ]
    for idx, stage in enumerate(stage_results, start=1):
        lines.append(f"### Stage {idx}: {stage['stage_name']}")
        lines.append(f"- Purpose: **{stage['purpose']}**")
        lines.append(f"- Preset: **{stage['preset']}**")
        lines.append(f"- Team Role: **{stage.get('team_role') or 'n/a'}**")
        lines.append(f"- Character ID: **{stage.get('character_id') or 'n/a'}**")
        lines.append(f"- Mode Overall: **{stage.get('mode_overall') or 'n/a'}**")
        lines.append(f"- Encounter Overall: **{stage.get('encounter_overall') or 'n/a'}**")
        lines.append(f"- Equipped: **{stage['equipped_count']}** | Dry Run: **{stage['dry_run_count']}** | Failed: **{stage['failed_count']}** | Unresolved: **{stage['unresolved_count']}**")
        lines.append("- Resolved Items:")
        for item in stage.get("resolved_items", []):
            lines.append(
                f"  - {item.get('slot') or 'unknown'} | {item.get('name') or 'Unknown'} | resolved={item.get('resolved')} | instance={item.get('resolvedInstanceId')}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 21 multi-stage loadout planning")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--auth-dir", default="auth")
    parser.add_argument("--plan", required=False, choices=sorted(MULTISTAGE_PLANS.keys()))
    parser.add_argument("--list-plans", action="store_true")
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--character-id", required=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = ensure_output_dir(args.output_dir)
    if args.list_plans:
        payload = {"plans": MULTISTAGE_PLANS, "encounter_library_keys": sorted(ENCOUNTER_LIBRARY.keys())}
        write_json(output_dir / "phase210_multistage.json", payload)
        lines = ["# Warmind Multi-Stage Plans", ""]
        for key, plan in MULTISTAGE_PLANS.items():
            lines.append(f"- **{key}**: {plan['label']} | {plan['description']}")
        write(output_dir / "Phase210 Multistage.md", "\n".join(lines))
        return

    if not args.plan:
        raise SystemExit("--plan is required unless --list-plans is used.")

    weapons = Path(args.weapons).expanduser().resolve()
    armor = Path(args.armor).expanduser().resolve()
    loadouts = Path(args.loadouts).expanduser().resolve() if args.loadouts else None
    auth_dir = Path(args.auth_dir).expanduser().resolve()
    auth_dir.mkdir(parents=True, exist_ok=True)

    plan = MULTISTAGE_PLANS[args.plan]
    stage_results: list[dict[str, Any]] = []
    raw_stage_results: list[dict[str, Any]] = []

    for stage in plan["stages"]:
        preset_key = stage["preset"]
        preset = ENCOUNTER_LIBRARY[preset_key]
        result = run_stage(
            weapons=weapons,
            armor=armor,
            loadouts=loadouts,
            output_dir=output_dir,
            auth_dir=auth_dir,
            preset=preset,
            membership_type=args.membership_type,
            membership_id=args.membership_id,
            character_id=args.character_id,
            dry_run=args.dry_run,
        )
        raw_stage_results.append(result)
        stage_results.append(stage_summary(stage["name"], stage["purpose"], preset_key, result))

    payload = {
        "selected_plan": args.plan,
        "plan": plan,
        "stage_results": stage_results,
        "raw_stage_results": raw_stage_results,
        "dry_run": args.dry_run,
    }
    write_json(output_dir / "phase210_multistage.json", payload)
    write(output_dir / "Phase210 Multistage.md", render_md(args.plan, plan, stage_results))


if __name__ == "__main__":
    main()
