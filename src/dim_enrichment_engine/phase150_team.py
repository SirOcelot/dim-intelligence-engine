from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

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

ITEM_TAGS = {
    "Buried Bloodline": {"safe_damage", "self_heal", "ammo_efficient", "anti-overload", "utility"},
    "Witherhoard": {"safe_damage", "dot", "burst_support", "ammo_efficient", "dps"},
    "Arbalest": {"long_range", "anti-barrier", "precision", "safe_damage", "utility"},
    "Le Monarque": {"long_range", "safe_damage", "anti-overload", "dot", "utility"},
    "Outbreak Perfected": {"long_range", "safe_damage", "sustained", "ammo_efficient", "dps"},
    "Graviton Lance": {"long_range", "safe_damage", "ease", "add_clear"},
    "Choir of One": {"burst", "mid_range", "dps"},
    "Trinity Ghoul": {"add_clear", "ease", "ammo_efficient", "anti-overload"},
    "Leviathan's Breath": {"long_range", "anti-unstoppable", "burst", "safe_damage", "utility"},
    "Thunderlord": {"sustained", "ease", "add_clear", "dps"},
    "Dragon's Breath": {"burst", "dot", "boss_damage", "dps"},
    "Gjallarhorn": {"burst", "boss_damage", "team_dps", "support_dps"},
    "Microcosm": {"sustained", "safe_damage", "boss_damage", "dps"},
    "Gyrfalcon's Hauberk": {"void_loop", "survivability", "volatile", "endgame_safe"},
    "Cyrtarachne's Facade": {"dr", "survivability", "endgame_safe", "comfort"},
    "Orpheus Rig": {"support", "tether", "team_value", "utility"},
    "Assassin's Cowl": {"self_heal", "survivability", "close_range"},
    "Wormhusk Crown": {"panic_heal", "survivability", "comfort"},
    "Lucky Pants": {"burst", "dps", "high_maintenance"},
}

TEAM_ROLE_PRIORITIES = {
    "support": {
        "needed_tags": {"utility", "support", "team_value", "anti-barrier", "anti-overload", "anti-unstoppable"},
        "preferred_profile": "gm",
        "armor_bias": ["Orpheus Rig", "Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Wormhusk Crown"],
    },
    "anti_champion": {
        "needed_tags": {"anti-barrier", "anti-overload", "anti-unstoppable", "utility"},
        "preferred_profile": "gm",
        "armor_bias": ["Cyrtarachne's Facade", "Gyrfalcon's Hauberk", "Orpheus Rig"],
    },
    "survivability": {
        "needed_tags": {"survivability", "self_heal", "safe_damage", "comfort"},
        "preferred_profile": "survivability",
        "armor_bias": ["Cyrtarachne's Facade", "Wormhusk Crown", "Assassin's Cowl", "Gyrfalcon's Hauberk"],
    },
    "dps": {
        "needed_tags": {"dps", "boss_damage", "burst", "team_dps"},
        "preferred_profile": "dps",
        "armor_bias": ["Lucky Pants", "Gyrfalcon's Hauberk", "Orpheus Rig"],
    },
}

ROLE_SCORE_BONUS = {
    "support": {"survivability": 1.1, "dps": 0.9, "ease": 1.0},
    "anti_champion": {"survivability": 1.1, "dps": 0.85, "ease": 1.0},
    "survivability": {"survivability": 1.25, "dps": 0.9, "ease": 1.1},
    "dps": {"survivability": 0.9, "dps": 1.25, "ease": 0.95},
}

BASE_STAT_PROFILES = {
    "gm": {"Health": (90, 110), "Grenade": (80, 120), "Class": (70, 100), "Weapons": (90, 120), "Super": (20, 60), "Melee": (0, 50)},
    "dps": {"Health": (60, 90), "Grenade": (40, 90), "Class": (30, 70), "Weapons": (120, 170), "Super": (60, 110), "Melee": (0, 40)},
    "survivability": {"Health": (95, 120), "Grenade": (70, 110), "Class": (85, 115), "Weapons": (80, 115), "Super": (20, 50), "Melee": (0, 40)},
}

SCORES = {
    "survivability": {"Buried Bloodline": 2.6, "Witherhoard": 1.0, "Arbalest": 0.7, "Le Monarque": 1.6, "Outbreak Perfected": 1.0, "Graviton Lance": 1.2, "Choir of One": 0.8, "Trinity Ghoul": 0.8, "Leviathan's Breath": 1.5, "Thunderlord": 0.8, "Dragon's Breath": 0.7, "Gjallarhorn": 0.6, "Microcosm": 0.7, "Gyrfalcon's Hauberk": 2.0, "Cyrtarachne's Facade": 2.1, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.8, "Wormhusk Crown": 1.6, "Lucky Pants": 0.6},
    "dps": {"Buried Bloodline": 1.2, "Witherhoard": 1.8, "Arbalest": 0.9, "Le Monarque": 1.0, "Outbreak Perfected": 1.5, "Graviton Lance": 1.1, "Choir of One": 1.8, "Trinity Ghoul": 0.7, "Leviathan's Breath": 1.6, "Thunderlord": 1.5, "Dragon's Breath": 1.9, "Gjallarhorn": 1.8, "Microcosm": 1.4, "Gyrfalcon's Hauberk": 1.0, "Cyrtarachne's Facade": 0.6, "Orpheus Rig": 1.1, "Assassin's Cowl": 0.7, "Wormhusk Crown": 0.5, "Lucky Pants": 1.7},
    "ease": {"Buried Bloodline": 1.5, "Witherhoard": 1.8, "Arbalest": 1.0, "Le Monarque": 1.3, "Outbreak Perfected": 1.6, "Graviton Lance": 1.7, "Choir of One": 1.0, "Trinity Ghoul": 1.8, "Leviathan's Breath": 1.1, "Thunderlord": 1.9, "Dragon's Breath": 1.2, "Gjallarhorn": 1.3, "Microcosm": 1.3, "Gyrfalcon's Hauberk": 1.2, "Cyrtarachne's Facade": 1.5, "Orpheus Rig": 1.3, "Assassin's Cowl": 1.0, "Wormhusk Crown": 1.8, "Lucky Pants": 0.9},
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
        "health": "health",
        "weapons_stat": "weapons",
        "grenade": "grenade",
        "class_stat": "class",
        "super": "super",
        "melee": "melee",
    }
    result: dict[str, str] = {}
    for out_key, in_key in mapping.items():
        col = cols.get(in_key)
        result[out_key] = norm(row.get(col)) if col else ""
    return result


def choose_baseline_profile(current: dict[str, str]) -> str:
    weapons = to_float(current.get("weapons_stat", 0))
    health = to_float(current.get("health", 0))
    if weapons >= 140:
        return "dps"
    if health < 70:
        return "gm"
    return "survivability"


def parse_team_context(team_roles: list[str], team_champions: list[str]) -> dict[str, Any]:
    normalized_roles = [r.strip().lower() for r in team_roles if r.strip()]
    normalized_champs = [c.strip().lower() for c in team_champions if c.strip()]
    present_support = any(r in {"support", "utility", "debuff"} for r in normalized_roles)
    present_dps = sum(1 for r in normalized_roles if r in {"dps", "boss", "damage"})
    present_survival = any(r in {"survivability", "safe", "tank"} for r in normalized_roles)
    champion_set = set(normalized_champs)

    missing = []
    if "barrier" not in champion_set:
        missing.append("barrier")
    if "overload" not in champion_set:
        missing.append("overload")
    if "unstoppable" not in champion_set:
        missing.append("unstoppable")

    if missing:
        recommended_role = "anti_champion"
    elif not present_support:
        recommended_role = "support"
    elif present_dps >= 2 and not present_survival:
        recommended_role = "survivability"
    else:
        recommended_role = "dps"

    return {
        "roles": normalized_roles,
        "champions": normalized_champs,
        "missing_champions": missing,
        "recommended_role": recommended_role,
    }


def adjust_stat_targets(current: dict[str, str], preferred_profile: str, team_role: str) -> dict[str, dict[str, float]]:
    base = BASE_STAT_PROFILES[preferred_profile]
    current_map = {
        "Health": to_float(current.get("health", 0)),
        "Grenade": to_float(current.get("grenade", 0)),
        "Class": to_float(current.get("class_stat", 0)),
        "Weapons": to_float(current.get("weapons_stat", 0)),
        "Super": to_float(current.get("super", 0)),
        "Melee": to_float(current.get("melee", 0)),
    }
    targets: dict[str, dict[str, float]] = {}
    for stat in STAT_ORDER:
        low, high = base[stat]
        if team_role == "support":
            if stat == "Class":
                low += 10; high += 10
            if stat == "Grenade":
                low += 5; high += 5
        elif team_role == "anti_champion":
            if stat == "Health":
                low += 5; high += 5
            if stat == "Class":
                low += 5; high += 5
        elif team_role == "survivability":
            if stat == "Health":
                low += 10; high += 10
            if stat == "Class":
                low += 10; high += 10
            if stat == "Weapons":
                low -= 5; high -= 5
        elif team_role == "dps":
            if stat == "Weapons":
                low += 10; high += 10
            if stat == "Super":
                low += 10; high += 10
        targets[stat] = {"current": current_map[stat], "target_low": low, "target_high": high}
    return targets


def choose_team_build(owned: set[str], team_ctx: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    role = team_ctx["recommended_role"]
    role_cfg = TEAM_ROLE_PRIORITIES[role]
    profile = role_cfg["preferred_profile"]
    priorities = CANDIDATE_PRIORITIES[profile]
    reasons: list[str] = [f"Recommended role is {role}."]

    def rank_item(item: str) -> float:
        tags = ITEM_TAGS.get(item, set())
        score = 1.0
        for tag in role_cfg["needed_tags"]:
            if tag in tags:
                score += 0.8
        if item in role_cfg["armor_bias"]:
            score += 1.0
        if role == "anti_champion":
            for champ in team_ctx["missing_champions"]:
                if champ == "barrier" and "anti-barrier" in tags:
                    score += 1.4
                elif champ == "overload" and "anti-overload" in tags:
                    score += 1.4
                elif champ == "unstoppable" and "anti-unstoppable" in tags:
                    score += 1.4
        return score

    def best_owned(options: list[str], slot: str) -> str:
        candidates = [x for x in options if x in owned]
        if not candidates:
            return "No clear pick"
        ranked = sorted(candidates, key=rank_item, reverse=True)
        chosen = ranked[0]
        reasons.append(f"Selected {chosen} for {slot} to fit {role} role.")
        return chosen

    build = {
        "kinetic": best_owned(priorities["kinetic"], "kinetic"),
        "energy": best_owned(priorities["energy"], "energy"),
        "power": best_owned(priorities["power"], "power"),
        "armor_exotic": best_owned(priorities["armor_exotic"], "armor_exotic"),
        "subclass": "Nightstalker",
    }

    if role == "anti_champion":
        if "barrier" in team_ctx["missing_champions"] and "Arbalest" in owned:
            build["kinetic"] = "Arbalest"; reasons.append("Forced Arbalest to cover missing barrier role.")
        if "overload" in team_ctx["missing_champions"] and "Le Monarque" in owned:
            build["energy"] = "Le Monarque"; reasons.append("Forced Le Monarque to cover missing overload role.")
        if "unstoppable" in team_ctx["missing_champions"] and "Leviathan's Breath" in owned:
            build["power"] = "Leviathan's Breath"; reasons.append("Forced Leviathan's Breath to cover missing unstoppable role.")
    elif role == "support":
        if "Orpheus Rig" in owned:
            build["armor_exotic"] = "Orpheus Rig"; reasons.append("Support role biases toward Orpheus Rig for team value.")
    elif role == "survivability":
        if "Buried Bloodline" in owned:
            build["kinetic"] = "Buried Bloodline"; reasons.append("Survivability role biases toward Buried Bloodline sustain.")
        if "Cyrtarachne's Facade" in owned:
            build["armor_exotic"] = "Cyrtarachne's Facade"; reasons.append("Survivability role biases toward Cyrtarachne's Facade DR.")
    elif role == "dps":
        if "Dragon's Breath" in owned:
            build["power"] = "Dragon's Breath"; reasons.append("DPS role biases toward Dragon's Breath.")
        if "Lucky Pants" in owned:
            build["armor_exotic"] = "Lucky Pants"; reasons.append("DPS role biases toward Lucky Pants.")

    return build, reasons


def champion_coverage(build: dict[str, str]) -> set[str]:
    items = [build.get("kinetic", ""), build.get("energy", ""), build.get("power", ""), build.get("armor_exotic", "")]
    covered: set[str] = set()
    for item in items:
        tags = ITEM_TAGS.get(item, set())
        if "anti-barrier" in tags:
            covered.add("barrier")
        if "anti-overload" in tags:
            covered.add("overload")
        if "anti-unstoppable" in tags:
            covered.add("unstoppable")
    return covered


def score_build(build: dict[str, str], stat_targets: dict[str, dict[str, float]], team_role: str) -> dict[str, float]:
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

    weights = ROLE_SCORE_BONUS[team_role]
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


def compare_scores(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    delta = {k: round(after[k] - before[k], 1) for k in ["survivability", "dps", "ease_of_use", "overall"]}
    if delta["overall"] > 0.3:
        verdict = "Net team-aware improvement."
    elif delta["overall"] < -0.3:
        verdict = "Net team-aware downgrade."
    else:
        verdict = "Mostly sidegrade or situational shift."
    return {"delta": delta, "verdict": verdict}


def render_md(team_ctx: dict[str, Any], baseline_profile: str, before_build: dict[str, str], after_build: dict[str, str], before_scores: dict[str, float], after_scores: dict[str, float], comparison: dict[str, Any], reasons: list[str], targets: dict[str, dict[str, float]], before_coverage: set[str], after_coverage: set[str]) -> str:
    lines = [
        "# Warmind Fireteam Intelligence",
        "",
        f"- Team Roles Reported: **{', '.join(team_ctx['roles']) if team_ctx['roles'] else 'none'}**",
        f"- Team Champion Coverage Reported: **{', '.join(team_ctx['champions']) if team_ctx['champions'] else 'none'}**",
        f"- Missing Team Champions: **{', '.join(team_ctx['missing_champions']) if team_ctx['missing_champions'] else 'none'}**",
        f"- Recommended Your Role: **{team_ctx['recommended_role']}**",
        f"- Baseline Profile: **{baseline_profile}**",
        "",
        "## Before",
        f"- Kinetic: **{before_build['kinetic']}**",
        f"- Energy: **{before_build['energy']}**",
        f"- Power: **{before_build['power']}**",
        f"- Exotic Armor: **{before_build['armor_exotic']}**",
        f"- Your Champion Coverage: **{', '.join(sorted(before_coverage)) if before_coverage else 'none'}**",
        f"- Overall: **{before_scores['overall']} / 10**",
        "",
        "## Team-Aware Build",
        f"- Kinetic: **{after_build['kinetic']}**",
        f"- Energy: **{after_build['energy']}**",
        f"- Power: **{after_build['power']}**",
        f"- Exotic Armor: **{after_build['armor_exotic']}**",
        f"- Your Champion Coverage: **{', '.join(sorted(after_coverage)) if after_coverage else 'none'}**",
        f"- Survivability: **{after_scores['survivability']} / 10** ({comparison['delta']['survivability']:+.1f})",
        f"- DPS: **{after_scores['dps']} / 10** ({comparison['delta']['dps']:+.1f})",
        f"- Ease of Use: **{after_scores['ease_of_use']} / 10** ({comparison['delta']['ease_of_use']:+.1f})",
        f"- Overall: **{after_scores['overall']} / 10** ({comparison['delta']['overall']:+.1f})",
        f"- Verdict: **{comparison['verdict']}**",
        "",
        "## Why Warmind Assigned This Role"]
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.extend(["", "## Team-Aware Stat Targets"])
    for stat in STAT_ORDER:
        lines.append(f"- **{stat}**: current {targets[stat]['current']:.0f} | target {targets[stat]['target_low']:.0f}-{targets[stat]['target_high']:.0f}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 15 fireteam intelligence")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--team-roles", required=False, default="", help="Comma-separated team roles already present, e.g. dps,support")
    parser.add_argument("--team-champions", required=False, default="", help="Comma-separated champion coverage already present on team")
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

    team_roles = [x.strip() for x in args.team_roles.split(",") if x.strip()]
    team_champions = [x.strip() for x in args.team_champions.split(",") if x.strip()]
    team_ctx = parse_team_context(team_roles, team_champions)

    after_build, reasons = choose_team_build(owned, team_ctx)
    targets = adjust_stat_targets(current, TEAM_ROLE_PRIORITIES[team_ctx['recommended_role']]['preferred_profile'], team_ctx['recommended_role'])
    before_targets = adjust_stat_targets(current, baseline_profile, "survivability")

    before_scores = score_build(before_build, before_targets, "survivability" if baseline_profile == "survivability" else "dps" if baseline_profile == "dps" else "support")
    after_scores = score_build(after_build, targets, team_ctx["recommended_role"])
    comparison = compare_scores(before_scores, after_scores)
    before_coverage = champion_coverage(before_build)
    after_coverage = champion_coverage(after_build)

    payload = {
        "team_context": team_ctx,
        "baseline_profile": baseline_profile,
        "before_build": before_build,
        "after_build": after_build,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "comparison": comparison,
        "targets": targets,
        "reasons": reasons,
        "before_coverage": sorted(before_coverage),
        "after_coverage": sorted(after_coverage),
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase150_team.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write(out / "Phase150 Team.md", render_md(team_ctx, baseline_profile, before_build, after_build, before_scores, after_scores, comparison, reasons, targets, before_coverage, after_coverage))


if __name__ == "__main__":
    main()
