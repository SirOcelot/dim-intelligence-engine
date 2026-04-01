from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import pandas as pd
import requests

API_ROOT = "https://www.bungie.net/Platform"
DEFAULT_COMPONENTS = [102, 201, 205, 300]

KINETIC_PRIORITY = ["Buried Bloodline", "Witherhoard", "Arbalest"]
ENERGY_PRIORITY = ["Le Monarque", "Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"]
POWER_PRIORITY = ["Leviathan's Breath", "Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"]
ARMOR_PRIORITY = ["Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Wormhusk Crown", "Lucky Pants"]


class BungieApiError(RuntimeError):
    pass


def load_env_file() -> None:
    for path in (Path('.env'), Path('.env.txt')):
        if not path.exists():
            continue
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        break


def first_col(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n', encoding='utf-8')


def dedupe_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        name = str(value).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def choose_first_owned(priority: list[str], owned: set[str]) -> str:
    for item in priority:
        if item in owned:
            return item
    return 'No clear pick'


class BungieClient:
    def __init__(self, api_key: str, access_token: str | None = None) -> None:
        self.s = requests.Session()
        self.s.headers.update({'X-API-Key': api_key})
        if access_token:
            self.s.headers.update({'Authorization': f'Bearer {access_token}'})

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        r = self.s.get(f'{API_ROOT}{path}', params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get('ErrorCode') not in (1, '1', None):
            raise BungieApiError(data.get('Message') or data.get('ErrorStatus') or 'Unknown Bungie API error')
        return data

    def current_memberships(self) -> dict[str, Any]:
        return self.get('/User/GetMembershipsForCurrentUser/')

    def profile(self, membership_type: int, membership_id: str, components: list[int] | None = None) -> dict[str, Any]:
        return self.get(
            f'/Destiny2/{membership_type}/Profile/{membership_id}/',
            components=','.join(str(x) for x in (components or DEFAULT_COMPONENTS)),
        )


def resolve_membership(client: BungieClient, membership_type: int | None, membership_id: str | None) -> tuple[int, str, str]:
    if membership_type and membership_id:
        return membership_type, membership_id, 'manual'
    memberships = client.current_memberships().get('Response', {}).get('destinyMemberships') or []
    if not memberships:
        raise BungieApiError('No Destiny memberships returned for the current account.')
    primary = memberships[0]
    return int(primary['membershipType']), str(primary['membershipId']), 'oauth'


def detect_current_hunter_loadout(loadouts_df: pd.DataFrame | None) -> dict[str, str]:
    if loadouts_df is None or loadouts_df.empty:
        return {}
    cols = {str(c).strip().lower(): c for c in loadouts_df.columns}
    class_col = cols.get('class type')
    name_col = cols.get('name')
    if not class_col or not name_col:
        return {}
    row = None
    for _, candidate in loadouts_df.iterrows():
        if str(candidate.get(class_col, '')).strip().lower() == 'hunter' and 'equipped hunter' in str(candidate.get(name_col, '')).strip().lower():
            row = candidate
            break
    if row is None:
        return {}
    mapping = {
        'kinetic': 'equipped kinetic weapons',
        'energy': 'equipped energy weapons',
        'power': 'equipped power weapons',
        'legs': 'equipped leg armor',
        'subclass': 'subclass',
    }
    result: dict[str, str] = {}
    for out_key, in_key in mapping.items():
        col = cols.get(in_key)
        result[out_key] = str(row.get(col, '')).strip() if col else ''
    return result


def build_recommended_shell(owned: set[str]) -> dict[str, str]:
    return {
        'kinetic': choose_first_owned(KINETIC_PRIORITY, owned),
        'energy': choose_first_owned(ENERGY_PRIORITY, owned),
        'power': choose_first_owned(POWER_PRIORITY, owned),
        'armor_exotic': choose_first_owned(ARMOR_PRIORITY, owned),
        'subclass': 'Nightstalker',
    }


def bucket_name_from_hash(bucket_hash: int | str | None) -> str:
    value = str(bucket_hash or '')
    mapping = {
        '1498876634': 'kinetic',
        '2465295065': 'energy',
        '953998645': 'power',
        '3448274439': 'helmet',
        '3551918588': 'gauntlets',
        '14239492': 'chest',
        '20886954': 'legs',
        '1585787867': 'class_item',
    }
    return mapping.get(value, 'unknown')


def collect_live_items(profile_payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = profile_payload.get('Response', {})
    items: list[dict[str, Any]] = []

    profile_inventory = response.get('profileInventory', {}).get('data', {}).get('items', [])
    for item in profile_inventory:
        items.append({
            'itemInstanceId': item.get('itemInstanceId'),
            'itemHash': item.get('itemHash'),
            'bucket': bucket_name_from_hash(item.get('bucketHash')),
            'location': 'vault',
            'characterId': None,
        })

    for character_id, data in (response.get('characterInventories', {}).get('data', {}) or {}).items():
        for item in data.get('items', []):
            items.append({
                'itemInstanceId': item.get('itemInstanceId'),
                'itemHash': item.get('itemHash'),
                'bucket': bucket_name_from_hash(item.get('bucketHash')),
                'location': 'inventory',
                'characterId': character_id,
            })

    for character_id, data in (response.get('characterEquipment', {}).get('data', {}) or {}).items():
        for item in data.get('items', []):
            items.append({
                'itemInstanceId': item.get('itemInstanceId'),
                'itemHash': item.get('itemHash'),
                'bucket': bucket_name_from_hash(item.get('bucketHash')),
                'location': 'equipped',
                'characterId': character_id,
            })

    return items


def build_csv_index(df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    name_col = first_col(df, ['Name', 'Item Name'])
    id_col = first_col(df, ['Id', 'Item Id', 'Instance Id', 'Item Instance Id'])
    hash_col = first_col(df, ['Hash', 'Item Hash'])
    bucket_col = first_col(df, ['Bucket', 'Bucket Name', 'Slot'])
    owner_col = first_col(df, ['Owner', 'Character'])
    if not name_col:
        return {}
    index: dict[str, list[dict[str, Any]]] = {}
    for _, row in df.iterrows():
        name = str(row.get(name_col, '')).strip()
        if not name:
            continue
        bucket_raw = str(row.get(bucket_col, '')).strip().lower() if bucket_col else ''
        if 'kinetic' in bucket_raw:
            bucket = 'kinetic'
        elif 'energy' in bucket_raw:
            bucket = 'energy'
        elif 'power' in bucket_raw or 'heavy' in bucket_raw:
            bucket = 'power'
        elif 'leg' in bucket_raw:
            bucket = 'legs'
        else:
            bucket = bucket_raw or 'unknown'
        index.setdefault(name, []).append({
            'name': name,
            'itemInstanceId': str(row.get(id_col, '')).strip() if id_col else None,
            'itemHash': str(row.get(hash_col, '')).strip() if hash_col else None,
            'bucket': bucket,
            'owner': str(row.get(owner_col, '')).strip() if owner_col else None,
            'source': 'csv',
        })
    return index


def resolve_instance_for_name(name: str, bucket: str, csv_index: dict[str, list[dict[str, Any]]], live_items: list[dict[str, Any]]) -> dict[str, Any]:
    csv_matches = [x for x in csv_index.get(name, []) if x.get('bucket') in {bucket, 'unknown'}]
    if csv_matches:
        best = csv_matches[0]
        live_match = None
        if best.get('itemInstanceId'):
            live_match = next((x for x in live_items if str(x.get('itemInstanceId')) == str(best.get('itemInstanceId'))), None)
        return {
            'name': name,
            'bucket': bucket,
            'itemInstanceId': best.get('itemInstanceId') or (live_match or {}).get('itemInstanceId'),
            'itemHash': best.get('itemHash') or (live_match or {}).get('itemHash'),
            'characterId': (live_match or {}).get('characterId'),
            'location': (live_match or {}).get('location') or 'csv',
            'resolved': bool(best.get('itemInstanceId') or best.get('itemHash') or live_match),
        }
    live_bucket_matches = [x for x in live_items if x.get('bucket') == bucket]
    if live_bucket_matches:
        best = live_bucket_matches[0]
        return {
            'name': name,
            'bucket': bucket,
            'itemInstanceId': best.get('itemInstanceId'),
            'itemHash': best.get('itemHash'),
            'characterId': best.get('characterId'),
            'location': best.get('location'),
            'resolved': bool(best.get('itemInstanceId') or best.get('itemHash')),
        }
    return {
        'name': name,
        'bucket': bucket,
        'itemInstanceId': None,
        'itemHash': None,
        'characterId': None,
        'location': None,
        'resolved': False,
    }


def build_dim_loadout_payload(shell: dict[str, str], resolved_items: list[dict[str, Any]], membership_type: int, membership_id: str) -> dict[str, Any]:
    items = []
    for item in resolved_items:
        items.append({
            'id': item.get('itemInstanceId'),
            'hash': item.get('itemHash'),
            'bucket': item.get('bucket'),
            'equip': True,
            'name': item.get('name'),
        })
    payload = {
        'app': 'Warmind',
        'name': 'Warmind Recommended Loadout',
        'class': 'Hunter',
        'subclass': shell.get('subclass', 'Nightstalker'),
        'membershipType': membership_type,
        'membershipId': membership_id,
        'items': items,
        'notes': [
            'Warmind DIM export scaffold',
            'Ready for manual DIM import or downstream schema mapping',
        ],
    }
    return payload


def build_dim_url(payload: dict[str, Any]) -> str:
    compact = json.dumps(payload, separators=(',', ':'))
    return 'https://app.destinyitemmanager.com/#/loadouts?payload=' + quote(compact, safe='')


def build_equip_plan(resolved_items: list[dict[str, Any]]) -> dict[str, Any]:
    character_ids = [str(x.get('characterId')) for x in resolved_items if x.get('characterId')]
    character_id = character_ids[0] if character_ids else None
    return {
        'characterId': character_id,
        'itemIds': [str(x.get('itemInstanceId')) for x in resolved_items if x.get('itemInstanceId')],
        'resolvedItemCount': sum(1 for x in resolved_items if x.get('resolved')),
        'totalItemCount': len(resolved_items),
        'ready': bool(character_id and all(x.get('itemInstanceId') for x in resolved_items)),
    }


def render_md(shell: dict[str, str], resolved_items: list[dict[str, Any]], dim_url: str, equip_plan: dict[str, Any], source: str) -> str:
    lines = [
        '# Warmind Instance Wiring',
        '',
        f'- Source: **{source}**',
        f'- Kinetic: **{shell["kinetic"]}**',
        f'- Energy: **{shell["energy"]}**',
        f'- Power: **{shell["power"]}**',
        f'- Exotic Armor: **{shell["armor_exotic"]}**',
        f'- Subclass: **{shell["subclass"]}**',
        '',
        '## Resolved Items',
    ]
    for item in resolved_items:
        lines.append(
            f'- **{item["bucket"]}**: {item["name"]} | instanceId: {item.get("itemInstanceId")} | hash: {item.get("itemHash")} | '
            f'characterId: {item.get("characterId")} | location: {item.get("location")} | resolved: {item.get("resolved")}'
        )
    lines.extend([
        '',
        '## DIM Export',
        f'- DIM URL scaffold: `{dim_url}`',
        '',
        '## Equip Plan',
        f'- Character ID: **{equip_plan.get("characterId") or "Unknown"}**',
        f'- Resolved Items: **{equip_plan.get("resolvedItemCount")}/{equip_plan.get("totalItemCount")}**',
        f'- Ready for direct equip: **{equip_plan.get("ready")}**',
        '',
        '## Next Step',
        '- Use this payload as the bridge to direct API equip or DIM-side loadout import.',
    ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='Warmind instance ID + DIM export wiring')
    parser.add_argument('--weapons', required=False)
    parser.add_argument('--armor', required=False)
    parser.add_argument('--loadouts', required=False)
    parser.add_argument('--output-dir', default='output')
    parser.add_argument('--membership-type', type=int, required=False)
    parser.add_argument('--membership-id', required=False)
    args = parser.parse_args()

    load_env_file()
    api_key = os.getenv('BUNGIE_API_KEY', '').strip()
    access_token = os.getenv('BUNGIE_ACCESS_TOKEN', '').strip() or None
    membership_type = args.membership_type or (int(os.getenv('BUNGIE_MEMBERSHIP_TYPE', '').strip()) if os.getenv('BUNGIE_MEMBERSHIP_TYPE', '').strip() else None)
    membership_id = args.membership_id or (os.getenv('BUNGIE_MEMBERSHIP_ID', '').strip() or None)

    if not api_key:
        raise SystemExit('BUNGIE_API_KEY is required.')

    if not args.weapons or not args.armor:
        raise SystemExit('For this bridge version, provide --weapons and --armor CSV files so Warmind can map names to live instances.')

    df_w = pd.read_csv(args.weapons).fillna('')
    df_a = pd.read_csv(args.armor).fillna('')
    df = pd.concat([df_w, df_a], ignore_index=True).fillna('')
    ldf = pd.read_csv(args.loadouts).fillna('') if args.loadouts and Path(args.loadouts).exists() else None

    name_col = first_col(df, ['Name', 'Item Name'])
    rarity_col = first_col(df, ['Rarity', 'Tier Type Name'])
    if not name_col or not rarity_col:
        raise SystemExit('Could not detect required DIM columns.')

    exotics = df[df[rarity_col].astype(str).str.lower() == 'exotic'].copy()
    owned = set(dedupe_names(exotics[name_col]))
    shell = build_recommended_shell(owned)

    client = BungieClient(api_key, access_token)
    resolved_membership_type, resolved_membership_id, source = resolve_membership(client, membership_type, membership_id)
    profile_payload = client.profile(resolved_membership_type, resolved_membership_id)
    live_items = collect_live_items(profile_payload)
    csv_index = build_csv_index(df)

    current = detect_current_hunter_loadout(ldf)
    if current.get('subclass'):
        shell['subclass'] = current['subclass']

    resolved_items = [
        resolve_instance_for_name(shell['kinetic'], 'kinetic', csv_index, live_items),
        resolve_instance_for_name(shell['energy'], 'energy', csv_index, live_items),
        resolve_instance_for_name(shell['power'], 'power', csv_index, live_items),
        resolve_instance_for_name(shell['armor_exotic'], 'legs', csv_index, live_items),
    ]

    dim_payload = build_dim_loadout_payload(shell, resolved_items, resolved_membership_type, resolved_membership_id)
    dim_url = build_dim_url(dim_payload)
    equip_plan = build_equip_plan(resolved_items)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'phase101_live_profile.json').write_text(json.dumps(profile_payload, indent=2), encoding='utf-8')
    (out / 'phase101_dim_payload.json').write_text(json.dumps(dim_payload, indent=2), encoding='utf-8')
    (out / 'phase101_equip_plan.json').write_text(json.dumps(equip_plan, indent=2), encoding='utf-8')
    write(out / 'Phase101 Instance Wiring.md', render_md(shell, resolved_items, dim_url, equip_plan, source))


if __name__ == '__main__':
    main()
