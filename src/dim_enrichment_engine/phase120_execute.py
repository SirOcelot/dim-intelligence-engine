from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

API_ROOT = "https://www.bungie.net/Platform"
SNAPSHOT_FILE = "phase120_snapshot.json"
DIFF_FILE = "Phase120 Diff.md"
DIM_FILE = "phase120_dim_payload.json"
EQUIP_PLAN_FILE = "phase120_equip_plan.json"
RESULT_FILE = "phase120_result.json"


class BungieApiError(RuntimeError):
    pass


class BungieWriteClient:
    def __init__(self, api_key: str, access_token: str | None = None) -> None:
        self.s = requests.Session()
        self.s.headers.update({"X-API-Key": api_key, "Content-Type": "application/json"})
        if access_token:
            self.s.headers.update({"Authorization": f"Bearer {access_token}"})

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        r = self.s.get(f"{API_ROOT}{path}", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("ErrorCode") not in (1, "1", None):
            raise BungieApiError(data.get("Message") or data.get("ErrorStatus") or "Unknown Bungie API error")
        return data

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = self.s.post(f"{API_ROOT}{path}", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("ErrorCode") not in (1, "1", None):
            raise BungieApiError(data.get("Message") or data.get("ErrorStatus") or "Unknown Bungie API error")
        return data


def load_env_file() -> None:
    for path in (Path(".env"), Path(".env.txt")):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        break


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def resolve_membership(client: BungieWriteClient, membership_type: int | None, membership_id: str | None) -> tuple[int, str, str]:
    if membership_type and membership_id:
        return membership_type, membership_id, "manual"
    payload = client.get("/User/GetMembershipsForCurrentUser/")
    memberships = payload.get("Response", {}).get("destinyMemberships") or []
    if not memberships:
        raise BungieApiError("No Destiny memberships returned for the current account.")
    primary = memberships[0]
    return int(primary["membershipType"]), str(primary["membershipId"]), "oauth"


def get_live_profile(client: BungieWriteClient, membership_type: int, membership_id: str) -> dict[str, Any]:
    return client.get(
        f"/Destiny2/{membership_type}/Profile/{membership_id}/",
        components="102,201,205,300",
    )


def collect_equipped_snapshot(profile_payload: dict[str, Any]) -> dict[str, Any]:
    response = profile_payload.get("Response", {})
    characters = response.get("characterEquipment", {}).get("data", {}) or {}
    snapshot = {"characters": {}}
    for character_id, data in characters.items():
        snapshot["characters"][character_id] = {
            "items": [
                {
                    "itemInstanceId": item.get("itemInstanceId"),
                    "itemHash": item.get("itemHash"),
                    "bucketHash": item.get("bucketHash"),
                }
                for item in data.get("items", [])
            ]
        }
    return snapshot


def load_best_copy_selection(output_dir: Path) -> dict[str, Any]:
    for filename in ["phase115_refinement.json", "item_selection.json", "phase101_dim_payload.json"]:
        path = output_dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit("No prior Warmind selection output found. Run Phase 11.5 or Phase 11 first.")


def build_execute_payload(selection_payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected = selection_payload.get("selected_best_copies") or selection_payload.get("selected_best_copies", {})
    if not selected:
        raise SystemExit("Selection payload missing selected_best_copies.")
    normalized = {}
    for slot in ["kinetic", "energy", "power", "legs"]:
        normalized[slot] = selected.get(slot, {})
    items = []
    for slot in ["kinetic", "energy", "power", "legs"]:
        item = normalized.get(slot, {})
        items.append(
            {
                "slot": slot,
                "name": item.get("name"),
                "itemInstanceId": item.get("instance_id") or item.get("itemInstanceId"),
                "itemHash": item.get("hash") or item.get("itemHash"),
                "owner": item.get("owner"),
                "score": item.get("score"),
            }
        )
    shell = selection_payload.get("recommended_shell", {})
    return shell, items


def select_character_id(profile_payload: dict[str, Any], planned_items: list[dict[str, Any]]) -> str | None:
    response = profile_payload.get("Response", {})
    char_equipment = response.get("characterEquipment", {}).get("data", {}) or {}
    char_inventory = response.get("characterInventories", {}).get("data", {}) or {}
    counts: dict[str, int] = {}
    wanted_ids = {str(x.get("itemInstanceId")) for x in planned_items if x.get("itemInstanceId")}
    for character_id, data in char_equipment.items():
        ids = {str(i.get("itemInstanceId")) for i in data.get("items", []) if i.get("itemInstanceId")}
        counts[character_id] = counts.get(character_id, 0) + len(wanted_ids & ids)
    for character_id, data in char_inventory.items():
        ids = {str(i.get("itemInstanceId")) for i in data.get("items", []) if i.get("itemInstanceId")}
        counts[character_id] = counts.get(character_id, 0) + len(wanted_ids & ids)
    if not counts:
        return None
    return max(counts, key=counts.get)


def build_dim_payload(shell: dict[str, Any], planned_items: list[dict[str, Any]], membership_type: int, membership_id: str) -> dict[str, Any]:
    payload = {
        "app": "Warmind",
        "name": "Warmind Recommended Loadout",
        "class": "Hunter",
        "subclass": shell.get("subclass", "Nightstalker"),
        "membershipType": membership_type,
        "membershipId": membership_id,
        "items": [
            {
                "id": item.get("itemInstanceId"),
                "hash": item.get("itemHash"),
                "bucket": item.get("slot"),
                "equip": True,
                "name": item.get("name"),
            }
            for item in planned_items
        ],
        "notes": ["Warmind Phase 12 DIM fallback", "Safe import path if direct equip is disabled or declined"],
    }
    return payload


def build_dim_url(payload: dict[str, Any]) -> str:
    compact = json.dumps(payload, separators=(",", ":"))
    return "https://app.destinyitemmanager.com/#/loadouts?payload=" + quote(compact, safe="")


def build_equip_plan(character_id: str | None, planned_items: list[dict[str, Any]]) -> dict[str, Any]:
    item_ids = [str(x.get("itemInstanceId")) for x in planned_items if x.get("itemInstanceId")]
    ready = bool(character_id and len(item_ids) == len(planned_items))
    return {
        "characterId": character_id,
        "itemIds": item_ids,
        "resolvedItemCount": len(item_ids),
        "totalItemCount": len(planned_items),
        "ready": ready,
    }


def render_diff(shell: dict[str, Any], planned_items: list[dict[str, Any]], equip_plan: dict[str, Any], dim_url: str) -> str:
    lines = [
        "# Phase 12 Execution Preview",
        "",
        f"- Kinetic: **{shell.get('kinetic')}**",
        f"- Energy: **{shell.get('energy')}**",
        f"- Power: **{shell.get('power')}**",
        f"- Exotic Armor: **{shell.get('armor_exotic')}**",
        f"- Subclass: **{shell.get('subclass', 'Nightstalker')}**",
        "",
        "## Planned Items",
    ]
    for item in planned_items:
        lines.append(
            f"- **{item['slot']}**: {item.get('name')} | instanceId: {item.get('itemInstanceId')} | hash: {item.get('itemHash')} | owner: {item.get('owner')} | score: {item.get('score')}"
        )
    lines.extend(
        [
            "",
            "## Execution Readiness",
            f"- Character ID: **{equip_plan.get('characterId') or 'Unknown'}**",
            f"- Resolved Items: **{equip_plan.get('resolvedItemCount')}/{equip_plan.get('totalItemCount')}**",
            f"- Ready for direct equip: **{equip_plan.get('ready')}**",
            "",
            "## DIM Fallback",
            f"- DIM URL scaffold: `{dim_url}`",
            "",
            "## Safety Gates",
            "- Direct equip only runs with --confirm and valid OAuth token.",
            "- Snapshot is taken before attempting equip.",
            "- If direct equip is not ready, use DIM fallback instead.",
        ]
    )
    return "\n".join(lines)


def save_snapshot(output_dir: Path, snapshot: dict[str, Any]) -> Path:
    path = output_dir / SNAPSHOT_FILE
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path


def execute_equip(client: BungieWriteClient, equip_plan: dict[str, Any]) -> dict[str, Any]:
    if not equip_plan.get("ready"):
        raise BungieApiError("Equip plan is not ready. Missing characterId or item instance IDs.")
    payload = {"characterId": equip_plan["characterId"], "itemIds": equip_plan["itemIds"]}
    return client.post("/Destiny2/Actions/Items/EquipItems/", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 12 execution layer")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--direct-equip", action="store_true")
    args = parser.parse_args()

    load_env_file()
    api_key = os.getenv("BUNGIE_API_KEY", "").strip()
    access_token = os.getenv("BUNGIE_ACCESS_TOKEN", "").strip() or None
    membership_type = args.membership_type or (int(os.getenv("BUNGIE_MEMBERSHIP_TYPE", "").strip()) if os.getenv("BUNGIE_MEMBERSHIP_TYPE", "").strip() else None)
    membership_id = args.membership_id or (os.getenv("BUNGIE_MEMBERSHIP_ID", "").strip() or None)

    if not api_key:
        raise SystemExit("BUNGIE_API_KEY is required.")

    output_dir = Path(args.output_dir)
    selection_payload = load_best_copy_selection(output_dir)
    shell, planned_items = build_execute_payload(selection_payload)

    client = BungieWriteClient(api_key, access_token)
    resolved_type, resolved_id, _ = resolve_membership(client, membership_type, membership_id)
    live_profile = get_live_profile(client, resolved_type, resolved_id)
    snapshot = collect_equipped_snapshot(live_profile)
    snapshot_path = save_snapshot(output_dir, snapshot)

    character_id = select_character_id(live_profile, planned_items)
    equip_plan = build_equip_plan(character_id, planned_items)
    dim_payload = build_dim_payload(shell, planned_items, resolved_type, resolved_id)
    dim_url = build_dim_url(dim_payload)
    diff_md = render_diff(shell, planned_items, equip_plan, dim_url)

    write(output_dir / DIFF_FILE, diff_md)
    (output_dir / DIM_FILE).write_text(json.dumps(dim_payload, indent=2), encoding="utf-8")
    (output_dir / EQUIP_PLAN_FILE).write_text(json.dumps(equip_plan, indent=2), encoding="utf-8")

    result: dict[str, Any] = {
        "snapshot": str(snapshot_path),
        "directEquipRequested": args.direct_equip,
        "confirmed": args.confirm,
        "equipPlan": equip_plan,
        "dimUrl": dim_url,
        "executed": False,
        "status": "preview_only",
    }

    if args.direct_equip:
        if not access_token:
            result["status"] = "direct_equip_blocked_missing_oauth"
        elif not args.confirm:
            result["status"] = "direct_equip_blocked_not_confirmed"
        elif not equip_plan.get("ready"):
            result["status"] = "direct_equip_blocked_plan_not_ready"
        else:
            api_result = execute_equip(client, equip_plan)
            result["executed"] = True
            result["status"] = "direct_equip_success"
            result["apiResult"] = api_result

    (output_dir / RESULT_FILE).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
