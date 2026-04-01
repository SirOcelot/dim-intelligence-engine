from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

S_TIER = {
    "Witherhoard", "Buried Bloodline", "Finality's Auger", "Choir of One", "Microcosm",
    "Outbreak Perfected", "Divinity", "Gjallarhorn", "Izanagi's Burden", "Dragon's Breath",
    "Still Hunt", "Le Monarque", "Thunderlord", "Trinity Ghoul", "Celestial Nighthawk",
    "Lucky Pants", "Cyrtarachne's Facade", "Caliban's Hand", "Orpheus Rig",
    "Gyrfalcon's Hauberk", "Star-Eater Scales", "Young Ahamkara's Spine",
}
A_TIER = {
    "Ager's Scepter", "Arbalest", "Leviathan's Breath", "Sunshot", "Graviton Lance",
    "Whisper of the Worm", "The Queenbreaker", "Tractor Cannon", "Riskrunner",
    "Mothkeeper's Wraps", "Oathkeeper", "Relativism", "Gifted Conviction",
    "Assassin's Cowl", "Wormhusk Crown", "Graviton Forfeit",
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
    "Buried Bloodline", "Le Monarque", "Witherhoard", "Arbalest", "Divinity",
    "Outbreak Perfected", "Choir of One", "Leviathan's Breath", "Graviton Lance",
    "Ager's Scepter", "Trinity Ghoul", "Riskrunner", "Thunderlord",
]
HUNTER_GM_ARMOR_PRIORITY = [
    "Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig",
    "Assassin's Cowl", "Wormhusk Crown", "Graviton Forfeit", "Lucky Pants",
]
DPS_BURST = [
    "Finality's Auger", "Still Hunt", "Izanagi's Burden", "Dragon's Breath",
    "Gjallarhorn", "Microcosm", "Whisper of the Worm", "The Queenbreaker", "Leviathan's Breath",
]
DPS_SUSTAINED = ["Outbreak Perfected", "Choir of One", "Microcosm", "Thunderlord", "Witherhoard", "Buried Bloodline", "Ager's Scepter"]
DPS_SUPPORT = ["Divinity", "Gjallarhorn", "Tractor Cannon"]
STAT_PROFILES = {
    "gm": {"Health": (90, 110), "Grenade": (80, 120), "Class": (70, 100), "Weapons": (90, 120), "Super": (20, 60), "Melee": (0, 50)},
    "dps": {"Health": (60, 90), "Grenade": (40, 90), "Class": (30, 70), "Weapons": (120, 170), "Super": (60, 110), "Melee": (0, 40)},
    "survivability": {"Health": (90, 120), "Grenade": (70, 110), "Class": (80, 110), "Weapons": (80, 115), "Super": (20, 50), "Melee": (0, 40)},
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
    seen = set(); result = []
    for value in values:
        name = str(value).strip()
        if name and name not in seen:
            seen.add(name); result.append(name)
    return result


def names_present(ordered_names: list[str], owned_names: set[str]) -> list[str]:
    return [name for name in ordered_names if name in owned_names]


def detect_current_hunter_loadout(loadouts_df: pd.DataFrame | None) -> dict[str, str]:
    if loadouts_df is None or loadouts_df.empty:
        return {}
    cols = {str(c).strip().lower(): c for c in loadouts_df.columns}
    class_col = cols.get('class type'); name_col = cols.get('name')
    if not class_col or not name_col:
        return {}
    target = None
    for _, row in loadouts_df.iterrows():
        if str(row.get(class_col, '')).strip().lower() == 'hunter' and 'equipped hunter' in str(row.get(name_col, '')).strip().lower():
            target = row; break
    if target is None:
        return {}
    mapping = {
        'kinetic': 'equipped kinetic weapons', 'energy': 'equipped energy weapons', 'power': 'equipped power weapons',
        'helmet': 'equipped helmet', 'gloves': 'equipped gauntlets', 'chest': 'equipped chest armor', 'legs': 'equipped leg armor',
        'class_item': 'equipped class armor', 'health': 'health', 'weapons_stat': 'weapons', 'grenade': 'grenade',
        'class_stat': 'class', 'super': 'super', 'melee': 'melee', 'subclass': 'subclass',
    }
    return {out_key: str(target.get(cols.get(in_key), '')).strip() if cols.get(in_key) else '' for out_key, in_key in mapping.items()}


def to_float(value: str) -> float:
    try: return float(str(value).strip())
    except Exception: return 0.0


def choose_stat_profile(current: dict[str, str]) -> tuple[str, str]:
    weapons = to_float(current.get('weapons_stat', 0)); health = to_float(current.get('health', 0)); grenade = to_float(current.get('grenade', 0))
    legs = current.get('legs', ''); kinetic = current.get('kinetic', ''); energy = current.get('energy', ''); power = current.get('power', '')
    if legs in {'Lucky Pants', 'Celestial Nighthawk', 'Star-Eater Scales'} or power in {"Dragon's Breath", 'Gjallarhorn', "Finality's Auger"}:
        return 'dps', 'Boss DPS / burst-oriented shell'
    if kinetic in {'Buried Bloodline', 'Witherhoard'} or energy in {'Le Monarque', 'Outbreak Perfected'} or health < 60:
        return 'gm', 'GM / endgame-safe shell'
    if grenade >= 100 and weapons >= 140:
        return 'dps', 'Ability-assisted damage shell'
    return 'survivability', 'General survivability shell'


def stat_recommendations(current: dict[str, str]) -> tuple[str, list[str], dict[str, dict[str, float]]]:
    profile_key, profile_label = choose_stat_profile(current)
    targets = STAT_PROFILES[profile_key]
    current_stats = {s: to_float(current.get(k, 0)) for s, k in [('Health','health'),('Grenade','grenade'),('Class','class_stat'),('Weapons','weapons_stat'),('Super','super'),('Melee','melee')]}
    advice = []; detailed = {}
    for stat in STAT_DISPLAY_ORDER:
        low, high = targets[stat]; cur = current_stats[stat]; detailed[stat] = {'current': cur, 'target_low': low, 'target_high': high}
        if cur < low: advice.append(f'- Increase **{stat}** from {cur:.0f} toward **{low}-{high}**.')
        elif cur > high: advice.append(f'- Reduce **{stat}** from {cur:.0f} toward **{low}-{high}** to free budget.')
        else: advice.append(f'- **{stat}** at {cur:.0f} is already in a strong range (**{low}-{high}**).')
    if current_stats['Weapons'] >= 150 and current_stats['Health'] <= 60:
        advice.append('- Your build is over-invested in **Weapons** at the cost of survivability. That is exactly the trap we want to prevent.')
    if current_stats['Class'] < 60 and profile_key in {'gm', 'survivability'}:
        advice.append('- **Class** is too low for a safe Hunter loop. Dodge uptime is part of survivability, not a luxury stat.')
    return profile_label, advice, detailed


def champion_lists(owned_set: set[str]) -> dict[str, list[str]]:
    barrier = []; overload = []; unstoppable = []
    if 'Arbalest' in owned_set: barrier.append('Arbalest')
    if 'Le Monarque' in owned_set: overload.append('Le Monarque')
    if 'Outbreak Perfected' in owned_set: overload.append('Outbreak Perfected (artifact pulse)')
    if 'Riskrunner' in owned_set: overload.append('Riskrunner (artifact SMG)')
    if "Leviathan's Breath" in owned_set: unstoppable.append("Leviathan's Breath")
    if 'Trinity Ghoul' in owned_set: unstoppable.append('Trinity Ghoul (artifact bow)')
    if 'Le Monarque' in owned_set: unstoppable.append('Le Monarque (artifact bow)')
    return {'Barrier': barrier, 'Overload': overload, 'Unstoppable': unstoppable}


def build_owned_meta(owned_unique: list[str]) -> str:
    s_owned = [n for n in owned_unique if n in S_TIER]
    a_owned = [n for n in owned_unique if n in A_TIER and n not in s_owned]
    other_owned = [n for n in owned_unique if n not in s_owned and n not in a_owned]
    lines = ['# Owned Meta', '']
    for title, items in [('S-Tier', s_owned), ('A-Tier', a_owned), ('Other Owned Exotics', other_owned)]:
        lines.append(f'## {title}')
        lines.extend([f"- **{item}**: {', '.join(ROLE_HINTS.get(item, []))}" if ROLE_HINTS.get(item) else f'- **{item}**' for item in items] or ['- None'])
        lines.append('')
    return '\n'.join(lines)


def build_missing_meta(owned_set: set[str], heading: str = '# Missing Meta') -> str:
    lines = [heading, '']
    missing = [(i, r) for i, r in EXPECTED_CHASE if i not in owned_set]
    lines.extend([f'- **{item}**: {reason}' for item, reason in missing] or ['- No tracked chase items missing from the current shortlist.'])
    return '\n'.join(lines)


def build_champion_coverage(owned_set: set[str]) -> str:
    lists = champion_lists(owned_set)
    lines = ['# Champion Coverage', '']
    for champ_type in ['Barrier', 'Overload', 'Unstoppable']:
        entries = lists[champ_type]
        lines.append(f"- **{champ_type}**: {', '.join(entries) if entries else 'No clear solution detected yet.'}")
    return '\n'.join(lines)


def build_avoid_this(current: dict[str, str], owned_set: set[str]) -> str:
    lines = ['# Avoid This', '']
    if not current:
        lines.append('- No current Hunter loadout found, so trap analysis was skipped.')
        return '\n'.join(lines)
    health = to_float(current.get('health', 0)); weapons_stat = to_float(current.get('weapons_stat', 0))
    if weapons_stat >= 140 and health <= 60:
        lines.append(f'- Do not run a Hunter shell with **Weapons {weapons_stat:.0f}** and **Health {health:.0f}** into hard endgame. That is a glass-cannon trap.')
    if current.get('legs') == 'Lucky Pants':
        lines.append("- **Lucky Pants** is not your safest blind-GM anchor. Use it when the activity rewards burst, not when survival is the bottleneck.")
    if current.get('power') and current.get('power') not in {"Leviathan's Breath", 'Thunderlord', "Dragon's Breath"}:
        lines.append(f"- **{current.get('power')}** may be workable, but it is not one of your safest GM heavy anchors.")
    if 'Buried Bloodline' in owned_set and current.get('kinetic') not in {'Buried Bloodline', 'Witherhoard', 'Arbalest'}:
        lines.append(f"- You own **Buried Bloodline**, so staying on **{current.get('kinetic') or 'your current kinetic'}** in a survival-focused activity may be leaving safety on the table.")
    if len(lines) == 2:
        lines.append('- No major trap picks detected from the current Hunter shell.')
    return '\n'.join(lines)


def build_gm_meta(owned_set: set[str], current: dict[str, str]) -> str:
    safe_weapons = names_present(GM_WEAPONS, owned_set); armor_priority = names_present(HUNTER_GM_ARMOR_PRIORITY, owned_set); champs = champion_lists(owned_set)
    lines = ['# GM Meta', '', '## Core Safe Weapons (You Own)']
    lines.extend([f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['gm-safe']))}" for item in safe_weapons] or ['- No core GM weapons detected.'])
    lines.extend(['', '## Hunter Survivability Core'])
    lines.extend([f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['survivability']))}" for item in armor_priority] or ['- No priority Hunter survivability exotics detected.'])
    lines.extend(['', '## Champion Coverage'])
    for champ in ['Barrier', 'Overload', 'Unstoppable']:
        lines.append(f"- **{champ}**: {', '.join(champs[champ]) if champs[champ] else 'No clear solution detected yet.'}")
    lines.extend(['', '## Recommended GM Default Shell'])
    if 'Buried Bloodline' in owned_set: lines.append('- Kinetic / utility slot: Buried Bloodline')
    elif 'Witherhoard' in owned_set: lines.append('- Kinetic / utility slot: Witherhoard')
    if 'Le Monarque' in owned_set: lines.append('- Primary pressure slot: Le Monarque')
    elif 'Outbreak Perfected' in owned_set: lines.append('- Primary pressure slot: Outbreak Perfected')
    if "Leviathan's Breath" in owned_set: lines.append("- Heavy slot: Leviathan's Breath for safer champion and boss utility")
    elif 'Thunderlord' in owned_set: lines.append('- Heavy slot: Thunderlord for easy damage and ad control')
    elif "Dragon's Breath" in owned_set: lines.append("- Heavy slot: Dragon's Breath for passive boss damage")
    lines.extend(['', '## Avoid This'])
    lines.extend(build_avoid_this(current, owned_set).splitlines()[2:])
    return '\n'.join(lines)


def build_dps_report(owned_set: set[str]) -> str:
    lines = ['# DPS', '']
    for title, pool in [('Boss Burst', DPS_BURST), ('Sustained DPS', DPS_SUSTAINED), ('Support DPS', DPS_SUPPORT)]:
        lines.append(f'## {title}')
        lines.extend([f"- **{item}**: {', '.join(ROLE_HINTS.get(item, ['dps']))}" for item in names_present(pool, owned_set)] or ['- None'])
        lines.append('')
    return '\n'.join(lines)


def build_replacement_report(owned_set: set[str], current: dict[str, str]) -> str:
    lines = ['# Replacement', '']
    if not current:
        lines.append('- No Equipped Hunter loadout found in loadouts CSV, so replacement logic was skipped.')
        return '\n'.join(lines)
    kinetic, energy, power, legs = current.get('kinetic',''), current.get('energy',''), current.get('power',''), current.get('legs','')
    lines.append('## Current Equipped Hunter')
    for label, value in [('Kinetic', kinetic), ('Energy', energy), ('Power', power), ('Armor Exotic / key piece', legs), ('Health', current.get('health', '')), ('Weapons', current.get('weapons_stat', ''))]:
        lines.append(f'- {label}: {value or "Unknown"}')
    lines.extend(['', '## GM Replacements'])
    if kinetic not in {'Buried Bloodline', 'Witherhoard', 'Arbalest'}:
        lines.append(f'- Replace **{kinetic or "current kinetic"}** with **Buried Bloodline** for safer survivability and stronger GM utility.' if 'Buried Bloodline' in owned_set else f'- Replace **{kinetic or "current kinetic"}** with **Witherhoard** for safer passive damage and area control.' if 'Witherhoard' in owned_set else '- No clear owned kinetic GM upgrade detected.')
    else: lines.append(f'- Keep **{kinetic}**. It already fits a strong GM utility role.')
    if energy not in {'Le Monarque', 'Outbreak Perfected', 'Choir of One', 'Divinity', 'Graviton Lance'}:
        lines.append(f'- Replace **{energy or "current energy"}** with **Le Monarque** for safer overload and ranged pressure.' if 'Le Monarque' in owned_set else f'- Replace **{energy or "current energy"}** with **Outbreak Perfected** for reliable primary DPS and ammo economy.' if 'Outbreak Perfected' in owned_set else '- No clear owned energy GM upgrade detected.')
    else: lines.append(f'- Keep **{energy}** when the activity supports its role.')
    if power not in {"Leviathan's Breath", 'Thunderlord', "Dragon's Breath"}:
        lines.append(f'- Replace **{power or "current heavy"}** with **Leviathan\'s Breath** for safer champion and boss utility in GMs.' if "Leviathan's Breath" in owned_set else f'- Replace **{power or "current heavy"}** with **Thunderlord** for easier, lower-friction GM damage.' if 'Thunderlord' in owned_set else '- No clear owned GM heavy upgrade detected.')
    else: lines.append(f'- Keep **{power}**. It is already in your safe-GM heavy pool.')
    if legs == 'Lucky Pants':
        if "Gyrfalcon's Hauberk" in owned_set: lines.append("- Replace **Lucky Pants** with **Gyrfalcon's Hauberk** when survivability and invis loop matter more than hand-cannon burst.")
        elif "Cyrtarachne's Facade" in owned_set: lines.append("- Replace **Lucky Pants** with **Cyrtarachne's Facade** when you need a safer DR-oriented Hunter shell.")
    lines.extend(['', '## Boss DPS Replacements'])
    if kinetic not in {"Izanagi's Burden", 'Witherhoard', 'Outbreak Perfected'} and "Izanagi's Burden" in owned_set: lines.append(f'- For boss damage, replace **{kinetic or "current kinetic"}** with **Izanagi\'s Burden** for real swap burst.')
    if energy not in {'Choir of One', 'Outbreak Perfected', 'Divinity', 'Still Hunt'}:
        if 'Still Hunt' in owned_set: lines.append(f'- For Hunter boss DPS, replace **{energy or "current energy"}** with **Still Hunt** when precision phases reward it.')
        elif 'Choir of One' in owned_set: lines.append(f'- For more direct burst, replace **{energy or "current energy"}** with **Choir of One**.')
    if power not in {"Dragon's Breath", 'Gjallarhorn', 'Microcosm', "Finality's Auger", "Leviathan's Breath", 'Thunderlord'} and "Dragon's Breath" in owned_set: lines.append(f'- For boss DPS, replace **{power or "current heavy"}** with **Dragon\'s Breath** unless the encounter specifically prefers a different heavy.')
    lines.extend(['', '## Farm If No Owned Upgrade Feels Right'])
    lines.extend([f'- **{item}**: {reason}' for item, reason in EXPECTED_CHASE[:3] if item not in owned_set])
    return '\n'.join(lines)


def build_stat_optimization(current: dict[str, str]) -> tuple[str, dict]:
    lines = ['# Stat Optimization', '']
    if not current: return '\n'.join(lines + ['- No Equipped Hunter loadout found, so stat optimization could not be calculated.']), {}
    profile_key, profile_label = choose_stat_profile(current)
    lines.extend(['## Recommended Profile', f'- **{profile_label}**', '', '## Current vs Target', ''])
    _, advice, detailed = stat_recommendations(current)
    lines.extend([f"- **{stat}**: current {detailed[stat]['current']:.0f} | target {detailed[stat]['target_low']:.0f}-{detailed[stat]['target_high']:.0f}" for stat in STAT_DISPLAY_ORDER])
    lines.extend(['', '## Recommendations', *advice])
    export_payload = {'profile_key': profile_key, 'profile_label': profile_label, 'current_loadout': current, 'targets': detailed, 'recommendations': advice}
    return '\n'.join(lines), export_payload


def choose_gm_build(owned_set: set[str]) -> dict[str, str]:
    kinetic = 'Buried Bloodline' if 'Buried Bloodline' in owned_set else 'Witherhoard' if 'Witherhoard' in owned_set else 'Arbalest' if 'Arbalest' in owned_set else 'No clear pick'
    energy = 'Le Monarque' if 'Le Monarque' in owned_set else 'Outbreak Perfected' if 'Outbreak Perfected' in owned_set else 'Graviton Lance' if 'Graviton Lance' in owned_set else 'Choir of One' if 'Choir of One' in owned_set else 'No clear pick'
    heavy = "Leviathan's Breath" if "Leviathan's Breath" in owned_set else 'Thunderlord' if 'Thunderlord' in owned_set else "Dragon's Breath" if "Dragon's Breath" in owned_set else 'No clear pick'
    armor = "Gyrfalcon's Hauberk" if "Gyrfalcon's Hauberk" in owned_set else "Cyrtarachne's Facade" if "Cyrtarachne's Facade" in owned_set else 'Orpheus Rig' if 'Orpheus Rig' in owned_set else "Assassin's Cowl" if "Assassin's Cowl" in owned_set else 'Wormhusk Crown' if 'Wormhusk Crown' in owned_set else 'No clear pick'
    subclass = 'Nightstalker' if armor in {"Gyrfalcon's Hauberk", 'Orpheus Rig', 'Graviton Forfeit'} else 'Prismatic Hunter' if armor == "Cyrtarachne's Facade" else 'Arcstrider' if armor == "Assassin's Cowl" else 'Nightstalker'
    return {'kinetic': kinetic, 'energy': energy, 'heavy': heavy, 'armor_exotic': armor, 'subclass': subclass}


def build_build_recommendation(owned_set: set[str], current: dict[str, str], stat_payload: dict) -> tuple[str, dict]:
    build = choose_gm_build(owned_set)
    lines = ['# Build Recommendation (GM)', '', f"- Kinetic: **{build['kinetic']}**", f"- Energy: **{build['energy']}**", f"- Heavy: **{build['heavy']}**", f"- Exotic Armor: **{build['armor_exotic']}**", f"- Subclass: **{build['subclass']}**", '']
    lines.append('## Why it works')
    reasons = []
    if build['kinetic'] == 'Buried Bloodline': reasons.append('- Buried Bloodline gives you one of the safest utility/survivability shells you own.')
    elif build['kinetic'] == 'Witherhoard': reasons.append('- Witherhoard gives passive damage and safe area control.')
    if build['energy'] == 'Le Monarque': reasons.append('- Le Monarque gives safe ranged pressure and strong overload coverage.')
    elif build['energy'] == 'Outbreak Perfected': reasons.append('- Outbreak Perfected gives reliable primary damage and excellent ammo economy.')
    if build['heavy'] == "Leviathan's Breath": reasons.append("- Leviathan's Breath is one of your safest heavy anchors for champion and boss utility.")
    elif build['heavy'] == 'Thunderlord': reasons.append('- Thunderlord is low-friction, easy damage with good ad-control value.')
    if build['armor_exotic'] == "Gyrfalcon's Hauberk": reasons.append('- Gyrfalcon gives a practical invis/volatile loop that fits blind endgame better than greedier shells.')
    elif build['armor_exotic'] == "Cyrtarachne's Facade": reasons.append('- Cyrtarachne helps stabilize survivability through DR instead of stat greed.')
    lines.extend(reasons[:3] or ['- No strong GM recommendation could be assembled yet.'])
    if stat_payload:
        lines.extend(['', '## Target Stats'])
        targets = stat_payload.get('targets', {})
        for stat in STAT_DISPLAY_ORDER:
            if stat in targets:
                lines.append(f"- **{stat}**: {int(targets[stat]['target_low'])}-{int(targets[stat]['target_high'])}")
    export_payload = {
        'profile': 'gm', 'activity': 'GM', 'class': 'Hunter', 'weapons': [build['kinetic'], build['energy'], build['heavy']],
        'armor_exotic': build['armor_exotic'], 'subclass': build['subclass'], 'stat_targets': stat_payload.get('targets', {}),
        'tags': ['gm', 'hunter', 'survivability-first'], 'source_current_loadout': current, 'notes': reasons[:3],
    }
    return '\n'.join(lines), export_payload


def build_dim_payload(build_payload: dict, stat_payload: dict) -> dict:
    return {
        'app': 'Warmind', 'engine': 'Destiny Intelligence Engine', 'profile': build_payload.get('profile', 'gm'), 'activity': build_payload.get('activity', 'GM'),
        'class': build_payload.get('class', 'Hunter'), 'subclass': build_payload.get('subclass', 'Nightstalker'), 'weapons': build_payload.get('weapons', []),
        'armor_exotic': build_payload.get('armor_exotic', 'Unknown'), 'stat_targets': build_payload.get('stat_targets', stat_payload.get('targets', {})),
        'tags': build_payload.get('tags', []), 'notes': build_payload.get('notes', []) + ['Warmind export scaffold', 'DIM import string not wired yet'],
        'source': {'build_recommendation': 'Build Recommendation.md', 'stat_optimization': 'Stat Optimization.md'},
    }


def normalize_slot_label(slot_text: str) -> str:
    value = str(slot_text).strip().lower()
    if 'kinetic' in value: return 'kinetic'
    if 'energy' in value: return 'energy'
    if 'power' in value or 'heavy' in value: return 'power'
    if 'helmet' in value: return 'helmet'
    if 'gauntlet' in value or 'glove' in value: return 'gauntlets'
    if 'chest' in value: return 'chest'
    if 'leg' in value: return 'legs'
    if 'cloak' in value or 'class armor' in value or 'class item' in value: return 'class_item'
    return 'unknown'


def detect_item_columns(df: pd.DataFrame) -> dict[str, str | None]:
    return {
        'name': first_col(df, ['Name', 'Item Name']),
        'id': first_col(df, ['Id', 'Item Id', 'Instance Id', 'Item Instance Id']),
        'hash': first_col(df, ['Hash', 'Item Hash']),
        'bucket': first_col(df, ['Bucket', 'Bucket Name', 'Slot']),
        'equipped': first_col(df, ['Equipped', 'Is Equipped']),
        'owner': first_col(df, ['Owner', 'Character']),
        'rarity': first_col(df, ['Rarity', 'Tier Type Name']),
    }


def build_inventory_index(df: pd.DataFrame) -> dict[str, list[dict]]:
    cols = detect_item_columns(df)
    name_col = cols['name']
    if not name_col:
        return {}
    index: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        name = str(row.get(name_col, '')).strip()
        if not name:
            continue
        record = {
            'name': name,
            'id': str(row.get(cols['id'], '')).strip() if cols['id'] else None,
            'hash': str(row.get(cols['hash'], '')).strip() if cols['hash'] else None,
            'bucket': normalize_slot_label(str(row.get(cols['bucket'], ''))) if cols['bucket'] else 'unknown',
            'equipped': str(row.get(cols['equipped'], '')).strip().lower() in {'true', 'yes', '1', 'equipped'} if cols['equipped'] else False,
            'owner': str(row.get(cols['owner'], '')).strip() if cols['owner'] else None,
            'rarity': str(row.get(cols['rarity'], '')).strip() if cols['rarity'] else None,
        }
        index.setdefault(name, []).append(record)
    return index


def resolve_item(name: str, inventory_index: dict[str, list[dict]], preferred_bucket: str | None = None) -> dict:
    matches = inventory_index.get(name, [])
    if preferred_bucket:
        bucket_matches = [m for m in matches if m.get('bucket') == preferred_bucket]
        if bucket_matches:
            matches = bucket_matches
    if not matches:
        return {'name': name, 'hash': None, 'id': None, 'resolved': False, 'bucket': preferred_bucket or 'unknown'}
    equipped_matches = [m for m in matches if m.get('equipped')]
    chosen = equipped_matches[0] if equipped_matches else matches[0]
    return {
        'name': name,
        'hash': chosen.get('hash') or None,
        'id': chosen.get('id') or None,
        'resolved': bool(chosen.get('hash') or chosen.get('id')),
        'bucket': chosen.get('bucket') or preferred_bucket or 'unknown',
        'owner': chosen.get('owner') or None,
    }


def build_dim_loadout_scaffold(dim_payload: dict, inventory_index: dict[str, list[dict]]) -> dict:
    weapons = dim_payload.get('weapons', [])
    resolved_items = [
        resolve_item(weapons[0], inventory_index, 'kinetic') if len(weapons) > 0 else None,
        resolve_item(weapons[1], inventory_index, 'energy') if len(weapons) > 1 else None,
        resolve_item(weapons[2], inventory_index, 'power') if len(weapons) > 2 else None,
        resolve_item(dim_payload.get('armor_exotic', ''), inventory_index, 'legs'),
    ]
    items = []
    for entry in resolved_items:
        if not entry:
            continue
        items.append({
            'name': entry['name'],
            'bucket': entry['bucket'],
            'hash': entry['hash'],
            'id': entry['id'],
            'resolved': entry['resolved'],
        })
    fully_resolved = all(item.get('hash') or item.get('id') for item in items)
    return {
        'app': 'Warmind',
        'engine': 'Destiny Intelligence Engine',
        'type': 'dim-loadout-scaffold',
        'name': f"Warmind {dim_payload.get('activity', 'GM')} Loadout",
        'classType': dim_payload.get('class', 'Hunter'),
        'subclass': dim_payload.get('subclass', 'Nightstalker'),
        'items': items,
        'parameters': {
            'activity': dim_payload.get('activity', 'GM'),
            'profile': dim_payload.get('profile', 'gm'),
            'statTargets': dim_payload.get('stat_targets', {}),
            'tags': dim_payload.get('tags', []),
        },
        'status': {
            'inventoryResolutionAttempted': True,
            'fullyResolved': fully_resolved,
            'resolvedItemCount': sum(1 for item in items if item.get('resolved')),
            'totalItemCount': len(items),
            'dimLoadoutSchemaReady': fully_resolved,
            'shareLinkReady': False,
        },
        'notes': dim_payload.get('notes', []),
    }


def build_dim_export_md(dim_payload: dict) -> str:
    lines = ['# DIM Export', '', '## Warmind Package']
    for label, value in [('App', dim_payload.get('app', 'Warmind')), ('Engine', dim_payload.get('engine', 'Destiny Intelligence Engine')), ('Profile', dim_payload.get('profile', 'unknown')), ('Activity', dim_payload.get('activity', 'unknown')), ('Class', dim_payload.get('class', 'unknown')), ('Subclass', dim_payload.get('subclass', 'unknown'))]:
        lines.append(f'- {label}: **{value}**')
    lines.extend(['', '## Weapons'])
    lines.extend([f'- **{weapon}**' for weapon in dim_payload.get('weapons', [])])
    lines.extend(['', '## Armor', f"- Exotic Armor: **{dim_payload.get('armor_exotic', 'unknown')}**", '', '## Target Stats'])
    for stat in STAT_DISPLAY_ORDER:
        target = dim_payload.get('stat_targets', {}).get(stat)
        if target:
            lines.append(f"- **{stat}**: {int(target['target_low'])}-{int(target['target_high'])}")
    lines.extend(['', '## Notes'])
    lines.extend([note if str(note).startswith('- ') else f'- {note}' for note in dim_payload.get('notes', [])])
    lines.extend(['', '## Export Status', '- This is a Warmind DIM-focused export scaffold, ready for later conversion into a true DIM import string.', '- Item hashes and socket/mod packaging are partially wired through inventory resolution attempts.'])
    return '\n'.join(lines)


def build_dim_loadout_md(loadout_payload: dict) -> str:
    lines = ['# DIM Loadout Scaffold', '']
    lines.append(f"- Name: **{loadout_payload.get('name', 'Warmind Loadout')}**")
    lines.append(f"- Class: **{loadout_payload.get('classType', 'Hunter')}**")
    lines.append(f"- Subclass: **{loadout_payload.get('subclass', 'unknown')}**")
    lines.extend(['', '## Resolved Items'])
    for item in loadout_payload.get('items', []):
        lines.append(f"- **{item.get('bucket')}**: {item.get('name')} | hash: {item.get('hash')} | id: {item.get('id')} | resolved: {item.get('resolved')}")
    lines.extend(['', '## Status'])
    for key, value in loadout_payload.get('status', {}).items():
        lines.append(f'- {key}: **{value}**')
    lines.extend(['', '## Parameters'])
    params = loadout_payload.get('parameters', {})
    lines.append(f"- Activity: **{params.get('activity', 'unknown')}**")
    lines.append(f"- Profile: **{params.get('profile', 'unknown')}**")
    lines.append(f"- Tags: **{', '.join(params.get('tags', []))}**")
    lines.extend(['', '## Next Wiring Needed'])
    if loadout_payload.get('status', {}).get('fullyResolved'):
        lines.append('- Item resolution succeeded for all core pieces. Next step is mapping to a true DIM loadout/share document.')
    else:
        lines.append('- Some items still need live hash or instance-id resolution from richer inventory/Bungie sources.')
    lines.append('- Share-link creation is not wired yet.')
    return '\n'.join(lines)


def build_set_bonus_report(armor_df: pd.DataFrame, type_col: str | None, owner_col: str | None) -> str:
    if not type_col: return '# Set Bonus Candidates\n\n- Structured set-bonus detection is not wired yet.'
    armor_types = armor_df[armor_df[type_col].astype(str).str.contains('Helmet|Gauntlets|Chest|Leg|Cloak|Bond|Mark', case=False, regex=True, na=False)].copy(); owner_counts = {}
    if owner_col and not armor_types.empty:
        for _, row in armor_types.iterrows():
            owner = str(row.get(owner_col, '')).strip() or 'Unknown'; owner_counts[owner] = owner_counts.get(owner, 0) + 1
    lines = ['# Set Bonus Candidates', '', '## Current Status', '- Structured set-bonus detection is not wired yet.']
    if owner_counts:
        lines.extend(['', '## Armor Counts By Owner']); lines.extend([f'- {owner}: {count}' for owner, count in sorted(owner_counts.items())])
    return '\n'.join(lines)


def generate_reports(weapons: Path, armor: Path, loadouts: Path | None, output_dir: Path, use_bungie: bool) -> None:
    load_env_file()
    df_w = pd.read_csv(weapons).fillna(''); df_a = pd.read_csv(armor).fillna(''); df = pd.concat([df_w, df_a], ignore_index=True).fillna(''); ldf = pd.read_csv(loadouts).fillna('') if loadouts and loadouts.exists() else None
    inventory_index = build_inventory_index(df)
    output_dir.mkdir(parents=True, exist_ok=True)
    name_col = first_col(df, ['Name', 'Item Name']); rarity_col = first_col(df, ['Rarity', 'Tier Type Name']); type_col = first_col(df, ['Type', 'Item Type']); owner_col = first_col(df, ['Owner', 'Character'])
    write(output_dir / 'manifest_summary.md', f'# Summary\n\nTotal Items: {len(df)}')
    if use_bungie:
        key = os.getenv('BUNGIE_API_KEY', '').strip(); write(output_dir / 'bungie_status.md', f"Bungie API Enabled: {'YES' if key else 'NO KEY'}")
    if not name_col or not rarity_col:
        write(output_dir / 'Owned Meta.md', '# Owned Meta\n\nCould not detect required DIM columns.'); return
    exotics = df[df[rarity_col].astype(str).str.lower() == 'exotic'].copy(); owned_unique = dedupe_names(exotics[name_col]); owned_set = set(owned_unique); current_hunter = detect_current_hunter_loadout(ldf)
    stat_md, stat_payload = build_stat_optimization(current_hunter); build_md, build_payload = build_build_recommendation(owned_set, current_hunter, stat_payload)
    dim_payload = build_dim_payload(build_payload, stat_payload); dim_loadout = build_dim_loadout_scaffold(dim_payload, inventory_index)
    write(output_dir / 'Owned Meta.md', build_owned_meta(owned_unique))
    write(output_dir / 'Missing Meta.md', build_missing_meta(owned_set))
    write(output_dir / 'Farm Next.md', build_missing_meta(owned_set, '# Farm Next'))
    write(output_dir / 'GM Meta.md', build_gm_meta(owned_set, current_hunter))
    write(output_dir / 'Champion Coverage.md', build_champion_coverage(owned_set))
    write(output_dir / 'Avoid This.md', build_avoid_this(current_hunter, owned_set))
    write(output_dir / 'DPS.md', build_dps_report(owned_set))
    write(output_dir / 'Replacement.md', build_replacement_report(owned_set, current_hunter))
    write(output_dir / 'Stat Optimization.md', stat_md)
    write(output_dir / 'Build Recommendation.md', build_md)
    write(output_dir / 'DIM Export.md', build_dim_export_md(dim_payload))
    write(output_dir / 'DIM Loadout Scaffold.md', build_dim_loadout_md(dim_loadout))
    write(output_dir / 'Set Bonus Candidates.md', build_set_bonus_report(df, type_col, owner_col))
    (output_dir / 'dim_export.json').write_text(json.dumps(dim_payload, indent=2), encoding='utf-8')
    (output_dir / 'dim_loadout_scaffold.json').write_text(json.dumps(dim_loadout, indent=2), encoding='utf-8')
    canonical_payload = {'app': 'Warmind', 'engine': 'Destiny Intelligence Engine', 'stat_optimization': stat_payload, 'build_recommendation': build_payload, 'dim_export': dim_payload, 'dim_loadout_scaffold': dim_loadout}
    (output_dir / 'recommendation_export.json').write_text(json.dumps(canonical_payload, indent=2), encoding='utf-8')
    if ldf is not None:
        lines = ['# Loadouts Summary', '', f'Count: **{len(ldf)}**', '']
        for idx, row in ldf.head(25).iterrows():
            lines.append(f'## Loadout {idx + 1}')
            for col in ldf.columns:
                value = str(row[col]).strip()
                if value: lines.append(f'- {col}: {value}')
            lines.append('')
        write(output_dir / 'Loadouts Summary.md', '\n'.join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description='Warmind Destiny Intelligence Engine Phase 3.9')
    parser.add_argument('--weapons', required=True); parser.add_argument('--armor', required=True); parser.add_argument('--loadouts', required=False); parser.add_argument('--use-bungie', action='store_true'); parser.add_argument('--output-dir', default='output')
    args = parser.parse_args()
    generate_reports(weapons=Path(args.weapons), armor=Path(args.armor), loadouts=Path(args.loadouts) if args.loadouts else None, output_dir=Path(args.output_dir), use_bungie=args.use_bungie)


if __name__ == '__main__':
    main()
