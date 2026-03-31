from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

S_TIER = {
    "Witherhoard",
    "Buried Bloodline",
    "Finality's Auger",
    "Choir of One",
    "Microcosm",
    "Outbreak Perfected",
    "Divinity",
    "Gjallarhorn",
    "Izanagi's Burden",
    "Dragon's Breath",
    "Still Hunt",
    "Le Monarque",
    "Thunderlord",
    "Trinity Ghoul",
    "Celestial Nighthawk",
    "Lucky Pants",
    "Cyrtarachne's Facade",
    "Caliban's Hand",
    "Orpheus Rig",
    "Gyrfalcon's Hauberk",
    "Star-Eater Scales",
    "Young Ahamkara's Spine",
}

A_TIER = {
    "Ager's Scepter",
    "Arbalest",
    "Leviathan's Breath",
    "Sunshot",
    "Graviton Lance",
    "Whisper of the Worm",
    "The Queenbreaker",
    "Tractor Cannon",
    "Riskrunner",
    "Mothkeeper's Wraps",
    "Oathkeeper",
    "Relativism",
    "Gifted Conviction",
    "Assassin's Cowl",
    "Wormhusk Crown",
}

ROLE_HINTS = {
    "Witherhoard": ["area control", "damage over time", "swap DPS"],
    "Buried Bloodline": ["survivability", "void utility", "special DPS"],
    "Finality's Auger": ["burst DPS", "boss damage"],
    "Choir of One": ["burst DPS", "void pressure"],
    "Microcosm": ["shield break", "utility DPS"],
    "Outbreak Perfected": ["sustained DPS", "ammo efficiency"],
    "Divinity": ["support", "debuff"],
    "Gjallarhorn": ["rocket support", "wolfpack rounds"],
    "Izanagi's Burden": ["burst DPS", "swap damage"],
    "Dragon's Breath": ["damage over time", "boss damage"],
    "Still Hunt": ["precision DPS", "hunter synergy"],
    "Le Monarque": ["overload utility", "safe ranged damage"],
    "Thunderlord": ["easy DPS", "machine gun utility"],
    "Trinity Ghoul": ["add clear", "low-stress farming"],
    "Celestial Nighthawk": ["super burst", "boss damage"],
    "Lucky Pants": ["hand cannon burst", "swap damage"],
    "Cyrtarachne's Facade": ["survivability", "grapple DR"],
    "Caliban's Hand": ["add clear", "solar knife utility"],
    "Orpheus Rig": ["support", "super uptime"],
    "Gyrfalcon's Hauberk": ["void DPS", "volatile loop"],
    "Star-Eater Scales": ["super damage", "orb conversion"],
    "Young Ahamkara's Spine": ["ability loop", "solar utility"],
}

EXPECTED_CHASE = [
    ("Conditional Finality", "top-tier control and burst utility"),
    ("Apex Predator", "elite rocket benchmark"),
    ("Edge Transit", "meta heavy GL option"),
    ("Ex Diris", "situational but unique add-clear utility"),
    ("The Call", "strong legendary utility sidearm"),
]


def load_env_file() -> None:
    candidates = [Path('.env'), Path('.env.txt')]
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ[key] = value
        break


def first_col(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def slug(text: str) -> str:
    return text.replace('/', '-').replace('\\', '-').strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n', encoding='utf-8')


def dedupe_names(series: pd.Series) -> list[str]:
    seen = set()
    result = []
    for value in series:
        name = str(value).strip()
        if not name:
            continue
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def tier_for(name: str) -> str:
    if name in S_TIER:
        return 'S-Tier'
    if name in A_TIER:
        return 'A-Tier'
    return 'Owned'


def generate_reports(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path, use_bungie: bool) -> None:
    load_env_file()

    df_w = pd.read_csv(weapons).fillna('')
    df_a = pd.read_csv(armor).fillna('')
    df = pd.concat([df_w, df_a], ignore_index=True).fillna('')

    output_dir.mkdir(parents=True, exist_ok=True)

    name_col = first_col(df, ['Name', 'Item Name'])
    rarity_col = first_col(df, ['Rarity', 'Tier Type Name'])
    type_col = first_col(df, ['Type', 'Item Type'])
    owner_col = first_col(df, ['Owner', 'Character'])

    write(output_dir / 'manifest_summary.md', f'# Summary\n\nTotal Items: {len(df)}')

    if use_bungie:
        key = os.getenv('BUNGIE_API_KEY', '').strip()
        write(output_dir / 'bungie_status.md', f"Bungie API Enabled: {'YES' if key else 'NO KEY'}")

    if not name_col or not rarity_col:
        write(output_dir / 'Owned Meta.md', '# Owned Meta\n\nCould not detect required DIM columns.')
        return

    exotics = df[df[rarity_col].astype(str).str.lower() == 'exotic'].copy()
    owned_unique = dedupe_names(exotics[name_col])

    s_owned = [n for n in owned_unique if n in S_TIER]
    a_owned = [n for n in owned_unique if n in A_TIER and n not in s_owned]
    other_owned = [n for n in owned_unique if n not in s_owned and n not in a_owned]

    owned_lines = ['# Owned Meta', '']
    for title, items in [('S-Tier', s_owned), ('A-Tier', a_owned), ('Other Owned Exotics', other_owned)]:
        owned_lines.append(f'## {title}')
        if not items:
            owned_lines.append('- None')
        else:
            for item in items:
                hints = ROLE_HINTS.get(item)
                if hints:
                    owned_lines.append(f"- **{item}**: {', '.join(hints)}")
                else:
                    owned_lines.append(f'- **{item}**')
        owned_lines.append('')
    write(output_dir / 'Owned Meta.md', '\n'.join(owned_lines))

    missing_lines = ['# Missing Meta', '']
    missing_any = False
    for item, reason in EXPECTED_CHASE:
        if item not in owned_unique:
            missing_any = True
            missing_lines.append(f'- **{item}**: {reason}')
    if not missing_any:
        missing_lines.append('- No tracked chase items missing from the current shortlist.')
    write(output_dir / 'Missing Meta.md', '\n'.join(missing_lines))

    dps_priority = []
    for item in owned_unique:
        if item in S_TIER or item in A_TIER:
            score = 3 if item in S_TIER else 2
            if item in {'Finality\'s Auger', 'Buried Bloodline', 'Still Hunt', 'Izanagi\'s Burden', 'Dragon\'s Breath', 'Gjallarhorn', 'Microcosm'}:
                score += 2
            dps_priority.append((score, item))
    dps_priority.sort(key=lambda x: (-x[0], x[1]))
    dps_lines = ['# Best DPS Candidates', '']
    if not dps_priority:
        dps_lines.append('- No candidates identified.')
    else:
        for score, item in dps_priority[:15]:
            hints = ROLE_HINTS.get(item, [])
            reason = ', '.join(hints[:2]) if hints else 'general endgame value'
            dps_lines.append(f'- **{item}**: score {score}; {reason}')
    write(output_dir / 'Best DPS Candidates.md', '\n'.join(dps_lines))

    farm_lines = ['# Farm Next', '']
    ranked_missing = [(item, reason) for item, reason in EXPECTED_CHASE if item not in owned_unique]
    if not ranked_missing:
        farm_lines.append('- No obvious farm targets from the current shortlist.')
    else:
        for idx, (item, reason) in enumerate(ranked_missing, start=1):
            farm_lines.append(f'{idx}. **{item}**: {reason}')
    write(output_dir / 'Farm Next.md', '\n'.join(farm_lines))

    if type_col:
        armor_types = df[df[type_col].astype(str).str.contains('Helmet|Gauntlets|Chest|Leg|Cloak|Bond|Mark', case=False, regex=True, na=False)].copy()
        owner_counts = {}
        if owner_col and not armor_types.empty:
            for _, row in armor_types.iterrows():
                owner = str(row.get(owner_col, '')).strip() or 'Unknown'
                owner_counts[owner] = owner_counts.get(owner, 0) + 1
        set_lines = ['# Set Bonus Candidates', '', '## Current Status']
        set_lines.append('- Structured set-bonus detection is not wired yet.')
        if owner_counts:
            set_lines.append('')
            set_lines.append('## Armor Counts By Owner')
            for owner, count in sorted(owner_counts.items()):
                set_lines.append(f'- {owner}: {count}')
        write(output_dir / 'Set Bonus Candidates.md', '\n'.join(set_lines))

    if loadouts and loadouts.exists():
        ldf = pd.read_csv(loadouts).fillna('')
        lines = ['# Loadouts Summary', '', f'Count: **{len(ldf)}**', '']
        for idx, row in ldf.head(25).iterrows():
            lines.append(f'## Loadout {idx + 1}')
            for col in ldf.columns:
                value = str(row[col]).strip()
                if value:
                    lines.append(f'- {col}: {value}')
            lines.append('')
        write(output_dir / 'Loadouts Summary.md', '\n'.join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description='DIM Intelligence Engine Phase 2.6')
    parser.add_argument('--weapons', required=True)
    parser.add_argument('--armor', required=True)
    parser.add_argument('--loadouts', required=False)
    parser.add_argument('--use-bungie', action='store_true')
    parser.add_argument('--output-dir', default='output')
    args = parser.parse_args()

    generate_reports(
        weapons=Path(args.weapons),
        armor=Path(args.armor),
        loadouts=Path(args.loadouts) if args.loadouts else None,
        output_dir=Path(args.output_dir),
        use_bungie=args.use_bungie,
    )


if __name__ == '__main__':
    main()
