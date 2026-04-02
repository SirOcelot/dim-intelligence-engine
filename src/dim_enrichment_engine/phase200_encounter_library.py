from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dim_enrichment_engine.phase185_hardening import ensure_output_dir
from dim_enrichment_engine.phase191_live_swap import main as live_swap_main

ENCOUNTER_LIBRARY: dict[str, dict[str, Any]] = {
    "gm_boss_room": {
        "label": "GM Boss Room",
        "activity": "gm",
        "mode": "safe",
        "encounter": "boss",
        "range": "long",
        "damage": "sustained",
        "team_roles": ["dps", "dps"],
        "team_champions": ["barrier"],
        "champions": ["barrier", "overload"],
        "summary": "Long-range GM boss room with sustained pressure and champion risk.",
        "why": [
            "Biases toward safe damage, champion coverage, and survivability.",
            "Assumes the fireteam usually over-indexes into damage and needs cleaner control.",
        ],
    },
    "gm_corridor": {
        "label": "GM Corridor",
        "activity": "gm",
        "mode": "safe",
        "encounter": "mixed",
        "range": "long",
        "damage": "sustained",
        "team_roles": ["dps", "support"],
        "team_champions": ["barrier"],
        "champions": ["barrier", "overload"],
        "summary": "Lane-heavy GM segment with ranged danger and repeated champion checks.",
        "why": [
            "Rewards ranged safety, ammo stability, and anti-champion uptime.",
            "Penalizes greedy close-range options that feel good on paper but fail in practice.",
        ],
    },
    "raid_boss_burst": {
        "label": "Raid Boss Burst",
        "activity": "raid",
        "mode": "aggressive",
        "encounter": "boss",
        "range": "mid",
        "damage": "burst",
        "team_roles": ["support", "dps"],
        "team_champions": [],
        "champions": [],
        "summary": "Short damage-window raid boss where burst ceiling matters more than comfort.",
        "why": [
            "Biases toward burst tools, boss damage, and cleaner weapon-weighted stat targets.",
            "Assumes survivability floor is handled by encounter knowledge and team support.",
        ],
    },
    "raid_boss_sustained": {
        "label": "Raid Boss Sustained",
        "activity": "raid",
        "mode": "aggressive",
        "encounter": "boss",
        "range": "mid",
        "damage": "sustained",
        "team_roles": ["support", "dps"],
        "team_champions": [],
        "champions": [],
        "summary": "Long raid damage window where stable sustained output beats over-rotating.",
        "why": [
            "Rewards uptime and ammo planning over burst-only spikes.",
            "Useful when the fireteam is already covered on support and debuffs.",
        ],
    },
    "raid_ad_clear": {
        "label": "Raid Add Clear",
        "activity": "raid",
        "mode": "comfort",
        "encounter": "add-clear",
        "range": "mid",
        "damage": "mixed",
        "team_roles": ["support", "dps"],
        "team_champions": [],
        "champions": [],
        "summary": "Raid add-clear segment with movement, mechanic load, and moderate threat.",
        "why": [
            "Biases toward lower-friction execution and reliable ad control.",
            "Useful when the player is juggling mechanics rather than free-firing damage.",
        ],
    },
    "solo_dungeon_boss": {
        "label": "Solo Dungeon Boss",
        "activity": "dungeon",
        "mode": "comfort",
        "encounter": "boss",
        "range": "mid",
        "damage": "sustained",
        "team_roles": ["survivability"],
        "team_champions": [],
        "champions": [],
        "summary": "Solo dungeon boss with repeated sustain checks and low tolerance for mistakes.",
        "why": [
            "Biases toward self-heal, DR loops, and stable damage over greed.",
            "Treats execution consistency as more important than spreadsheet peaks.",
        ],
    },
    "solo_dungeon_traversal": {
        "label": "Solo Dungeon Traversal",
        "activity": "dungeon",
        "mode": "comfort",
        "encounter": "mixed",
        "range": "mid",
        "damage": "mixed",
        "team_roles": ["survivability"],
        "team_champions": [],
        "champions": [],
        "summary": "Solo dungeon transition segment with mixed threats and no team bailout.",
        "why": [
            "Rewards survivability loops, comfort, and ammo-efficient generalist tools.",
            "Useful for stabilizing between boss phases without retooling manually.",
        ],
    },
    "seasonal_speedfarm": {
        "label": "Seasonal Speed Farm",
        "activity": "seasonal",
        "mode": "economy",
        "encounter": "mixed",
        "range": "mid",
        "damage": "mixed",
        "team_roles": ["dps"],
        "team_champions": [],
        "champions": [],
        "summary": "Fast seasonal farming where low friction and ammo stability matter most.",
        "why": [
            "Biases toward efficient loop builds rather than over-specialized boss setups.",
            "Intended for fast repetition and reduced downtime.",
        ],
    },
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_live_swap_with_preset(
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
) -> None:
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

    old_argv = sys.argv[:]
    try:
        sys.argv = argv
        live_swap_main()
    finally:
        sys.argv = old_argv


def render_library_md(selected_key: str, preset: dict[str, Any], result_payload: dict[str, Any]) -> str:
    lines = [
        "# Warmind Encounter Library",
        "",
        f"- Selected Preset: **{selected_key}**",
        f"- Label: **{preset['label']}**",
        f"- Summary: **{preset['summary']}**",
        f"- Activity: **{preset['activity']}**",
        f"- Mode: **{preset['mode']}**",
        f"- Encounter: **{preset['encounter']}**",
        f"- Range: **{preset['range']}**",
        f"- Damage Window: **{preset['damage']}**",
        f"- Team Roles: **{', '.join(preset.get('team_roles', [])) or 'none'}**",
        f"- Team Champions: **{', '.join(preset.get('team_champions', [])) or 'none'}**",
        f"- Encounter Champions: **{', '.join(preset.get('champions', [])) or 'none'}**",
        "",
        "## Why This Preset Exists",
    ]
    for reason in preset.get("why", []):
        lines.append(f"- {reason}")

    equip_result = result_payload.get("equip_result", {})
    lines.extend([
        "",
        "## Live Swap Outcome",
        f"- Equipped: **{equip_result.get('equipped_count', 0)}**",
        f"- Dry Run: **{equip_result.get('dry_run_count', 0)}**",
        f"- Failed: **{equip_result.get('failed_count', 0)}**",
        f"- Unresolved: **{equip_result.get('unresolved_count', 0)}**",
        "",
        "## Output Files",
        "- phase191_live_swap_plan.json",
        "- phase191_live_swap_result.json",
        "- Phase191 Live Swap.md",
        "- Phase191 Live Swap Equip.md",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 20 encounter library")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--auth-dir", default="auth")
    parser.add_argument("--preset", required=False, choices=sorted(ENCOUNTER_LIBRARY.keys()))
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--character-id", required=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = ensure_output_dir(args.output_dir)
    if args.list_presets:
        payload = {"presets": ENCOUNTER_LIBRARY}
        write_json(output_dir / "phase200_encounter_library.json", payload)
        lines = ["# Warmind Encounter Library Presets", ""]
        for key, preset in ENCOUNTER_LIBRARY.items():
            lines.append(f"- **{key}**: {preset['label']} | {preset['summary']}")
        write(output_dir / "Phase200 Encounter Library.md", "\n".join(lines))
        return

    if not args.preset:
        raise SystemExit("--preset is required unless --list-presets is used.")

    preset = ENCOUNTER_LIBRARY[args.preset]
    weapons = Path(args.weapons).expanduser().resolve()
    armor = Path(args.armor).expanduser().resolve()
    loadouts = Path(args.loadouts).expanduser().resolve() if args.loadouts else None
    auth_dir = Path(args.auth_dir).expanduser().resolve()
    auth_dir.mkdir(parents=True, exist_ok=True)

    run_live_swap_with_preset(
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

    result_payload = json.loads((output_dir / "phase191_live_swap_result.json").read_text(encoding="utf-8"))
    library_payload = {
        "selected_preset": args.preset,
        "preset": preset,
        "result": result_payload,
    }
    write_json(output_dir / "phase200_encounter_library.json", library_payload)
    write(output_dir / "Phase200 Encounter Library.md", render_library_md(args.preset, preset, result_payload))


if __name__ == "__main__":
    main()
