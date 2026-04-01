from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API_ROOT = "https://www.bungie.net/Platform"
DEFAULT_COMPONENTS = [100, 102, 200, 201, 205, 300]


class BungieApiError(RuntimeError):
    pass


@dataclass
class BungieCredentials:
    api_key: str
    access_token: str | None = None
    membership_type: int | None = None
    membership_id: str | None = None


class BungieClient:
    def __init__(self, creds: BungieCredentials) -> None:
        self.creds = creds
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": creds.api_key})
        if creds.access_token:
            self.session.headers.update({"Authorization": f"Bearer {creds.access_token}"})

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(f"{API_ROOT}{path}", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("ErrorCode") not in (1, "1", None):
            raise BungieApiError(payload.get("Message") or payload.get("ErrorStatus") or "Unknown Bungie API error")
        return payload

    def get_current_user_memberships(self) -> dict[str, Any]:
        if not self.creds.access_token:
            raise BungieApiError("BUNGIE_ACCESS_TOKEN is required for live user membership discovery.")
        return self._get("/User/GetMembershipsForCurrentUser/")

    def get_profile(self, membership_type: int, membership_id: str, components: list[int] | None = None) -> dict[str, Any]:
        component_list = components or DEFAULT_COMPONENTS
        return self._get(
            f"/Destiny2/{membership_type}/Profile/{membership_id}/",
            components=",".join(str(c) for c in component_list),
        )


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


def build_live_summary(profile_payload: dict[str, Any], membership_type: int, membership_id: str) -> dict[str, Any]:
    response = profile_payload.get("Response", {})
    profile = response.get("profile", {}).get("data", {})
    characters = response.get("characters", {}).get("data", {})
    profile_inventory = response.get("profileInventory", {}).get("data", {}).get("items", [])
    character_inventories = response.get("characterInventories", {}).get("data", {})
    character_equipment = response.get("characterEquipment", {}).get("data", {})
    item_components = response.get("itemComponents", {})

    character_summaries: list[dict[str, Any]] = []
    for character_id, char_data in characters.items():
        inv_count = len(character_inventories.get(character_id, {}).get("items", []))
        equip_count = len(character_equipment.get(character_id, {}).get("items", []))
        character_summaries.append(
            {
                "character_id": character_id,
                "class_hash": char_data.get("classHash"),
                "race_hash": char_data.get("raceHash"),
                "gender_hash": char_data.get("genderHash"),
                "light": char_data.get("light"),
                "base_character_level": char_data.get("baseCharacterLevel"),
                "title_record_hash": char_data.get("titleRecordHash"),
                "inventory_count": inv_count,
                "equipment_count": equip_count,
            }
        )

    return {
        "membership_type": membership_type,
        "membership_id": membership_id,
        "character_count": len(characters),
        "vault_item_count": len(profile_inventory),
        "character_summaries": character_summaries,
        "item_component_keys": sorted(item_components.keys()),
        "profile_last_played": profile.get("dateLastPlayed"),
    }


def render_live_md(summary: dict[str, Any], source: str) -> str:
    lines = [
        "# Warmind Live API",
        "",
        f"- Source: **{source}**",
        f"- Membership Type: **{summary['membership_type']}**",
        f"- Membership ID: **{summary['membership_id']}**",
        f"- Character Count: **{summary['character_count']}**",
        f"- Vault Item Count: **{summary['vault_item_count']}**",
        f"- Profile Last Played: **{summary.get('profile_last_played') or 'Unknown'}**",
        "",
        "## Characters",
    ]
    for char in summary["character_summaries"]:
        lines.append(
            f"- **{char['character_id']}** | light: {char.get('light')} | base level: {char.get('base_character_level')} | "
            f"inventory: {char.get('inventory_count')} | equipped: {char.get('equipment_count')}"
        )
    lines.extend(["", "## Available Item Components", f"- {', '.join(summary['item_component_keys']) if summary['item_component_keys'] else 'None returned'}"])
    lines.extend(
        [
            "",
            "## Next Warmind Steps",
            "- Map live item hashes and instance IDs into the Warmind scoring and simulation pipeline.",
            "- Use authenticated inventory reads for vault-aware, CSV-free recommendations.",
            "- Wire authenticated equip and loadout actions only after live profile resolution is stable.",
        ]
    )
    return "\n".join(lines)


def resolve_membership_from_args_or_api(client: BungieClient, args: argparse.Namespace) -> tuple[int, str, str]:
    if args.membership_type and args.membership_id:
        return int(args.membership_type), str(args.membership_id), "manual"

    memberships_payload = client.get_current_user_memberships()
    response = memberships_payload.get("Response", {})
    destiny_memberships = response.get("destinyMemberships") or []
    if not destiny_memberships:
        raise BungieApiError("No Destiny memberships were returned for the current Bungie account.")

    primary = next((m for m in destiny_memberships if m.get("crossSaveOverride") and m.get("crossSaveOverride") != 0), None)
    if primary is None:
        primary = destiny_memberships[0]

    membership_type = int(primary["membershipType"])
    membership_id = str(primary["membershipId"])
    return membership_type, membership_id, "oauth"


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 9 live Bungie API scaffold")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--membership-type", type=int, required=False)
    parser.add_argument("--membership-id", required=False)
    parser.add_argument("--components", required=False, help="Comma-separated Destiny component IDs. Defaults to 100,102,200,201,205,300")
    args = parser.parse_args()

    load_env_file()

    api_key = os.getenv("BUNGIE_API_KEY", "").strip()
    access_token = os.getenv("BUNGIE_ACCESS_TOKEN", "").strip() or None
    membership_type_env = os.getenv("BUNGIE_MEMBERSHIP_TYPE", "").strip() or None
    membership_id_env = os.getenv("BUNGIE_MEMBERSHIP_ID", "").strip() or None

    membership_type = args.membership_type or (int(membership_type_env) if membership_type_env else None)
    membership_id = args.membership_id or membership_id_env

    if not api_key:
        raise SystemExit("BUNGIE_API_KEY is required. Set it in your environment or .env file.")

    client = BungieClient(BungieCredentials(api_key=api_key, access_token=access_token, membership_type=membership_type, membership_id=membership_id))

    resolved_membership_type, resolved_membership_id, source = resolve_membership_from_args_or_api(client, argparse.Namespace(membership_type=membership_type, membership_id=membership_id))

    components = DEFAULT_COMPONENTS
    if args.components:
        components = [int(x.strip()) for x in args.components.split(",") if x.strip()]

    profile_payload = client.get_profile(resolved_membership_type, resolved_membership_id, components=components)
    summary = build_live_summary(profile_payload, resolved_membership_type, resolved_membership_id)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live_profile.json").write_text(json.dumps(profile_payload, indent=2), encoding="utf-8")
    (out / "live_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write(out / "Warmind Live API.md", render_live_md(summary, source))


if __name__ == "__main__":
    main()
