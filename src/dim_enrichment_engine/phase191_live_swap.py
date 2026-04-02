from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dim_enrichment_engine.phase185_hardening import ensure_output_dir
from dim_enrichment_engine.phase190_dim_live import (
    BungieLiveClient,
    BungieLiveEquipError,
    LiveEquipConfig,
    build_inventory_index,
    choose_character_id,
    equip_full_build,
    extract_planned_items,
    fetch_live_profile,
    load_config,
    pick_best_payload,
    render_md as render_live_md,
    resolve_item_instances,
    resolve_membership,
    write,
    write_json,
)

ACTIVITY_TO_MODE = {
    "gm": "safe",
    "raid": "aggressive",
    "dungeon": "comfort",
    "seasonal": "economy",
}

ACTIVITY_TO_TEAM_ROLE_HINTS = {
    "gm": {"roles": ["dps", "dps"], "champions": []},
    "raid": {"roles": ["support", "dps"], "champions": []},
    "dungeon": {"roles": ["survivability"], "champions": []},
    "seasonal": {"roles": ["dps"], "champions": []},
}

ACTIVITY_TO_ENCOUNTER_DEFAULTS = {
    "gm": {"encounter": "mixed", "range": "long", "damage": "sustained"},
    "raid": {"encounter": "boss", "range": "mid", "damage": "burst"},
    "dungeon": {"encounter": "mixed", "range": "mid", "damage": "sustained"},
    "seasonal": {"encounter": "mixed", "range": "mid", "damage": "mixed"},
}

WORKFLOW_PRIORITY = [
    ("team", "phase150_team.json"),
    ("encounter", "phase160_encounter.json"),
    ("feedback", "phase133_feedback.json"),
    ("modes", "phase132_modes.json"),
    ("adaptive", "phase131_adaptive.json"),
    ("refinement", "phase115_refinement.json"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_mode_phase(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path, mode: str) -> dict[str, Any]:
    from dim_enrichment_engine.phase132_modes import main as mode_main
    import sys

    argv = [
        "phase132_modes",
        "--weapons", str(weapons),
        "--armor", str(armor),
        "--output-dir", str(output_dir),
        "--mode", mode,
    ]
    if loadouts:
        argv.extend(["--loadouts", str(loadouts)])
    old = sys.argv[:]
    try:
        sys.argv = argv
        mode_main()
    finally:
        sys.argv = old
    return read_json(output_dir / "phase132_modes.json")


def run_team_phase(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path, team_roles: list[str], team_champions: list[str]) -> dict[str, Any]:
    from dim_enrichment_engine.phase150_team import main as team_main
    import sys

    argv = [
        "phase150_team",
        "--weapons", str(weapons),
        "--armor", str(armor),
        "--output-dir", str(output_dir),
        "--team-roles", ",".join(team_roles),
        "--team-champions", ",".join(team_champions),
    ]
    if loadouts:
        argv.extend(["--loadouts", str(loadouts)])
    old = sys.argv[:]
    try:
        sys.argv = argv
        team_main()
    finally:
        sys.argv = old
    return read_json(output_dir / "phase150_team.json")


def run_encounter_phase(
    weapons: Path,
    armor: Path,
    loadouts: Path | None,
    output_dir: Path,
    activity: str,
    encounter: str,
    range_band: str,
    damage: str,
    champions: list[str],
) -> dict[str, Any]:
    from dim_enrichment_engine.phase160_encounter import main as encounter_main
    import sys

    argv = [
        "phase160_encounter",
        "--weapons", str(weapons),
        "--armor", str(armor),
        "--output-dir", str(output_dir),
        "--activity", activity,
        "--encounter", encounter,
        "--range", range_band,
        "--damage", damage,
        "--champions", ",".join(champions),
    ]
    if loadouts:
        argv.extend(["--loadouts", str(loadouts)])
    old = sys.argv[:]
    try:
        sys.argv = argv
        encounter_main()
    finally:
        sys.argv = old
    return read_json(output_dir / "phase160_encounter.json")


def run_refinement_phase(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path) -> dict[str, Any]:
    from dim_enrichment_engine.phase115_refinement import main as refinement_main
    import sys

    argv = [
        "phase115_refinement",
        "--weapons", str(weapons),
        "--armor", str(armor),
        "--output-dir", str(output_dir),
    ]
    if loadouts:
        argv.extend(["--loadouts", str(loadouts)])
    old = sys.argv[:]
    try:
        sys.argv = argv
        refinement_main()
    finally:
        sys.argv = old
    return read_json(output_dir / "phase115_refinement.json")


def choose_context(output_dir: Path) -> tuple[str, dict[str, Any]]:
    for label, filename in WORKFLOW_PRIORITY:
        path = output_dir / filename
        if path.exists():
            return label, read_json(path)
    raise BungieLiveEquipError("No generated context payload was found after live swap pipeline execution.")


def build_swap_summary(
    activity: str,
    mode: str,
    payload_source: str,
    character_id: str,
    resolved_items: list[dict[str, Any]],
    equip_result: dict[str, Any],
    team_payload: dict[str, Any] | None,
    encounter_payload: dict[str, Any] | None,
    mode_payload: dict[str, Any] | None,
) -> str:
    lines = [
        "# Warmind Activity-Aware Live Swap",
        "",
        f"- Activity: **{activity}**",
        f"- Mode: **{mode}**",
        f"- Context Source Used For Equip: **{payload_source}**",
        f"- Character ID: **{character_id}**",
        "",
        "## Pipeline Outputs",
    ]
    if mode_payload:
        lines.append(f"- Mode overall score: **{mode_payload.get('after_scores', {}).get('overall', 'n/a')}**")
    if encounter_payload:
        lines.append(f"- Encounter overall score: **{encounter_payload.get('after_scores', {}).get('overall', 'n/a')}**")
        champs = encounter_payload.get('encounter_context', {}).get('champions', [])
        lines.append(f"- Encounter champions: **{', '.join(champs) if champs else 'none'}**")
    if team_payload:
        lines.append(f"- Recommended team role: **{team_payload.get('team_context', {}).get('recommended_role', 'n/a')}**")
        missing = team_payload.get('team_context', {}).get('missing_champions', [])
        lines.append(f"- Missing team champs before your swap: **{', '.join(missing) if missing else 'none'}**")

    lines.extend(["", "## Resolved Equip Plan"])
    for item in resolved_items:
        lines.append(
            f"- **{item.get('slot') or 'unknown'}**: {item.get('name') or 'Unknown'} | resolved={item.get('resolved')} | instance={item.get('resolvedInstanceId')}"
        )

    lines.extend([
        "",
        "## Equip Result",
        f"- Equipped: **{equip_result.get('equipped_count', 0)}**",
        f"- Dry Run: **{equip_result.get('dry_run_count', 0)}**",
        f"- Failed: **{equip_result.get('failed_count', 0)}**",
        f"- Unresolved: **{equip_result.get('unresolved_count', 0)}**",
    ])
    for result in equip_result.get("results", []):
        lines.append(
            f"- {result.get('slot') or 'unknown'} | {result.get('name') or 'Unknown'} | status={result.get('status')} | message={result.get('message', '')}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 19B activity-aware live swap engine")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--auth-dir", default="auth")
    parser.add_argument("--activity", required=True, choices=["gm", "raid", "dungeon", "seasonal"])
    parser.add_argument("--mode", required=False, choices=["safe", "aggressive", "comfort", "anti-champion", "economy"])
    parser.add_argument("--team-roles", default="")
    parser.add_argument("--team-champions", default="")
    parser.add_argument("--encounter", choices=["boss", "add-clear", "mixed"], required=False)
    parser.add_argument("--range", dest="range_band", choices=["close", "mid", "long"], required=False)
    parser.add_argument("--damage", dest="damage_window", choices=["burst", "sustained", "mixed"], required=False)
    parser.add_argument("--champions", default="")
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--character-id", required=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    weapons = Path(args.weapons).expanduser().resolve()
    armor = Path(args.armor).expanduser().resolve()
    loadouts = Path(args.loadouts).expanduser().resolve() if args.loadouts else None
    output_dir = ensure_output_dir(args.output_dir)
    auth_dir = Path(args.auth_dir).expanduser().resolve()
    auth_dir.mkdir(parents=True, exist_ok=True)

    mode = args.mode or ACTIVITY_TO_MODE[args.activity]
    default_encounter = ACTIVITY_TO_ENCOUNTER_DEFAULTS[args.activity]
    encounter = args.encounter or default_encounter["encounter"]
    range_band = args.range_band or default_encounter["range"]
    damage_window = args.damage_window or default_encounter["damage"]

    explicit_team_roles = [x.strip() for x in args.team_roles.split(",") if x.strip()]
    explicit_team_champions = [x.strip() for x in args.team_champions.split(",") if x.strip()]
    if not explicit_team_roles:
        explicit_team_roles = ACTIVITY_TO_TEAM_ROLE_HINTS[args.activity]["roles"][:]
    if not explicit_team_champions:
        explicit_team_champions = ACTIVITY_TO_TEAM_ROLE_HINTS[args.activity]["champions"][:]

    encounter_champions = [x.strip() for x in args.champions.split(",") if x.strip()]
    team_payload = run_team_phase(weapons, armor, loadouts, output_dir, explicit_team_roles, explicit_team_champions)
    if not encounter_champions:
        encounter_champions = team_payload.get("team_context", {}).get("missing_champions", [])

    mode_payload = run_mode_phase(weapons, armor, loadouts, output_dir, mode)
    encounter_payload = run_encounter_phase(
        weapons,
        armor,
        loadouts,
        output_dir,
        args.activity,
        encounter,
        range_band,
        damage_window,
        encounter_champions,
    )
    refinement_payload = run_refinement_phase(weapons, armor, loadouts, output_dir)

    config = load_config(auth_dir, args.membership_type, args.membership_id, args.character_id)
    client = BungieLiveClient(config)
    membership_type, membership_id = resolve_membership(client, config)
    live_profile = fetch_live_profile(client, membership_type, membership_id)

    payload_source, payload = pick_best_payload(output_dir)
    planned_items = extract_planned_items(payload_source, payload)
    character_id = choose_character_id(live_profile, config.character_id, planned_items)
    inventory_index = build_inventory_index(live_profile, character_id)
    resolved_items = resolve_item_instances(planned_items, inventory_index)
    equip_result = equip_full_build(client, membership_type, character_id, resolved_items, dry_run=args.dry_run)

    swap_plan = {
        "activity": args.activity,
        "mode": mode,
        "encounter": encounter,
        "range": range_band,
        "damage_window": damage_window,
        "team_roles": explicit_team_roles,
        "team_champions": explicit_team_champions,
        "encounter_champions": encounter_champions,
        "payload_source": payload_source,
        "membership_type": membership_type,
        "membership_id": membership_id,
        "character_id": character_id,
        "dry_run": args.dry_run,
        "resolved_items": resolved_items,
        "mode_payload": mode_payload,
        "team_payload": team_payload,
        "encounter_payload": encounter_payload,
        "refinement_payload": refinement_payload,
    }
    result_payload = {
        **swap_plan,
        "equip_result": equip_result,
    }

    write_json(output_dir / "phase191_live_swap_plan.json", swap_plan)
    write_json(output_dir / "phase191_live_swap_result.json", result_payload)
    write(
        output_dir / "Phase191 Live Swap.md",
        build_swap_summary(
            args.activity,
            mode,
            payload_source,
            character_id,
            resolved_items,
            equip_result,
            team_payload,
            encounter_payload,
            mode_payload,
        ),
    )
    write(
        output_dir / "Phase191 Live Swap Equip.md",
        render_live_md(payload_source, character_id, membership_type, membership_id, args.dry_run, resolved_items, equip_result),
    )


if __name__ == "__main__":
    main()
