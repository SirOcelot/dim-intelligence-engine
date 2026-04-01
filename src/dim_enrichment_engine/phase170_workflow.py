from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pick_best_context(output_dir: Path) -> tuple[str, dict[str, Any]]:
    candidates = [
        ("team", output_dir / "phase150_team.json"),
        ("encounter", output_dir / "phase160_encounter.json"),
        ("feedback", output_dir / "phase133_feedback.json"),
        ("modes", output_dir / "phase132_modes.json"),
        ("adaptive", output_dir / "phase131_adaptive.json"),
        ("refinement", output_dir / "phase115_refinement.json"),
        ("selection", output_dir / "item_selection.json"),
        ("dim_bridge", output_dir / "phase101_dim_payload.json"),
    ]
    for label, path in candidates:
        payload = load_json_if_exists(path)
        if payload is not None:
            return label, payload
    raise SystemExit("No prior Warmind outputs found in output directory. Run earlier phases first.")


def extract_build(payload_type: str, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if payload_type == "team":
        return payload["after_build"], payload.get("reasons", [])
    if payload_type == "encounter":
        return payload["after_build"], payload.get("reasons", [])
    if payload_type == "feedback":
        return payload["after_build"], payload.get("reasons", [])
    if payload_type == "modes":
        return payload["after_build"], payload.get("reasons", [])
    if payload_type == "adaptive":
        return payload["after_build"], payload.get("reasons", [])
    if payload_type == "refinement":
        shell = payload.get("recommended_shell", {})
        selected = payload.get("selected_best_copies", {})
        build = {
            "kinetic": selected.get("kinetic", {}).get("name", shell.get("kinetic")),
            "energy": selected.get("energy", {}).get("name", shell.get("energy")),
            "power": selected.get("power", {}).get("name", shell.get("power")),
            "armor_exotic": selected.get("legs", {}).get("name", shell.get("armor_exotic")),
            "subclass": shell.get("subclass", "Nightstalker"),
        }
        return build, ["Derived from refinement-selected best copies."]
    if payload_type == "selection":
        shell = payload.get("recommended_shell", {})
        selected = payload.get("selected_best_copies", {})
        build = {
            "kinetic": selected.get("kinetic", {}).get("name", shell.get("kinetic")),
            "energy": selected.get("energy", {}).get("name", shell.get("energy")),
            "power": selected.get("power", {}).get("name", shell.get("power")),
            "armor_exotic": selected.get("legs", {}).get("name", shell.get("armor_exotic")),
            "subclass": shell.get("subclass", "Nightstalker"),
        }
        return build, ["Derived from item selection engine."]
    if payload_type == "dim_bridge":
        items = payload.get("items", [])
        build = {"kinetic": "Unknown", "energy": "Unknown", "power": "Unknown", "armor_exotic": "Unknown", "subclass": payload.get("subclass", "Nightstalker")}
        for item in items:
            bucket = str(item.get("bucket", "")).lower()
            if bucket == "kinetic":
                build["kinetic"] = item.get("name", "Unknown")
            elif bucket == "energy":
                build["energy"] = item.get("name", "Unknown")
            elif bucket == "power":
                build["power"] = item.get("name", "Unknown")
            elif bucket in {"legs", "leg"}:
                build["armor_exotic"] = item.get("name", "Unknown")
        return build, ["Derived from DIM bridge payload."]
    raise SystemExit(f"Unsupported payload type: {payload_type}")


def extract_selected_items(payload_type: str, payload: dict[str, Any], build: dict[str, Any]) -> list[dict[str, Any]]:
    if payload_type in {"refinement", "selection"}:
        selected = payload.get("selected_best_copies", {})
        return [
            {"slot": "kinetic", **selected.get("kinetic", {})},
            {"slot": "energy", **selected.get("energy", {})},
            {"slot": "power", **selected.get("power", {})},
            {"slot": "legs", **selected.get("legs", {})},
        ]
    if payload_type == "dim_bridge":
        return [{"slot": item.get("bucket"), "name": item.get("name"), "itemInstanceId": item.get("id"), "itemHash": item.get("hash")} for item in payload.get("items", [])]
    return [
        {"slot": "kinetic", "name": build.get("kinetic")},
        {"slot": "energy", "name": build.get("energy")},
        {"slot": "power", "name": build.get("power")},
        {"slot": "legs", "name": build.get("armor_exotic")},
    ]


def build_dim_payload(build: dict[str, Any], selected_items: list[dict[str, Any]], source_type: str) -> dict[str, Any]:
    return {
        "app": "Warmind",
        "name": f"Warmind {source_type.title()} Loadout",
        "class": "Hunter",
        "subclass": build.get("subclass", "Nightstalker"),
        "items": [
            {
                "bucket": item.get("slot"),
                "name": item.get("name"),
                "id": item.get("instance_id") or item.get("itemInstanceId"),
                "hash": item.get("hash") or item.get("itemHash"),
                "equip": True,
            }
            for item in selected_items
        ],
        "notes": [
            "Warmind Phase 17 workflow integration",
            f"Source pipeline: {source_type}",
            "Use as DIM import payload or execution handoff.",
        ],
    }


def build_dim_url(dim_payload: dict[str, Any]) -> str:
    compact = json.dumps(dim_payload, separators=(",", ":"))
    return "https://app.destinyitemmanager.com/#/loadouts?payload=" + quote(compact, safe="")


def build_cli_command(output_dir: Path, workflow_mode: str) -> str:
    base = f'python -m dim_enrichment_engine.phase120_execute --output-dir "{output_dir}"'
    if workflow_mode == "preview":
        return base
    if workflow_mode == "direct":
        return base + " --direct-equip --confirm"
    return base


def build_workflow_steps(source_type: str, workflow_mode: str, output_dir: Path) -> list[str]:
    steps = [
        f"Warmind selected the latest build context from phase '{source_type}'.",
        "Warmind generated a DIM-ready payload and handoff URL.",
        "Warmind prepared an execution handoff path into Phase 12.",
    ]
    if workflow_mode == "preview":
        steps.append("Workflow mode is preview, so direct equip is not requested.")
    else:
        steps.append("Workflow mode is direct, so the next recommended action is Phase 12 direct equip with confirmation.")
    steps.append(f"Execution command: {build_cli_command(output_dir, workflow_mode)}")
    return steps


def render_md(source_type: str, build: dict[str, Any], selected_items: list[dict[str, Any]], dim_url: str, workflow_mode: str, reasons: list[str], steps: list[str]) -> str:
    lines = [
        "# Warmind Workflow Integration",
        "",
        f"- Source Context: **{source_type}**",
        f"- Workflow Mode: **{workflow_mode}**",
        f"- Kinetic: **{build.get('kinetic', 'Unknown')}**",
        f"- Energy: **{build.get('energy', 'Unknown')}**",
        f"- Power: **{build.get('power', 'Unknown')}**",
        f"- Exotic Armor: **{build.get('armor_exotic', 'Unknown')}**",
        f"- Subclass: **{build.get('subclass', 'Nightstalker')}**",
        "",
        "## Workflow Handoff Items",
    ]
    for item in selected_items:
        lines.append(
            f"- **{item.get('slot', 'unknown')}**: {item.get('name')} | instanceId: {item.get('instance_id') or item.get('itemInstanceId')} | hash: {item.get('hash') or item.get('itemHash')}"
        )
    lines.extend([
        "",
        "## DIM Workflow",
        f"- DIM URL scaffold: `{dim_url}`",
        "",
        "## Why This Workflow Exists",
    ])
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.extend(["", "## Next Steps"])
    for step in steps:
        lines.append(f"- {step}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 17 workflow integration")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--workflow-mode", choices=["preview", "direct"], default="preview")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    source_type, payload = pick_best_context(output_dir)
    build, reasons = extract_build(source_type, payload)
    selected_items = extract_selected_items(source_type, payload, build)
    dim_payload = build_dim_payload(build, selected_items, source_type)
    dim_url = build_dim_url(dim_payload)
    steps = build_workflow_steps(source_type, args.workflow_mode, output_dir)

    result = {
        "source_type": source_type,
        "workflow_mode": args.workflow_mode,
        "build": build,
        "selected_items": selected_items,
        "dim_payload": dim_payload,
        "dim_url": dim_url,
        "steps": steps,
        "reasons": reasons,
    }

    (output_dir / "phase170_workflow.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (output_dir / "phase170_dim_payload.json").write_text(json.dumps(dim_payload, indent=2), encoding="utf-8")
    write(output_dir / "Phase170 Workflow.md", render_md(source_type, build, selected_items, dim_url, args.workflow_mode, reasons, steps))


if __name__ == "__main__":
    main()
