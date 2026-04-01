from __future__ import annotations

import argparse
import json
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
    "Graviton Forfeit",
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
    "Arbalest": ["barrier answer", "long-range utility"],
    "Leviathan's Breath": ["unstoppable utility", "safe heavy damage"],
    "Ager's Scepter": ["crowd control", "stasis utility"],
    "Graviton Lance": ["safe void primary", "add clear"],
    "Riskrunner": ["arc survivability", "easy add clear"],
    "Celestial Nighthawk": ["super burst", "boss damage"],
    "Lucky Pants": ["hand cannon burst", "swap damage"],
    "Cyrtarachne's Facade": ["survivability", "grapple DR"],
    "Caliban's Hand": ["add clear", "solar knife utility"],
    "Orpheus Rig": ["support", "super uptime"],
    "Gyrfalcon's Hauberk": ["void DPS", "volatile loop"],
    "Star-Eater Scales": ["super damage", "orb conversion"],
    "Young Ahamkara's Spine": ["ability loop", "solar utility"],
    "Assassin's Cowl": ["healing", "panic recovery"],
    "Wormhusk Crown": ["panic dodge heal", "survivability"],
    "Graviton Forfeit": ["invis uptime", "safe play"],
}

EXPECTED_CHASE = [
    ("Conditional Finality", "top-tier control and burst utility"),
    ("Apex Predator", "elite rocket benchmark"),
    ("Edge Transit", "meta heavy GL option"),
    ("Ex Diris", "situational but unique add-clear utility"),
    ("The Call", "strong legendary utility sidearm"),
]

GM_WEAPONS = [
    "Buried Bloodline",
    "Le Monarque",
    "Witherhoard",
    "Arbalest",
    "Divinity",
    "Outbreak Perfected",
    "Choir of One",
    "Leviathan's Breath",
    "Graviton Lance",
    "Ager's Scepter",
    "Trinity Ghoul",
    "Riskrunner",
    "Thunderlord",
]

HUNTER_GM_ARMOR_PRIORITY = [
    "Gyrfalcon's Hauberk",
    "Cyrtarachne's Facade",
    "Orpheus Rig",
    "Assassin's Cowl",
    "Wormhusk Crown",
    "Graviton Forfeit",
    "Lucky Pants",
]

DPS_BURST = [
    "Finality's Auger",
    "Still Hunt",
    "Izanagi's Burden",
    "Dragon's Breath",
    "Gjallarhorn",
    "Microcosm",
    "Whisper of the Worm",
    "The Queenbreaker",
    "Leviathan's Breath",
]

DPS_SUSTAINED = [
    "Outbreak Perfected",
    "Choir of One",
    "Microcosm",
    "Thunderlord",
    "Witherhoard",
    "Buried Bloodline",
    "Ager's Scepter",
]

DPS_SUPPORT = [
    "Divinity",
    "Gjallarhorn",
    "Tractor Cannon",
]

STAT_PROFILES = {
    "gm": {
        "Health": (90, 110),
        "Grenade": (80, 120),
        "Class": (70, 100),
        "Weapons": (90, 120),
        "Super": (20, 60),
        "Melee": (0, 50),
    },
    "dps": {
        "Health": (60, 90),
        "Grenade": (40, 90),
        "Class": (30, 70),
        "Weapons": (120, 170),
        "Super": (60, 110),
        "Melee": (0, 40),
    },
    "survivability": {
        "Health": (90, 120),
        "Grenade": (70, 110),
        "Class": (80, 110),
        "Weapons": (80, 115),
        "Super": (20, 50),
        "Melee": (0, 40),
    },
}

STAT_DISPLAY_ORDER = ["Health", "Grenade", "Class", "Weapons", "Super", "Melee"]


def load_env_file() -> None:
    for path in (Path('.env'), Path('.env.txt')):
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


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n', encoding='utf-8')


def dedupe_names(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        name = str(value).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def names_present(ordered_names: list[str], owned_names: set[str]) -> list[str]:
    return [name for name in ordered_names if name in owned_names]


def detect_current_hunter_loadout(loadouts_df: pd.DataFrame | None) -> dict[str, str]:
    if loadouts_df is None or loadouts_df.empty:
        return {}
    cols = {str(c).strip().lower(): c for c in loadouts_df.columns}
    class_col = cols.get('class type')
    name_col = cols.get('name')
    if not class_col or not name_col:
        return {}
    target = None
    for _, row in loadouts_df.iterrows():
        class_type = str(row.get(class_col, '')).strip().lower()
        name = str(row.get(name_col, '')).strip().lower()
        if class_type == 'hunter' and ('equipped hunter' in name or name == 'equipped hunter'):
            target = row
            break
    if target is None:
        return {}
    mapping = {
        'kinetic': 'equipped kinetic weapons',
        'energy': 'equipped energy weapons',
        'power': 'equipped power weapons',
        'helmet': 'equipped helmet',
        'gloves': 'equipped gauntlets',
        'chest': 'equipped chest armor',
        'legs': 'equipped leg armor',
        'class_item': 'equipped class armor',
        'health': 'health',
        'weapons_stat': 'weapons',
        'grenade': 'grenade',
        'class_stat': 'class',
        'super': 'super',
        'melee': 'melee',
        'subclass': 'subclass',
    }
    result = {}
    for out_key, in_key in mapping.items():
        col = cols.get(in_key)
        result[out_key] = str(target.get(col, '')).strip() if col else ''
    return result


def to_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def choose_stat_profile(current: dict[str, str]) -> tuple[str, str]:
    weapons = to_float(current.get('weapons_stat', 0))
    health = to_float(current.get('health', 0))
    grenade = to_float(current.get('grenade', 0))
    legs = current.get('legs', '')
    kinetic = current.get('kinetic', '')
    energy = current.get('energy', '')
    power = current.get('power', '')

    if legs in {'Lucky Pants', 'Celestial Nighthawk', 'Star-Eater Scales'} or power in {'Dragon\'s Breath', 'Gjallarhorn', 'Finality\'s Auger'}:
        return 'dps', 'Boss DPS / burst-oriented shell'
    if kinetic in {'Buried Bloodline', 'Witherhoard'} or energy in {'Le Monarque', 'Outbreak Perfected'} or health < 60:
        return 'gm', 'GM / endgame-safe shell'
    if grenade >= 100 and weapons >= 140:
        return 'dps', 'Ability-assisted damage shell'
    return 'survivability', 'General survivability shell'


def stat_recommendations(current: dict[str, str]) -> tuple[str, list[str], dict[str, dict[str, float]]]:
    profile_key, profile_label = choose_stat_profile(current)
    targets = STAT_PROFILES[profile_key]
    current_stats = {
        'Health': to_float(current.get('health', 0)),
        'Grenade': to_float(current.get('grenade', 0)),
        'Class': to_float(current.get('class_stat', 0)),
        'Weapons': to_float(current.get('weapons_stat', 0)),
        'Super': to_float(current.get('super', 0)),
        'Melee': to_float(current.get('melee', 0)),
    }
    advice = []
    detailed = {}
    for stat in STAT_DISPLAY_ORDER:
        low, high = targets[stat]
        cur = current_stats[stat]
        detailed[stat] = {'current': cur, 'target_low': low, 'target_high': high}
        if cur < low:
            advice.append(f'- Increase **{stat}** from {cur:.0f} toward **{low}-{high}**.')
        elif cur > high:
            advice.append(f'- Reduce **{stat}** from {cur:.0f} toward **{low}-{high}** to free budget.')
        else:
            advice.append(f'- **{stat}** at {cur:.0f} is already in a strong range (**{low}-{high}**).')
    if current_stats['Weapons'] >= 150 and current_stats['Health'] <= 60:
        advice.append('- Your build is over-invested in **Weapons** at the cost of survivability. That is exactly the trap we want to prevent.')
    if current_stats['Class'] < 60 and profile_key in {'gm', 'survivability'}:
        advice.append('- **Class** is too low for a safe Hunter loop. Dodge uptime is part of survivability, not a luxury stat.')
    return profile_label, advice, detailed


def build_owned_meta(owned_unique: list[str]) -> str:
    s_owned = [n for n in owned_unique if n in S_TIER]
    a_owned = [n for n in owned_unique if n in A_TIER and n not in s_owned]
    other_owned = [n for n in owned_unique if n not in s_owned and n not in a_owned]
    lines = ['# Owned Meta', '']
    for title, items in [('S-Tier', s_owned), ('A-Tier', a_owned), ('Other Owned Exotics', other_owned)]:
        lines.append(f'## {title}')
        if not items:
            lines.append('- None')
        else:
            for item in items:
                hints = ROLE_HINTS.get(item)
                lines.append(f"- **{item}**: {', '.join(hints)}" if hints else f'- **{item}**')
        lines.append('')
    return '\n'.join(lines)


def build_missing_meta(owned_set: set[str], heading: str = '# Missing Meta') -> str:
    lines = [heading, '']
    missing_any = False
    for item, reason in EXPECTED_CHASE:
        if item not in owned_set:
            missing_any = True
            lines.append(f'- **{item}**: {reason}')
    if not missing_any:
        lines.append('- No tracked chase items missing from the current shortlist.')
    return '\n'.join(lines)


def build_gm_meta(owned_set: set[str], current: dict[str, str]) -> str:
    safe_weapons = names_present(GM_WEAPONS, owned_set)
    armor_priority = names_present(HUNTER_GM_ARMOR_PRIORITY, owned_set)
    lines = ['# GM Meta', '']
    lines.append('## Core Safe Weapons (You Own)')
    if safe_weapons:
        for item in safe_weapons:
            lines.append(f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['gm-safe']))}")
    else:
        lines.append('- No core GM weapons detected.')
    lines.extend(['', '## Hunter Survivability Core'])
    if armor_priority:
        for item in armor_priority:
            lines.append(f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['survivability']))}")
    else:
        lines.append('- No priority Hunter survivability exotics detected.')
    lines.extend(['', '## Champion Coverage'])
    barrier, overload, unstoppable = [], [], []
    if 'Arbalest' in owned_set:
        barrier.append('Arbalest')
    if 'Le Monarque' in owned_set:
        overload.append('Le Monarque')
    if 'Outbreak Perfected' in owned_set:
        overload.append('Outbreak Perfected (artifact pulse)')
    if 'Riskrunner' in owned_set:
        overload.append('Riskrunner (artifact SMG)')
    if "Leviathan's Breath" in owned_set:
        unstoppable.append("Leviathan's Breath")
    if 'Trinity Ghoul' in owned_set:
        unstoppable.append('Trinity Ghoul (artifact bow)')
    if 'Le Monarque' in owned_set:
        unstoppable.append('Le Monarque (artifact bow)')
    lines.append(f"- **Barrier**: {', '.join(barrier) if barrier else 'No clear barrier solution detected yet.'}")
    lines.append(f"- **Overload**: {', '.join(overload) if overload else 'No overload solution detected yet.'}")
    lines.append(f"- **Unstoppable**: {', '.join(unstoppable) if unstoppable else 'No unstoppable solution detected yet.'}")
    lines.extend(['', '## Recommended GM Default Shell'])
    if 'Buried Bloodline' in owned_set:
        lines.append('- Kinetic / utility slot: Buried Bloodline')
    elif 'Witherhoard' in owned_set:
        lines.append('- Kinetic / utility slot: Witherhoard')
    if 'Le Monarque' in owned_set:
        lines.append('- Primary pressure slot: Le Monarque')
    elif 'Outbreak Perfected' in owned_set:
        lines.append('- Primary pressure slot: Outbreak Perfected')
    if "Leviathan's Breath" in owned_set:
        lines.append("- Heavy slot: Leviathan's Breath for safer champion and boss utility")
    elif 'Thunderlord' in owned_set:
        lines.append('- Heavy slot: Thunderlord for easy damage and ad control')
    elif "Dragon's Breath" in owned_set:
        lines.append("- Heavy slot: Dragon's Breath for passive boss damage")
    lines.extend(['', '## Avoid This'])
    health = to_float(current.get('health', 0))
    weapons_stat = to_float(current.get('weapons_stat', 0))
    if weapons_stat >= 140 and health <= 60:
        lines.append(f'- Your current Hunter profile is over-skewed toward Weapons ({weapons_stat:.0f}) and too low on Health ({health:.0f}). That is a GM trap.')
    else:
        lines.append('- No major stat trap detected from the current Hunter shell.')
    if current.get('legs') == 'Lucky Pants':
        lines.append("- Lucky Pants is strong, but for blind or high-pressure GMs it is less stable than Gyrfalcon's, Cyrtarachne, or Orpheus.")
    return '\n'.join(lines)


def build_dps_report(owned_set: set[str]) -> str:
    lines = ['# DPS', '']
    for title, pool in [('Boss Burst', DPS_BURST), ('Sustained DPS', DPS_SUSTAINED), ('Support DPS', DPS_SUPPORT)]:
        lines.append(f'## {title}')
        hits = names_present(pool, owned_set)
        if not hits:
            lines.append('- None')
        else:
            for item in hits:
                lines.append(f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['dps']))}")
        lines.append('')
    return '\n'.join(lines)


def build_replacement_report(owned_set: set[str], current: dict[str, str]) -> str:
    lines = ['# Replacement', '']
    if not current:
        lines.append('- No Equipped Hunter loadout found in loadouts CSV, so replacement logic was skipped.')
        return '\n'.join(lines)
    kinetic = current.get('kinetic', '')
    energy = current.get('energy', '')
    power = current.get('power', '')
    legs = current.get('legs', '')
    lines.append('## Current Equipped Hunter')
    for label, value in [('Kinetic', kinetic), ('Energy', energy), ('Power', power), ('Armor Exotic / key piece', legs), ('Health', current.get('health', '')), ('Weapons', current.get('weapons_stat', ''))]:
        lines.append(f'- {label}: {value or "Unknown"}')
    lines.extend(['', '## GM Replacements'])
    if kinetic not in {'Buried Bloodline', 'Witherhoard', 'Arbalest'}:
        if 'Buried Bloodline' in owned_set:
            lines.append(f'- Replace **{kinetic or "current kinetic"}** with **Buried Bloodline** for safer survivability and stronger GM utility.')
        elif 'Witherhoard' in owned_set:
            lines.append(f'- Replace **{kinetic or "current kinetic"}** with **Witherhoard** for safer passive damage and area control.')
    else:
        lines.append(f'- Keep **{kinetic}**. It already fits a strong GM utility role.')
    if energy not in {'Le Monarque', 'Outbreak Perfected', 'Choir of One', 'Divinity', 'Graviton Lance'}:
        if 'Le Monarque' in owned_set:
            lines.append(f'- Replace **{energy or "current energy"}** with **Le Monarque** for safer overload and ranged pressure.')
        elif 'Outbreak Perfected' in owned_set:
            lines.append(f'- Replace **{energy or "current energy"}** with **Outbreak Perfected** for reliable primary DPS and ammo economy.')
    else:
        lines.append(f'- Keep **{energy}** when the activity supports its role.')
    if power not in {"Leviathan's Breath", 'Thunderlord', "Dragon's Breath"}:
        if "Leviathan's Breath" in owned_set:
            lines.append(f'- Replace **{power or "current heavy"}** with **Leviathan\'s Breath** for safer champion and boss utility in GMs.')
        elif 'Thunderlord' in owned_set:
            lines.append(f'- Replace **{power or "current heavy"}** with **Thunderlord** for easier, lower-friction GM damage.')
    else:
        lines.append(f'- Keep **{power}**. It is already in your safe-GM heavy pool.')
    if legs == 'Lucky Pants':
        if "Gyrfalcon's Hauberk" in owned_set:
            lines.append("- Replace **Lucky Pants** with **Gyrfalcon's Hauberk** when survivability and invis loop matter more than hand-cannon burst.")
        elif "Cyrtarachne's Facade" in owned_set:
            lines.append("- Replace **Lucky Pants** with **Cyrtarachne's Facade** when you need a safer DR-oriented Hunter shell.")
    lines.extend(['', '## Boss DPS Replacements'])
    if kinetic not in {"Izanagi's Burden", 'Witherhoard', 'Outbreak Perfected'} and "Izanagi's Burden" in owned_set:
        lines.append(f'- For boss damage, replace **{kinetic or "current kinetic"}** with **Izanagi\'s Burden** for real swap burst.')
    if energy not in {'Choir of One', 'Outbreak Perfected', 'Divinity', 'Still Hunt'}:
        if 'Still Hunt' in owned_set:
            lines.append(f'- For Hunter boss DPS, replace **{energy or "current energy"}** with **Still Hunt** when precision phases reward it.')
        elif 'Choir of One' in owned_set:
            lines.append(f'- For more direct burst, replace **{energy or "current energy"}** with **Choir of One**.')
    if power not in {"Dragon's Breath", 'Gjallarhorn', 'Microcosm', "Finality's Auger", "Leviathan's Breath", 'Thunderlord'} and "Dragon's Breath" in owned_set:
        lines.append(f'- For boss DPS, replace **{power or "current heavy"}** with **Dragon\'s Breath** unless the encounter specifically prefers a different heavy.')
    lines.extend(['', '## Farm If No Owned Upgrade Feels Right'])
    for item, reason in EXPECTED_CHASE[:3]:
        if item not in owned_set:
            lines.append(f'- **{item}**: {reason}')
    return '\n'.join(lines)


def build_stat_optimization(current: dict[str, str]) -> tuple[str, dict]:
    lines = ['# Stat Optimization', '']
    if not current:
        lines.append('- No Equipped Hunter loadout found, so stat optimization could not be calculated.')
        return '\n'.join(lines), {}
    profile_key, profile_label = choose_stat_profile(current)
    lines.append(f'## Recommended Profile')
    lines.append(f'- **{profile_label}**')
    lines.append('')
    lines.append('## Current vs Target')
    lines.append('')
    _, advice, detailed = stat_recommendations(current)
    for stat in STAT_DISPLAY_ORDER:
        entry = detailed[stat]
        lines.append(f"- **{stat}**: current {entry['current']:.0f} | target {entry['target_low']:.0f}-{entry['target_high']:.0f}")
    lines.append('')
    lines.append('## Recommendations')
    lines.extend(advice)
    export_payload = {
        'profile_key': profile_key,
        'profile_label': profile_label,
        'current_loadout': current,
        'targets': detailed,
        'recommendations': advice,
    }
    return '\n'.join(lines), export_payload


def build_set_bonus_report(armor_df: pd.DataFrame, type_col: str | None, owner_col: str | None) -> str:
    if not type_col:
        return '# Set Bonus Candidates\n\n- Structured set-bonus detection is not wired yet.'
    armor_types = armor_df[armor_df[type_col].astype(str).str.contains('Helmet|Gauntlets|Chest|Leg|Cloak|Bond|Mark', case=False, regex=True, na=False)].copy()
    owner_counts = {}
    if owner_col and not armor_types.empty:
        for _, row in armor_types.iterrows():
            owner = str(row.get(owner_col, '')).strip() or 'Unknown'
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
    lines = ['# Set Bonus Candidates', '', '## Current Status', '- Structured set-bonus detection is not wired yet.']
    if owner_counts:
        lines.extend(['', '## Armor Counts By Owner'])
        for owner, count in sorted(owner_counts.items()):
            lines.append(f'- {owner}: {count}')
    return '\n'.join(lines)


def generate_reports(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path, use_bungie: bool) -> None:
    load_env_file()
    df_w = pd.read_csv(weapons).fillna('')
    df_a = pd.read_csv(armor).fillna('')
    df = pd.concat([df_w, df_a], ignore_index=True).fillna('')
    ldf = pd.read_csv(loadouts).fillna('') if loadouts and loadouts.exists() else None
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
    owned_set = set(owned_unique)
    current_hunter = detect_current_hunter_loadout(ldf)

    write(output_dir / 'Owned Meta.md', build_owned_meta(owned_unique))
    write(output_dir / 'Missing Meta.md', build_missing_meta(owned_set))
    write(output_dir / 'GM Meta.md', build_gm_meta(owned_set, current_hunter))
    write(output_dir / 'DPS.md', build_dps_report(owned_set))
    write(output_dir / 'Replacement.md', build_replacement_report(owned_set, current_hunter))
    write(output_dir / 'Farm Next.md', build_missing_meta(owned_set, '# Farm Next'))
    write(output_dir / 'Set Bonus Candidates.md', build_set_bonus_report(df, type_col, owner_col))
    stat_md, export_payload = build_stat_optimization(current_hunter)
    write(output_dir / 'Stat Optimization.md', stat_md)
    if export_payload:
        (output_dir / 'recommendation_export.json').write_text(json.dumps(export_payload, indent=2), encoding='utf-8')

    if ldf is not None:
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
    parser = argparse.ArgumentParser(description='DIM Intelligence Engine Phase 3.5')
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
