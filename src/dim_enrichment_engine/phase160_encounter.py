from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

STAT_ORDER = ["Health", "Grenade", "Class", "Weapons", "Super", "Melee"]

BASE_STAT_PROFILES = {
    "gm": {"Health": (90, 110), "Grenade": (80, 120), "Class": (70, 100), "Weapons": (90, 120), "Super": (20, 60), "Melee": (0, 50)},
    "dps": {"Health": (60, 90), "Grenade": (40, 90), "Class": (30, 70), "Weapons": (120, 170), "Super": (60, 110), "Melee": (0, 40)},
    "survivability": {"Health": (95, 120), "Grenade": (70, 110), "Class": (85, 115), "Weapons": (80, 115), "Super": (20, 50), "Melee": (0, 40)},
}

CANDIDATE_PRIORITIES = {
    "gm": {
        "kinetic": ["Buried Bloodline", "Witherhoard", "Arbalest"],
        "energy": ["Le Monarque", "Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"],
        "power": ["Leviathan's Breath", "Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"],
        "armor_exotic": ["Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Wormhusk Crown", "Lucky Pants"],
    },
    "dps": {
        "kinetic": ["Witherhoard", "Buried Bloodline", "Arbalest"],
        "energy": ["Choir of One", "Outbreak Perfected", "Le Monarque", "Graviton Lance", "Trinity Ghoul"],
        "power": ["Dragon's Breath", "Gjallarhorn", "Leviathan's Breath", "Thunderlord", "Microcosm"],
        "armor_exotic": ["Lucky Pants", "Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Wormhusk Crown"],
    },
    "survivability": {
        "kinetic": ["Buried Bloodline", "Witherhoard", "Arbalest"],
        "energy": ["Le Monarque", "Graviton Lance", "Outbreak Perfected", "Trinity Ghoul", "Choir of One"],
        "power": ["Leviathan's Breath", "Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"],
        "armor_exotic": ["Cyrtarachne's Facade", "Gyrfalcon's Hauberk", "Assassin's Cowl", "Wormhusk Crown", "Orpheus Rig", "Lucky Pants"],
    },
}

ITEM_TAGS = {
    "Buried Bloodline": {"safe_damage", "self_heal", "ammo_efficient", "anti-overload"},
    "Witherhoard": {"safe_damage", "dot", "burst_support", "ammo_efficient"},
    "Arbalest": {"long_range", "anti-barrier", "precision", "safe_damage"},
    "Le Monarque": {"long_range", "safe_damage", "anti-overload", "dot"},
    "Outbreak Perfected": {"long_range", "safe_damage", "sustained", "ammo_efficient"},
    "Graviton Lance": {"long_range", "safe_damage", "ease", "add_clear"},
    "Choir of One": {"burst", "mid_range", "dps"},
    "Trinity Ghoul": {"add_clear", "ease", "ammo_efficient", "anti-overload"},
    "Leviathan's Breath": {"long_range", "anti-unstoppable", "burst", "safe_damage"},
    "Thunderlord": {"sustained", "ease", "add_clear"},
    "Dragon's Breath": {"burst", "dot", "boss_damage"},
    "Gjallarhorn": {"burst", "boss_damage", "team_dps"},
    "Microcosm": {"sustained", "safe_damage", "boss_damage"},
    "Gyrfalcon's Hauberk": {"void_loop", "survivability", "volatile", "endgame_safe"},
    "Cyrtarachne's Facade": {"dr", "survivability", "endgame_safe", "comfort"},
    "Orpheus Rig": {"support", "tether", "team_value"},
    "Assassin's Cowl": {"self_heal", "survivability", "close_range"},
    "Wormhusk Crown": {"panic_heal", "survivability", "comfort"},
    "Lucky Pants": {"burst", "dps", "high_maintenance"},
}

SCORES = {
    "survivability": {"Buried Bloodline": 2.6, "Witherhoard": 1.0, "Arbalest": 0.7, "Le Monarque": 1.6, "Outbreak Perfected": 1.0, "Graviton Lance": 1.2, "Choir of One": 0.8, "Trinity Ghoul": 0.8, "Leviathan's Breath": 1.5, "Thunderlord": 0.8, "Dragon's Breath": 0.7, "Gjallarhorn": 0.6, "Microcosm": 0.7, "Gyrfalcon's Hauberk": 2.0, "Cyrtarachne's Facade": 2.1, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.8, "Wormhusk Crown": 1.6, "Lucky Pants": 0.6},
    "dps": {"Buried Bloodline": 1.2, "Witherhoard": 1.8, "Arbalest": 0.9, "Le Monarque": 1.0, "Outbreak Perfected": 1.5, "Graviton Lance": 1.1, "Choir of One": 1.8, "Trinity Ghoul": 0.7, "Leviathan's Breath": 1.6, "Thunderlord": 1.5, "Dragon's Breath": 1.9, "Gjallarhorn": 1.8, "Microcosm": 1.4, "Gyrfalcon's Hauberk": 1.0, "Cyrtarachne's Facade": 0.6, "Orpheus Rig": 1.1, "Assassin's Cowl": 0.7, "Wormhusk Crown": 0.5, "Lucky Pants": 1.7},
    "ease": {"Buried Bloodline": 1.5, "Witherhoard": 1.8, "Arbalest": 1.0, "Le Monarque": 1.3, "Outbreak Perfected": 1.6, "Graviton Lance": 1.7, "Choir of One": 1.0, "Trinity Ghoul": 1.8, "Leviathan's Breath": 1.1, "Thunderlord": 1.9, "Dragon's Breath": 1.2, "Gjallarhorn": 1.3, "Microcosm": 1.3, "Gyrfalcon's Hauberk": 1.2, "Cyrtarachne's Facade": 1.5, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.0, "Wormhusk Crown": 1.8, "Lucky Pants": 0.9},
}

ENCOUNTER_ARCHETYPES = {
    ("gm", "mixed"): {"profile": "gm", "survivability_weight": 1.25, "dps_weight": 0.95, "ease_weight": 1.05, "preferred_tags": {"safe_damage", "long_range", "ammo_efficient"}, "penalized_tags": {"high_maintenance", "close_range"}},
    ("gm", "boss"): {"profile": "gm", "survivability_weight": 1.20, "dps_weight": 1.05, "ease_weight": 1.00, "preferred_tags": {"long_range", "burst", "safe_damage"}, "penalized_tags": {"close_range"}},
    ("gm", "add-clear"): {"profile": "gm", "survivability_weight": 1.20, "dps_weight": 0.90, "ease_weight": 1.15, "preferred_tags": {"add_clear", "ammo_efficient", "safe_damage"}, "penalized_tags": {"high_maintenance"}},
    ("raid", "boss"): {"profile": "dps", "survivability_weight": 0.90, "dps_weight": 1.35, "ease_weight": 0.95, "preferred_tags": {"burst", "boss_damage", "team_dps"}, "penalized_tags": {"add_clear"}},
    ("raid", "mixed"): {"profile": "dps", "survivability_weight": 1.00, "dps_weight": 1.20, "ease_weight": 1.00, "preferred_tags": {"burst", "sustained", "support"}, "penalized_tags": {"close_range"}},
    ("dungeon", "boss"): {"profile": "survivability", "survivability_weight": 1.20, "dps_weight": 1.10, "ease_weight": 1.15, "preferred_tags": {"self_heal", "safe_damage", "boss_damage"}, "penalized_tags": {"team_dps"}},
    ("dungeon", "mixed"): {"profile": "survivability", "survivability_weight": 1.30, "dps_weight": 1.00, "ease_weight": 1.20, "preferred_tags": {"self_heal", "ammo_efficient", "safe_damage"}, "penalized_tags": {"high_maintenance"}},
    ("seasonal", "mixed"): {"profile": "gm", "survivability_weight": 1.05, "dps_weight": 1.00, "ease_weight": 1.15, "preferred_tags": {"ease", "ammo_efficient", "add_clear"}, "penalized_tags": {"high_maintenance"}},
}

RANGE_TAG_PREFERENCES = {
    "close": {"prefer": {"close_range", "burst", "self_heal"}, "penalize": {"long_range"}},
    "mid": {"prefer": {"safe_damage", "sustained"}, "penalize": set()},
    "long": {"prefer": {"long_range", "safe_damage", "precision"}, "penalize": {"close_range"}},
}

DAMAGE_WINDOW_PREFERENCES = {
    "burst": {"prefer": {"burst", "boss_damage"}, "penalize": {"sustained", "add_clear"}},
    "sustained": {"prefer": {"sustained", "dot", "ammo_efficient"}, "penalize": {"high_maintenance"}},
    "mixed": {"prefer": {"safe_damage", "sustained", "burst"}, "penalize": set()},
}

CHAMPION_ITEM_TAGS = {
    "barrier": {"anti-barrier"},
    "overload": {"anti-overload"},
    "unstoppable": {"anti-unstoppable"},
}


def first_col(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def norm(value: Any) -> str:
    return str(value).strip()


def to_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def clamp_1_10(value: float) -> float:
    return max(1.0, min(10.0, round(value, 1)))


def dedupe_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        name = norm(value)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def detect_current_hunter_loadout(loadouts_df: pd.DataFrame | None) -> dict[str, str]:
    if loadouts_df is None or loadouts_df.empty:
        return {}
    cols = {str(c).strip().lower(): c for c in loadouts_df.columns}
    class_col = cols.get("class type")
    name_col = cols.get("name")
    if not class_col or not name_col:
        return {}
    row = None
    for _, candidate in loadouts_df.iterrows():
        if norm(candidate.get(class_col)).lower() == "hunter" and "equipped hunter" in norm(candidate.get(name_col)).lower():
            row = candidate
            break
    if row is None:
        return {}
    mapping = {
        "kinetic": "equipped kinetic weapons",
        "energy": "equipped energy weapons",
        "power": "equipped power weapons",
        "legs": "equipped leg armor",
        "health": "health",
        "weapons_stat": "weapons",
        "grenade": "grenade",
        "class_stat": "class",
        "super": "super",
        "melee": "melee",
        "subclass": "subclass",
    }
    result: dict[str, str] = {}
    for out_key, in_key in mapping.items():
        col = cols.get(in_key)
        result[out_key] = norm(row.get(col)) if col else ""
    return result


def build_encounter_context(activity: str, encounter_type: str, range_band: str, damage_window: str, champions: list[str]) -> dict[str, Any]:
    activity_norm = activity.lower().strip()
    encounter_norm = encounter_type.lower().strip()
    profile = ENCOUNTER_ARCHETYPES.get((activity_norm, encounter_norm), ENCOUNTER_ARCHETYPES.get((activity_norm, "mixed"), ENCOUNTER_ARCHETYPES[("seasonal", "mixed")]))
    return {
        "activity": activity_norm,
        "encounter": encounter_norm,
        "range": range_band.lower().strip(),
        "damage_window": damage_window.lower().strip(),
        "champions": [c.strip().lower() for c in champions if c.strip()],
        "profile": profile,
    }


def choose_baseline_profile(current: dict[str, str]) -> str:
    weapons = to_float(current.get("weapons_stat", 0))
    health = to_float(current.get("health", 0))
    power = current.get("power", "")
    legs = current.get("legs", "")
    if legs == "Lucky Pants" or power in {"Dragon's Breath", "Gjallarhorn"} or weapons >= 140:
        return "dps"
    if health < 70 or current.get("kinetic", "") in {"Buried Bloodline", "Witherhoard"}:
        return "gm"
    return "survivability"


def baseline_build_for_profile(owned: set[str], profile: str) -> dict[str, str]:
    priorities = CANDIDATE_PRIORITIES[profile]
    def first_owned(options: list[str]) -> str:
        for item in options:
            if item in owned:
                return item
        return "No clear pick"
    return {"kinetic": first_owned(priorities["kinetic"]), "energy": first_owned(priorities["energy"]), "power": first_owned(priorities["power"]), "armor_exotic": first_owned(priorities["armor_exotic"]), "subclass": "Nightstalker"}


def adjust_stat_targets(current: dict[str, str], encounter_ctx: dict[str, Any]) -> dict[str, dict[str, float]]:
    profile_name = encounter_ctx["profile"]["profile"]
    base = BASE_STAT_PROFILES[profile_name]
    targets: dict[str, dict[str, float]] = {}
    current_map = {"Health": to_float(current.get("health", 0)), "Grenade": to_float(current.get("grenade", 0)), "Class": to_float(current.get("class_stat", 0)), "Weapons": to_float(current.get("weapons_stat", 0)), "Super": to_float(current.get("super", 0)), "Melee": to_float(current.get("melee", 0))}
    range_band = encounter_ctx["range"]
    damage_window = encounter_ctx["damage_window"]
    activity = encounter_ctx["activity"]

    for stat in STAT_ORDER:
        low, high = base[stat]
        if activity == "gm":
            if stat == "Health":
                low += 5; high += 5
            if stat == "Class":
                low += 5; high += 5
        if range_band == "long":
            if stat == "Weapons":
                low += 5; high += 5
            if stat == "Health":
                low += 5
        if damage_window == "burst":
            if stat == "Weapons":
                low += 10; high += 10
            if stat == "Super":
                low += 10; high += 10
        elif damage_window == "sustained":
            if stat == "Grenade":
                low += 5; high += 5
            if stat == "Class":
                low += 5; high += 5
        targets[stat] = {"current": current_map[stat], "target_low": low, "target_high": high}
    return targets


def champion_coverage(build: dict[str, str], encounter_ctx: dict[str, Any]) -> dict[str, list[str]]:
    items = [build.get("kinetic", ""), build.get("energy", ""), build.get("power", ""), build.get("armor_exotic", "")]
    item_tags = {item: ITEM_TAGS.get(item, set()) for item in items}
    coverage: dict[str, list[str]] = {}
    for champ in encounter_ctx["champions"]:
        needed = CHAMPION_ITEM_TAGS.get(champ, set())
        providers = [item for item, tags in item_tags.items() if tags & needed]
        coverage[champ] = providers
    return coverage


def encounter_tag_modifier(item: str, encounter_ctx: dict[str, Any]) -> tuple[float, list[str]]:
    tags = ITEM_TAGS.get(item, set())
    score = 0.0
    reasons: list[str] = []

    preferred = set(encounter_ctx["profile"].get("preferred_tags", set()))
    penalized = set(encounter_ctx["profile"].get("penalized_tags", set()))
    range_pref = RANGE_TAG_PREFERENCES.get(encounter_ctx["range"], {"prefer": set(), "penalize": set()})
    damage_pref = DAMAGE_WINDOW_PREFERENCES.get(encounter_ctx["damage_window"], {"prefer": set(), "penalize": set()})

    for tag in preferred:
        if tag in tags:
            score += 0.6
            reasons.append(f"fits encounter preference '{tag}' (+0.6)")
    for tag in penalized:
        if tag in tags:
            score -= 0.7
            reasons.append(f"clashes with encounter profile '{tag}' (-0.7)")
    for tag in range_pref["prefer"]:
        if tag in tags:
            score += 0.5
            reasons.append(f"fits range requirement '{tag}' (+0.5)")
    for tag in range_pref["penalize"]:
        if tag in tags:
            score -= 0.6
            reasons.append(f"weak for range requirement '{tag}' (-0.6)")
    for tag in damage_pref["prefer"]:
        if tag in tags:
            score += 0.5
            reasons.append(f"fits damage window '{tag}' (+0.5)")
    for tag in damage_pref["penalize"]:
        if tag in tags:
            score -= 0.5
            reasons.append(f"less ideal for damage window '{tag}' (-0.5)")
    return score, reasons


def choose_encounter_build(owned: set[str], encounter_ctx: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    profile_name = encounter_ctx["profile"]["profile"]
    priorities = CANDIDATE_PRIORITIES[profile_name]
    reasons: list[str] = []

    def best_owned(options: list[str]) -> str:
        best_name = "No clear pick"
        best_score = -999.0
        best_reason_local: list[str] = []
        for item in options:
            if item not in owned:
                continue
            base = 1.0
            mod, local_reasons = encounter_tag_modifier(item, encounter_ctx)
            total = base + mod
            if total > best_score:
                best_score = total
                best_name = item
                best_reason_local = local_reasons
        if best_name != "No clear pick":
            reasons.append(f"Selected {best_name} from encounter-aware ranking.")
            reasons.extend(best_reason_local[:2])
        return best_name

    build = {
        "kinetic": best_owned(priorities["kinetic"]),
        "energy": best_owned(priorities["energy"]),
        "power": best_owned(priorities["power"]),
        "armor_exotic": best_owned(priorities["armor_exotic"]),
        "subclass": "Nightstalker",
    }

    coverage = champion_coverage(build, encounter_ctx)
    for champ, providers in coverage.items():
        if providers:
            reasons.append(f"Champion coverage for {champ} provided by {', '.join(providers)}.")
        else:
            if champ == "barrier" and "Arbalest" in owned:
                build["kinetic"] = "Arbalest"
                reasons.append("Forced Arbalest to satisfy barrier coverage.")
            elif champ == "overload" and "Le Monarque" in owned:
                build["energy"] = "Le Monarque"
                reasons.append("Forced Le Monarque to satisfy overload coverage.")
            elif champ == "unstoppable" and "Leviathan's Breath" in owned:
                build["power"] = "Leviathan's Breath"
                reasons.append("Forced Leviathan's Breath to satisfy unstoppable coverage.")

    if encounter_ctx["activity"] == "raid" and encounter_ctx["encounter"] == "boss":
        if "Lucky Pants" in owned:
            build["armor_exotic"] = "Lucky Pants"
            reasons.append("Raid boss encounter biases toward Lucky Pants for burst damage.")
        if "Dragon's Breath" in owned and encounter_ctx["damage_window"] == "burst":
            build["power"] = "Dragon's Breath"
            reasons.append("Burst boss window biases toward Dragon's Breath.")
    if encounter_ctx["activity"] == "dungeon" and encounter_ctx["encounter"] in {"boss", "mixed"}:
        if "Buried Bloodline" in owned:
            build["kinetic"] = "Buried Bloodline"
            reasons.append("Dungeon solo context biases toward Buried Bloodline sustain.")
    if encounter_ctx["range"] == "long" and "Graviton Lance" in owned and build["energy"] == "Choir of One":
        build["energy"] = "Graviton Lance"
        reasons.append("Long-range constraint swapped Choir of One to Graviton Lance.")

    return build, reasons


def score_build(build: dict[str, str], stat_targets: dict[str, dict[str, float]], encounter_ctx: dict[str, Any]) -> dict[str, float]:
    health = stat_targets["Health"]["current"]
    grenade = stat_targets["Grenade"]["current"]
    class_stat = stat_targets["Class"]["current"]
    weapons_stat = stat_targets["Weapons"]["current"]
    super_stat = stat_targets["Super"]["current"]

    items = [build.get("kinetic", ""), build.get("energy", ""), build.get("power", ""), build.get("armor_exotic", "")]

    survivability = 3.0 + min(3.0, health / 40.0) + min(2.0, class_stat / 50.0) + min(1.2, grenade / 100.0)
    dps = 3.0 + min(3.0, weapons_stat / 50.0) + min(1.8, super_stat / 70.0) + min(0.8, grenade / 120.0)
    ease = 4.0 + min(1.5, health / 80.0) + min(1.0, class_stat / 90.0)

    encounter_mod = {"survivability": 0.0, "dps": 0.0, "ease": 0.0}
    for item in items:
        survivability += SCORES["survivability"].get(item, 0.0)
        dps += SCORES["dps"].get(item, 0.0)
        ease += SCORES["ease"].get(item, 0.0)
        mod, _ = encounter_tag_modifier(item, encounter_ctx)
        encounter_mod["survivability"] += max(0.0, mod * 0.4)
        encounter_mod["dps"] += mod * 0.5
        encounter_mod["ease"] += max(0.0, mod * 0.35)

    coverage = champion_coverage(build, encounter_ctx)
    missing_champs = [champ for champ, providers in coverage.items() if not providers]
    if missing_champs:
        survivability -= 1.2 * len(missing_champs)
        dps -= 0.8 * len(missing_champs)
        ease -= 0.5 * len(missing_champs)

    survivability += encounter_mod["survivability"]
    dps += encounter_mod["dps"]
    ease += encounter_mod["ease"]

    survivability *= encounter_ctx["profile"]["survivability_weight"]
    dps *= encounter_ctx["profile"]["dps_weight"]
    ease *= encounter_ctx["profile"]["ease_weight"]

    result = {
        "survivability": clamp_1_10(survivability),
        "dps": clamp_1_10(dps),
        "ease_of_use": clamp_1_10(ease),
    }
    result["overall"] = clamp_1_10((result["survivability"] * 0.4) + (result["dps"] * 0.35) + (result["ease_of_use"] * 0.25))
    result["missing_champion_count"] = float(len(missing_champs))
    return result


def compare_scores(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    delta = {k: round(after[k] - before[k], 1) for k in ["survivability", "dps", "ease_of_use", "overall"]}
    if delta["overall"] > 0.3:
        verdict = "Net encounter-aware improvement."
    elif delta["overall"] < -0.3:
        verdict = "Net encounter-aware downgrade."
    else:
        verdict = "Mostly sidegrade or situational shift."
    return {"delta": delta, "verdict": verdict}


def render_md(encounter_ctx: dict[str, Any], baseline_profile: str, before_build: dict[str, str], after_build: dict[str, str], before_scores: dict[str, float], after_scores: dict[str, float], comparison: dict[str, Any], reasons: list[str], targets: dict[str, dict[str, float]], coverage: dict[str, list[str]]) -> str:
    lines = [
        "# Warmind Encounter Intelligence",
        "",
        f"- Activity: **{encounter_ctx['activity']}**",
        f"- Encounter: **{encounter_ctx['encounter']}**",
        f"- Range: **{encounter_ctx['range']}**",
        f"- Damage Window: **{encounter_ctx['damage_window']}**",
        f"- Champions: **{', '.join(encounter_ctx['champions']) if encounter_ctx['champions'] else 'none'}**",
        f"- Baseline Profile: **{baseline_profile}**",
        f"- Encounter Profile: **{encounter_ctx['profile']['profile']}**",
        "",
        "## Before",
        f"- Kinetic: **{before_build['kinetic']}**",
        f"- Energy: **{before_build['energy']}**",
        f"- Power: **{before_build['power']}**",
        f"- Exotic Armor: **{before_build['armor_exotic']}**",
        f"- Survivability: **{before_scores['survivability']} / 10**",
        f"- DPS: **{before_scores['dps']} / 10**",
        f"- Ease of Use: **{before_scores['ease_of_use']} / 10**",
        f"- Overall: **{before_scores['overall']} / 10**",
        "",
        "## Encounter-Aware Build",
        f"- Kinetic: **{after_build['kinetic']}**",
        f"- Energy: **{after_build['energy']}**",
        f"- Power: **{after_build['power']}**",
        f"- Exotic Armor: **{after_build['armor_exotic']}**",
        f"- Survivability: **{after_scores['survivability']} / 10** ({comparison['delta']['survivability']:+.1f})",
        f"- DPS: **{after_scores['dps']} / 10** ({comparison['delta']['dps']:+.1f})",
        f"- Ease of Use: **{after_scores['ease_of_use']} / 10** ({comparison['delta']['ease_of_use']:+.1f})",
        f"- Overall: **{after_scores['overall']} / 10** ({comparison['delta']['overall']:+.1f})",
        f"- Verdict: **{comparison['verdict']}**",
        "",
        "## Champion Coverage",
    ]
    if coverage:
        for champ, providers in coverage.items():
            lines.append(f"- **{champ}**: {', '.join(providers) if providers else 'MISSING'}")
    else:
        lines.append("- No champion requirements provided.")
    lines.extend(["", "## Why Warmind Chose This Encounter Build"])
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.extend(["", "## Encounter-Aware Stat Targets"])
    for stat in STAT_ORDER:
        lines.append(f"- **{stat}**: current {targets[stat]['current']:.0f} | target {targets[stat]['target_low']:.0f}-{targets[stat]['target_high']:.0f}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 16 encounter-specific intelligence")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--activity", required=True, choices=["gm", "raid", "dungeon", "seasonal"])
    parser.add_argument("--encounter", required=True, choices=["boss", "add-clear", "mixed"])
    parser.add_argument("--range", dest="range_band", required=True, choices=["close", "mid", "long"])
    parser.add_argument("--damage", dest="damage_window", required=True, choices=["burst", "sustained", "mixed"])
    parser.add_argument("--champions", required=False, default="")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    df_w = pd.read_csv(args.weapons).fillna("")
    df_a = pd.read_csv(args.armor).fillna("")
    df = pd.concat([df_w, df_a], ignore_index=True).fillna("")
    ldf = pd.read_csv(args.loadouts).fillna("") if args.loadouts and Path(args.loadouts).exists() else None

    name_col = first_col(df, ["Name", "Item Name"])
    rarity_col = first_col(df, ["Rarity", "Tier Type Name"])
    if not name_col:
        raise SystemExit("Could not detect item name column.")

    exotics = df[df[rarity_col].astype(str).str.lower() == "exotic"].copy() if rarity_col else df.copy()
    owned = set(dedupe_names(exotics[name_col]))
    current = detect_current_hunter_loadout(ldf)

    champions = [x.strip() for x in args.champions.split(",") if x.strip()]
    encounter_ctx = build_encounter_context(args.activity, args.encounter, args.range_band, args.damage_window, champions)

    baseline_profile = choose_baseline_profile(current)
    before_build = baseline_build_for_profile(owned, baseline_profile)
    before_targets = adjust_stat_targets(current, build_encounter_context(args.activity, "mixed", args.range_band, "mixed", champions))
    after_targets = adjust_stat_targets(current, encounter_ctx)
    after_build, reasons = choose_encounter_build(owned, encounter_ctx)

    before_scores = score_build(before_build, before_targets, encounter_ctx)
    after_scores = score_build(after_build, after_targets, encounter_ctx)
    comparison = compare_scores(before_scores, after_scores)
    coverage = champion_coverage(after_build, encounter_ctx)

    payload = {
        "encounter_context": encounter_ctx,
        "baseline_profile": baseline_profile,
        "before_build": before_build,
        "after_build": after_build,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "comparison": comparison,
        "coverage": coverage,
        "targets": after_targets,
        "reasons": reasons,
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase160_encounter.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write(out / "Phase160 Encounter.md", render_md(encounter_ctx, baseline_profile, before_build, after_build, before_scores, after_scores, comparison, reasons, after_targets, coverage))


if __name__ == "__main__":
    main()
