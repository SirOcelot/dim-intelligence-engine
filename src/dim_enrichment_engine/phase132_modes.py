from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

MODE_MAP = {
    "safe": {
        "issue": "dying_too_much",
        "label": "Safety-first adaptation",
        "description": "Prioritize survivability, stability, and lower-risk execution.",
    },
    "aggressive": {
        "issue": "boss_damage_low",
        "label": "Aggressive damage adaptation",
        "description": "Prioritize damage output and higher-ceiling pressure.",
    },
    "comfort": {
        "issue": "too_hard_to_execute",
        "label": "Comfort adaptation",
        "description": "Prioritize ease of use and lower-friction gameplay.",
    },
    "anti-champion": {
        "issue": "champion_failures",
        "label": "Anti-champion adaptation",
        "description": "Prioritize reliable champion coverage and safer control.",
    },
    "economy": {
        "issue": "ammo_starved",
        "label": "Ammo-economy adaptation",
        "description": "Prioritize ammo stability and sustainable output.",
    },
}

ISSUE_PROFILES = {
    "dying_too_much": {
        "profile": "survivability",
        "weights": {"survivability": 1.35, "dps": 0.85, "ease": 1.10},
        "notes": [
            "Increase survivability weighting and reduce greedier damage bias.",
            "Prefer safer exotic armor and stronger sustain or DR loops.",
            "Raise Health and Class priority before adding more Weapons.",
        ],
    },
    "ammo_starved": {
        "profile": "gm",
        "weights": {"survivability": 1.05, "dps": 0.90, "ease": 1.20},
        "notes": [
            "Penalize heavy-dependent options and reward stable primary economy.",
            "Favor lower-friction damage tools that do not collapse without ammo.",
            "Improve ease-of-use to reduce execution waste.",
        ],
    },
    "boss_damage_low": {
        "profile": "dps",
        "weights": {"survivability": 0.90, "dps": 1.35, "ease": 0.95},
        "notes": [
            "Increase DPS weighting and allow more aggressive burst picks.",
            "Raise Weapons and Super target emphasis while preserving a minimum survivability floor.",
            "Prefer stronger burst or sustained damage tools over comfort picks.",
        ],
    },
    "champion_failures": {
        "profile": "gm",
        "weights": {"survivability": 1.10, "dps": 0.85, "ease": 1.00},
        "notes": [
            "Hard-prioritize explicit champion coverage before comfort or damage upgrades.",
            "Unsafe swaps that remove champion answers should be penalized heavily.",
            "Maintain long-range safety where possible.",
        ],
    },
    "too_hard_to_execute": {
        "profile": "survivability",
        "weights": {"survivability": 1.05, "dps": 0.90, "ease": 1.35},
        "notes": [
            "Favor simpler, lower-friction tools and passive damage options.",
            "Penalize high-maintenance rotations and greedier shells.",
            "Preserve enough survivability to stabilize imperfect execution.",
        ],
    },
}

BASE_STAT_PROFILES = {
    "gm": {"Health": (90, 110), "Grenade": (80, 120), "Class": (70, 100), "Weapons": (90, 120), "Super": (20, 60), "Melee": (0, 50)},
    "dps": {"Health": (60, 90), "Grenade": (40, 90), "Class": (30, 70), "Weapons": (120, 170), "Super": (60, 110), "Melee": (0, 40)},
    "survivability": {"Health": (95, 120), "Grenade": (70, 110), "Class": (85, 115), "Weapons": (80, 115), "Super": (20, 50), "Melee": (0, 40)},
}
STAT_ORDER = ["Health", "Grenade", "Class", "Weapons", "Super", "Melee"]

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

SCORES = {
    "survivability": {
        "Buried Bloodline": 2.6, "Witherhoard": 1.0, "Arbalest": 0.7,
        "Le Monarque": 1.6, "Outbreak Perfected": 1.0, "Graviton Lance": 1.2, "Choir of One": 0.8, "Trinity Ghoul": 0.8,
        "Leviathan's Breath": 1.5, "Thunderlord": 0.8, "Dragon's Breath": 0.7, "Gjallarhorn": 0.6, "Microcosm": 0.7,
        "Gyrfalcon's Hauberk": 2.0, "Cyrtarachne's Facade": 2.1, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.8, "Wormhusk Crown": 1.6, "Lucky Pants": 0.6,
    },
    "dps": {
        "Buried Bloodline": 1.2, "Witherhoard": 1.8, "Arbalest": 0.9,
        "Le Monarque": 1.0, "Outbreak Perfected": 1.5, "Graviton Lance": 1.1, "Choir of One": 1.8, "Trinity Ghoul": 0.7,
        "Leviathan's Breath": 1.6, "Thunderlord": 1.5, "Dragon's Breath": 1.9, "Gjallarhorn": 1.8, "Microcosm": 1.4,
        "Gyrfalcon's Hauberk": 1.0, "Cyrtarachne's Facade": 0.6, "Orpheus Rig": 1.1, "Assassin's Cowl": 0.7, "Wormhusk Crown": 0.5, "Lucky Pants": 1.7,
    },
    "ease": {
        "Buried Bloodline": 1.5, "Witherhoard": 1.8, "Arbalest": 1.0,
        "Le Monarque": 1.3, "Outbreak Perfected": 1.6, "Graviton Lance": 1.7, "Choir of One": 1.0, "Trinity Ghoul": 1.8,
        "Leviathan's Breath": 1.1, "Thunderlord": 1.9, "Dragon's Breath": 1.2, "Gjallarhorn": 1.3, "Microcosm": 1.3,
        "Gyrfalcon's Hauberk": 1.2, "Cyrtarachne's Facade": 1.5, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.0, "Wormhusk Crown": 1.8, "Lucky Pants": 0.9,
    },
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


def dedupe_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        name = norm(value)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


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


def score_build(build: dict[str, str], stat_targets: dict[str, dict[str, float]], profile: str, issue: str | None = None) -> dict[str, float]:
    weights = ISSUE_PROFILES.get(issue or "", {}).get("weights", {"survivability": 1.0, "dps": 1.0, "ease": 1.0})
    health = stat_targets["Health"]["current"]
    grenade = stat_targets["Grenade"]["current"]
    class_stat = stat_targets["Class"]["current"]
    weapons_stat = stat_targets["Weapons"]["current"]
    super_stat = stat_targets["Super"]["current"]
    items = [build.get("kinetic", ""), build.get("energy", ""), build.get("power", ""), build.get("armor_exotic", "")]

    survivability = 3.0 + min(3.0, health / 40.0) + min(2.0, class_stat / 50.0) + min(1.2, grenade / 100.0)
    dps = 3.0 + min(3.0, weapons_stat / 50.0) + min(1.8, super_stat / 70.0) + min(0.8, grenade / 120.0)
    ease = 4.0 + min(1.5, health / 80.0) + min(1.0, class_stat / 90.0)

    for item in items:
        survivability += SCORES["survivability"].get(item, 0.0)
        dps += SCORES["dps"].get(item, 0.0)
        ease += SCORES["ease"].get(item, 0.0)

    survivability *= weights["survivability"]
    dps *= weights["dps"]
    ease *= weights["ease"]

    result = {
        "survivability": clamp_1_10(survivability),
        "dps": clamp_1_10(dps),
        "ease_of_use": clamp_1_10(ease),
    }
    result["overall"] = clamp_1_10((result["survivability"] * 0.4) + (result["dps"] * 0.35) + (result["ease_of_use"] * 0.25))
    return result


def adjust_stat_targets(current: dict[str, str], adaptive_profile: str, issue: str) -> dict[str, dict[str, float]]:
    base = BASE_STAT_PROFILES[adaptive_profile]
    targets: dict[str, dict[str, float]] = {}
    current_map = {
        "Health": to_float(current.get("health", 0)),
        "Grenade": to_float(current.get("grenade", 0)),
        "Class": to_float(current.get("class_stat", 0)),
        "Weapons": to_float(current.get("weapons_stat", 0)),
        "Super": to_float(current.get("super", 0)),
        "Melee": to_float(current.get("melee", 0)),
    }
    for stat in STAT_ORDER:
        low, high = base[stat]
        if issue == "dying_too_much":
            if stat == "Health":
                low += 10; high += 10
            elif stat == "Class":
                low += 10; high += 10
            elif stat == "Weapons":
                low -= 10; high -= 10
        elif issue == "boss_damage_low":
            if stat == "Weapons":
                low += 10; high += 10
            elif stat == "Super":
                low += 10; high += 10
            elif stat == "Health":
                low -= 5; high -= 5
        elif issue == "ammo_starved":
            if stat == "Weapons":
                low -= 5; high -= 10
            elif stat == "Class":
                low += 5; high += 5
        elif issue == "too_hard_to_execute":
            if stat == "Class":
                low += 10; high += 10
            elif stat == "Weapons":
                low -= 5; high -= 5
        elif issue == "champion_failures":
            if stat == "Health":
                low += 5; high += 5
            elif stat == "Class":
                low += 5; high += 5
        targets[stat] = {"current": current_map[stat], "target_low": low, "target_high": high}
    return targets


def baseline_build_for_profile(owned: set[str], profile: str) -> dict[str, str]:
    priorities = CANDIDATE_PRIORITIES[profile]
    def first_owned(options: list[str]) -> str:
        for item in options:
            if item in owned:
                return item
        return "No clear pick"
    return {
        "kinetic": first_owned(priorities["kinetic"]),
        "energy": first_owned(priorities["energy"]),
        "power": first_owned(priorities["power"]),
        "armor_exotic": first_owned(priorities["armor_exotic"]),
        "subclass": "Nightstalker",
    }


def select_adaptive_build(owned: set[str], issue: str) -> dict[str, str]:
    adaptive_profile = ISSUE_PROFILES[issue]["profile"]
    build = baseline_build_for_profile(owned, adaptive_profile)
    if issue == "champion_failures":
        if "Le Monarque" in owned:
            build["energy"] = "Le Monarque"
        if "Leviathan's Breath" in owned:
            build["power"] = "Leviathan's Breath"
    if issue == "ammo_starved":
        if "Outbreak Perfected" in owned:
            build["energy"] = "Outbreak Perfected"
        if "Thunderlord" in owned:
            build["power"] = "Thunderlord"
    if issue == "dying_too_much":
        if "Buried Bloodline" in owned:
            build["kinetic"] = "Buried Bloodline"
        if "Cyrtarachne's Facade" in owned:
            build["armor_exotic"] = "Cyrtarachne's Facade"
    if issue == "boss_damage_low":
        if "Witherhoard" in owned:
            build["kinetic"] = "Witherhoard"
        if "Choir of One" in owned:
            build["energy"] = "Choir of One"
        if "Dragon's Breath" in owned:
            build["power"] = "Dragon's Breath"
        if "Lucky Pants" in owned:
            build["armor_exotic"] = "Lucky Pants"
    if issue == "too_hard_to_execute":
        if "Witherhoard" in owned:
            build["kinetic"] = "Witherhoard"
        if "Graviton Lance" in owned:
            build["energy"] = "Graviton Lance"
        if "Thunderlord" in owned:
            build["power"] = "Thunderlord"
        if "Wormhusk Crown" in owned:
            build["armor_exotic"] = "Wormhusk Crown"
    return build


def build_adaptation_reason(mode: str, issue: str, before: dict[str, str], after: dict[str, str]) -> list[str]:
    reasons = [MODE_MAP[mode]["description"], *ISSUE_PROFILES[issue]["notes"]]
    for slot in ["kinetic", "energy", "power", "armor_exotic"]:
        if before.get(slot) != after.get(slot):
            reasons.append(f"Changed {slot} from {before.get(slot)} to {after.get(slot)} to support {mode} mode.")
    return reasons


def compare_scores(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    delta = {k: round(after[k] - before[k], 1) for k in before.keys()}
    if delta["overall"] > 0.3:
        verdict = "Net adaptive improvement."
    elif delta["overall"] < -0.3:
        verdict = "Net adaptive downgrade."
    else:
        verdict = "Mostly sidegrade or situational shift."
    return {"delta": delta, "verdict": verdict}


def render_md(mode: str, issue: str, baseline_profile: str, adaptive_profile: str, before_build: dict[str, str], after_build: dict[str, str], before_scores: dict[str, float], after_scores: dict[str, float], comparison: dict[str, Any], reasons: list[str], targets: dict[str, dict[str, float]]) -> str:
    lines = [
        "# Warmind Adaptive Modes",
        "",
        f"- Mode: **{mode}**",
        f"- Issue Mapping: **{issue}**",
        f"- Baseline Profile: **{baseline_profile}**",
        f"- Adaptive Profile: **{adaptive_profile}**",
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
        "## After",
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
        "## Why Warmind Switched Modes",
    ]
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.extend(["", "## Mode Stat Targets"])
    for stat in STAT_ORDER:
        lines.append(f"- **{stat}**: current {targets[stat]['current']:.0f} | target {targets[stat]['target_low']:.0f}-{targets[stat]['target_high']:.0f}")
    lines.extend(["", "## Available Modes"])
    for key, data in MODE_MAP.items():
        lines.append(f"- **{key}**: {data['description']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 13.2 adaptive modes")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--mode", required=True, choices=sorted(MODE_MAP.keys()))
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

    baseline_profile = choose_baseline_profile(current)
    before_build = baseline_build_for_profile(owned, baseline_profile)

    issue = MODE_MAP[args.mode]["issue"]
    adaptive_profile = ISSUE_PROFILES[issue]["profile"]
    before_targets = adjust_stat_targets(current, baseline_profile, issue if baseline_profile == adaptive_profile else "champion_failures")
    after_targets = adjust_stat_targets(current, adaptive_profile, issue)
    after_build = select_adaptive_build(owned, issue)

    before_scores = score_build(before_build, before_targets, baseline_profile, None)
    after_scores = score_build(after_build, after_targets, adaptive_profile, issue)
    comparison = compare_scores(before_scores, after_scores)
    reasons = build_adaptation_reason(args.mode, issue, before_build, after_build)

    payload = {
        "mode": args.mode,
        "issue": issue,
        "baseline_profile": baseline_profile,
        "adaptive_profile": adaptive_profile,
        "before_build": before_build,
        "after_build": after_build,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "comparison": comparison,
        "adaptive_targets": after_targets,
        "reasons": reasons,
        "available_modes": MODE_MAP,
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase132_modes.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write(out / "Phase132 Modes.md", render_md(args.mode, issue, baseline_profile, adaptive_profile, before_build, after_build, before_scores, after_scores, comparison, reasons, after_targets))


if __name__ == "__main__":
    main()
