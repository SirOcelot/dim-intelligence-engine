from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BUNGIE_API_ROOT = "https://www.bungie.net/Platform"
DEFAULT_AUTH_DIR = "auth"
DEFAULT_SESSION_FILE = "session.json"
DEFAULT_RESULT_FILE = "phase190_live_equip.json"
DEFAULT_PLAN_FILE = "phase190_live_plan.json"

SLOT_ALIASES = {
    "kinetic": {"kinetic", "kinetic weapons", "primary"},
    "energy": {"energy", "energy weapons", "special"},
    "power": {"power", "power weapons", "heavy"},
    "legs": {"legs", "leg", "leg armor"},
    "armor_exotic": {"legs", "leg", "leg armor"},
}


class BungieLiveEquipError(RuntimeError):
    pass


@dataclass
class LiveEquipConfig:
    api_key: str
    access_token: str
    membership_type: int | None = None
    membership_id: str | None = None
    character_id: str | None = None


class BungieLiveClient:
    def __init__(self, config: LiveEquipConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": config.api_key,
                "Authorization": f"Bearer {config.access_token}",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(f"{BUNGIE_API_ROOT}{path}", params=params, timeout=45)
        response.raise_for_status()
        payload = response.json()
        self._raise_on_bungie_error(payload)
        return payload

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{BUNGIE_API_ROOT}{path}", json=payload, timeout=45)
        response.raise_for_status()
        result = response.json()
        self._raise_on_bungie_error(result)
        return result

    @staticmethod
    def _raise_on_bungie_error(payload: dict[str, Any]) -> None:
        error_code = payload.get("ErrorCode")
        if error_code in (None, 1, "1"):
            return
        raise BungieLiveEquipError(payload.get("Message") or payload.get("ErrorStatus") or "Unknown Bungie API error")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BungieLiveEquipError(f"Missing required JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BungieLiveEquipError(f"Invalid JSON in {path}: {exc}") from exc


def norm(value: Any) -> str:
    return str(value).strip()


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


def load_session(session_path: Path) -> dict[str, Any]:
    if not session_path.exists():
        return {}
    return read_json(session_path)


def load_config(auth_dir: Path, membership_type: int | None, membership_id: str | None, character_id: str | None) -> LiveEquipConfig:
    load_env_file()
    session_path = auth_dir / DEFAULT_SESSION_FILE
    session = load_session(session_path)

    api_key = os.getenv("BUNGIE_API_KEY", "").strip() or norm(session.get("api_key"))
    access_token = os.getenv("BUNGIE_ACCESS_TOKEN", "").strip() or norm(session.get("access_token"))
    if not api_key:
        raise BungieLiveEquipError("BUNGIE_API_KEY is required. Put it in environment or auth/session.json.")
    if not access_token:
        raise BungieLiveEquipError("BUNGIE_ACCESS_TOKEN is required. Put it in environment or auth/session.json.")

    resolved_membership_type = membership_type
    if resolved_membership_type is None:
        raw = os.getenv("BUNGIE_MEMBERSHIP_TYPE", "").strip() or norm(session.get("membershipType"))
        resolved_membership_type = int(raw) if raw else None

    resolved_membership_id = membership_id or os.getenv("BUNGIE_MEMBERSHIP_ID", "").strip() or norm(session.get("membershipId")) or None
    resolved_character_id = character_id or os.getenv("BUNGIE_CHARACTER_ID", "").strip() or norm(session.get("characterId")) or None

    return LiveEquipConfig(
        api_key=api_key,
        access_token=access_token,
        membership_type=resolved_membership_type,
        membership_id=resolved_membership_id,
        character_id=resolved_character_id,
    )


def resolve_membership(client: BungieLiveClient, config: LiveEquipConfig) -> tuple[int, str]:
    if config.membership_type is not None and config.membership_id:
        return config.membership_type, config.membership_id
    payload = client.get("/User/GetMembershipsForCurrentUser/")
    memberships = payload.get("Response", {}).get("destinyMemberships") or []
    if not memberships:
        raise BungieLiveEquipError("No Destiny memberships returned for the authenticated account.")
    primary = memberships[0]
    return int(primary["membershipType"]), str(primary["membershipId"])


def fetch_live_profile(client: BungieLiveClient, membership_type: int, membership_id: str) -> dict[str, Any]:
    return client.get(
        f"/Destiny2/{membership_type}/Profile/{membership_id}/",
        components="102,201,205,300,302,304,305",
    )


def choose_character_id(profile_payload: dict[str, Any], explicit_character_id: str | None, planned_items: list[dict[str, Any]]) -> str:
    if explicit_character_id:
        return explicit_character_id

    response = profile_payload.get("Response", {})
    char_equipment = response.get("characterEquipment", {}).get("data", {}) or {}
    char_inventory = response.get("characterInventories", {}).get("data", {}) or {}
    wanted_ids = {norm(x.get("itemInstanceId")) for x in planned_items if norm(x.get("itemInstanceId"))}
    if not wanted_ids:
        raise BungieLiveEquipError("No item instance IDs available to determine character. Run refinement or workflow first.")

    counts: dict[str, int] = {}
    for character_id, payload in char_equipment.items():
        equipped_ids = {norm(item.get("itemInstanceId")) for item in payload.get("items", []) if norm(item.get("itemInstanceId"))}
        counts[character_id] = counts.get(character_id, 0) + len(wanted_ids & equipped_ids)
    for character_id, payload in char_inventory.items():
        inv_ids = {norm(item.get("itemInstanceId")) for item in payload.get("items", []) if norm(item.get("itemInstanceId"))}
        counts[character_id] = counts.get(character_id, 0) + len(wanted_ids & inv_ids)
    if not counts:
        raise BungieLiveEquipError("Could not infer character ID from live profile.")
    return max(counts, key=counts.get)


def pick_best_payload(output_dir: Path) -> tuple[str, dict[str, Any]]:
    candidates = [
        ("workflow", output_dir / "phase170_workflow.json"),
        ("execute", output_dir / "phase120_equip_plan.json"),
        ("refinement", output_dir / "phase115_refinement.json"),
        ("selection", output_dir / "item_selection.json"),
        ("dim_bridge", output_dir / "phase101_dim_payload.json"),
    ]
    for label, path in candidates:
        if path.exists():
            return label, read_json(path)
    raise BungieLiveEquipError("No compatible Warmind payload found in output directory.")


def extract_planned_items(payload_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload_type == "workflow":
        items = payload.get("selected_items") or payload.get("dim_payload", {}).get("items") or []
        extracted = []
        for item in items:
            extracted.append(
                {
                    "slot": norm(item.get("slot") or item.get("bucket")),
                    "name": item.get("name"),
                    "itemInstanceId": item.get("instance_id") or item.get("itemInstanceId") or item.get("id"),
                    "itemHash": item.get("hash") or item.get("itemHash"),
                }
            )
        return extracted

    if payload_type == "execute":
        item_ids = payload.get("itemIds", [])
        return [{"slot": "unknown", "name": None, "itemInstanceId": x, "itemHash": None} for x in item_ids]

    if payload_type in {"refinement", "selection"}:
        selected = payload.get("selected_best_copies", {})
        return [
            {"slot": "kinetic", "name": selected.get("kinetic", {}).get("name"), "itemInstanceId": selected.get("kinetic", {}).get("instance_id"), "itemHash": selected.get("kinetic", {}).get("hash")},
            {"slot": "energy", "name": selected.get("energy", {}).get("name"), "itemInstanceId": selected.get("energy", {}).get("instance_id"), "itemHash": selected.get("energy", {}).get("hash")},
            {"slot": "power", "name": selected.get("power", {}).get("name"), "itemInstanceId": selected.get("power", {}).get("instance_id"), "itemHash": selected.get("power", {}).get("hash")},
            {"slot": "legs", "name": selected.get("legs", {}).get("name"), "itemInstanceId": selected.get("legs", {}).get("instance_id"), "itemHash": selected.get("legs", {}).get("hash")},
        ]

    if payload_type == "dim_bridge":
        return [
            {
                "slot": norm(item.get("bucket")),
                "name": item.get("name"),
                "itemInstanceId": item.get("id"),
                "itemHash": item.get("hash"),
            }
            for item in payload.get("items", [])
        ]

    raise BungieLiveEquipError(f"Unsupported payload type: {payload_type}")


def slot_matches(target_slot: str, bucket_name: str) -> bool:
    slot_key = norm(target_slot).lower()
    bucket_key = norm(bucket_name).lower()
    aliases = SLOT_ALIASES.get(slot_key, {slot_key})
    return bucket_key in aliases or any(alias in bucket_key for alias in aliases)


def build_inventory_index(profile_payload: dict[str, Any], character_id: str) -> list[dict[str, Any]]:
    response = profile_payload.get("Response", {})
    item_components = response.get("itemComponents", {}) or {}
    instances = item_components.get("instances", {}).get("data", {}) or {}

    inventory_sources = []
    char_equipment = response.get("characterEquipment", {}).get("data", {}).get(character_id, {}) or {}
    char_inventory = response.get("characterInventories", {}).get("data", {}).get(character_id, {}) or {}
    inventory_sources.extend(char_equipment.get("items", []))
    inventory_sources.extend(char_inventory.get("items", []))
    inventory_sources.extend((response.get("profileInventory", {}).get("data", {}) or {}).get("items", []))

    indexed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in inventory_sources:
        item_instance_id = norm(item.get("itemInstanceId"))
        if item_instance_id and item_instance_id in seen:
            continue
        if item_instance_id:
            seen.add(item_instance_id)
        instance_payload = instances.get(item_instance_id, {}) if item_instance_id else {}
        indexed.append(
            {
                "itemInstanceId": item_instance_id or None,
                "itemHash": str(item.get("itemHash")) if item.get("itemHash") is not None else None,
                "bucketHash": str(item.get("bucketHash")) if item.get("bucketHash") is not None else None,
                "bucketName": norm(instance_payload.get("bucketTypeHash") or item.get("bucketHash")),
                "location": item.get("location"),
                "transferStatus": instance_payload.get("canEquip"),
            }
        )
    return indexed


def resolve_item_instances(planned_items: list[dict[str, Any]], inventory_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in planned_items:
        instance_id = norm(item.get("itemInstanceId"))
        slot = norm(item.get("slot"))
        item_hash = norm(item.get("itemHash"))

        chosen = None
        if instance_id:
            chosen = next((x for x in inventory_index if norm(x.get("itemInstanceId")) == instance_id), None)
        if chosen is None and item_hash:
            hash_matches = [x for x in inventory_index if norm(x.get("itemHash")) == item_hash]
            if slot:
                slot_filtered = [x for x in hash_matches if slot_matches(slot, x.get("bucketName") or "")]
                chosen = slot_filtered[0] if slot_filtered else (hash_matches[0] if hash_matches else None)
            elif hash_matches:
                chosen = hash_matches[0]

        resolved.append(
            {
                "slot": slot,
                "name": item.get("name"),
                "requestedInstanceId": item.get("itemInstanceId"),
                "requestedHash": item.get("itemHash"),
                "resolvedInstanceId": chosen.get("itemInstanceId") if chosen else None,
                "resolvedHash": chosen.get("itemHash") if chosen else item.get("itemHash"),
                "resolved": chosen is not None,
            }
        )
    return resolved


def equip_item(client: BungieLiveClient, membership_type: int, character_id: str, item_instance_id: str) -> dict[str, Any]:
    payload = {
        "itemId": item_instance_id,
        "characterId": character_id,
        "membershipType": membership_type,
    }
    return client.post("/Destiny2/Actions/Items/EquipItem/", payload)


def equip_full_build(client: BungieLiveClient, membership_type: int, character_id: str, resolved_items: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    results = []
    for item in resolved_items:
        if not item.get("resolved"):
            results.append(
                {
                    "slot": item.get("slot"),
                    "name": item.get("name"),
                    "status": "skipped_unresolved",
                    "message": "Could not resolve item instance ID",
                }
            )
            continue

        if dry_run:
            results.append(
                {
                    "slot": item.get("slot"),
                    "name": item.get("name"),
                    "status": "dry_run",
                    "itemInstanceId": item.get("resolvedInstanceId"),
                }
            )
            continue

        try:
            response = equip_item(client, membership_type, character_id, str(item.get("resolvedInstanceId")))
            results.append(
                {
                    "slot": item.get("slot"),
                    "name": item.get("name"),
                    "status": "equipped",
                    "itemInstanceId": item.get("resolvedInstanceId"),
                    "apiResponse": response,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "slot": item.get("slot"),
                    "name": item.get("name"),
                    "status": "failed",
                    "itemInstanceId": item.get("resolvedInstanceId"),
                    "message": str(exc),
                }
            )
    return {
        "results": results,
        "equipped_count": sum(1 for x in results if x["status"] == "equipped"),
        "dry_run_count": sum(1 for x in results if x["status"] == "dry_run"),
        "failed_count": sum(1 for x in results if x["status"] == "failed"),
        "unresolved_count": sum(1 for x in results if x["status"] == "skipped_unresolved"),
    }


def render_md(payload_type: str, character_id: str, membership_type: int, membership_id: str, dry_run: bool, resolved_items: list[dict[str, Any]], equip_result: dict[str, Any]) -> str:
    lines = [
        "# Warmind Live DIM Integration",
        "",
        f"- Source Payload: **{payload_type}**",
        f"- Membership Type: **{membership_type}**",
        f"- Membership ID: **{membership_id}**",
        f"- Character ID: **{character_id}**",
        f"- Dry Run: **{dry_run}**",
        "",
        "## Resolution Plan",
    ]
    for item in resolved_items:
        lines.append(
            f"- **{item.get('slot') or 'unknown'}**: {item.get('name') or 'Unknown'} | requestedInstance={item.get('requestedInstanceId')} | resolvedInstance={item.get('resolvedInstanceId')} | resolved={item.get('resolved')}"
        )
    lines.extend([
        "",
        "## Live Equip Result",
        f"- Equipped: **{equip_result.get('equipped_count', 0)}**",
        f"- Dry Run: **{equip_result.get('dry_run_count', 0)}**",
        f"- Failed: **{equip_result.get('failed_count', 0)}**",
        f"- Unresolved: **{equip_result.get('unresolved_count', 0)}**",
    ])
    for item in equip_result.get("results", []):
        lines.append(
            f"- {item.get('slot') or 'unknown'} | {item.get('name') or 'Unknown'} | status={item.get('status')} | itemInstanceId={item.get('itemInstanceId')} | message={item.get('message', '')}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 19A live DIM integration")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--auth-dir", default=DEFAULT_AUTH_DIR)
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--character-id", required=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    auth_dir = Path(args.auth_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    auth_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(auth_dir, args.membership_type, args.membership_id, args.character_id)
    client = BungieLiveClient(config)
    membership_type, membership_id = resolve_membership(client, config)
    profile_payload = fetch_live_profile(client, membership_type, membership_id)

    payload_type, payload = pick_best_payload(output_dir)
    planned_items = extract_planned_items(payload_type, payload)
    character_id = choose_character_id(profile_payload, config.character_id, planned_items)
    inventory_index = build_inventory_index(profile_payload, character_id)
    resolved_items = resolve_item_instances(planned_items, inventory_index)

    plan_payload = {
        "payload_type": payload_type,
        "membership_type": membership_type,
        "membership_id": membership_id,
        "character_id": character_id,
        "dry_run": args.dry_run,
        "resolved_items": resolved_items,
    }
    write_json(output_dir / DEFAULT_PLAN_FILE, plan_payload)

    equip_result = equip_full_build(client, membership_type, character_id, resolved_items, dry_run=args.dry_run)
    result_payload = {
        "payload_type": payload_type,
        "membership_type": membership_type,
        "membership_id": membership_id,
        "character_id": character_id,
        "dry_run": args.dry_run,
        "equip_result": equip_result,
        "resolved_items": resolved_items,
    }
    write_json(output_dir / DEFAULT_RESULT_FILE, result_payload)
    write(output_dir / "Phase190 Live Equip.md", render_md(payload_type, character_id, membership_type, membership_id, args.dry_run, resolved_items, equip_result))


if __name__ == "__main__":
    main()
