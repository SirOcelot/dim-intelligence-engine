from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

STAT_PROFILES = {
    "gm": {"Health": (90, 110), "Grenade": (80, 120), "Class": (70, 100), "Weapons": (90, 120), "Super": (20, 60), "Melee": (0, 50)},
    "dps": {"Health": (60, 90), "Grenade": (40, 90), "Class": (30, 70), "Weapons": (120, 170), "Super": (60, 110), "Melee": (0, 40)},
    "survivability": {"Health": (90, 120), "Grenade": (70, 110), "Class": (80, 110), "Weapons": (80, 115), "Super": (20, 50), "Melee": (0, 40)},
}
STAT_ORDER = ["Health", "Grenade", "Class", "Weapons", "Super", "Melee"]
KINETIC_PRIORITY = ["Buried Bloodline", "Witherhoard", "Arbalest"]
ENERGY_PRIORITY = ["Le Monarque", "Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"]
POWER_PRIORITY = ["Leviathan's Breath", "Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"]
ARMOR_PRIORITY = ["Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Wormhusk Crown", "Lucky Pants"]
CHASE_PRIORITY = ["Conditional Finality", "Apex Predator", "Edge Transit", "The Call", "Ex Diris"]

SURVIVABILITY_ITEMS = {
    "Buried Bloodline": 2.5,
    "Le Monarque": 1.5,
    "Leviathan's Breath": 1.5,
    "Gyrfalcon's Hauberk": 2.0,
    "Cyrtarachne's Facade": 2.0,
    "Witherhoard": 1.0,
    "Arbalest": 0.8,
    "Outbreak Perfected": 1.0,
    "Thunderlord": 0.7,
    "Wormhusk Crown": 1.5,
    "Assassin's Cowl": 1.7,
}
DPS_ITEMS = {
    "Buried Bloodline": 1.2,
    "Witherhoard": 1.8,
    "Le Monarque": 1.0,
    "Outbreak Perfected": 1.4,
    "Choir of One": 1.7,
    "Leviathan's Breath": 1.6,
    "Thunderlord": 1.5,
    "Dragon's Breath": 1.8,
    "Gjallarhorn": 1.7,
    "Microcosm": 1.4,
    "Lucky Pants": 1.6,
    "Gyrfalcon's Hauberk": 1.0,
}
EASE_ITEMS = {
    "Buried Bloodline": 1.5,
    "Witherhoard": 1.8,
    "Le Monarque": 1.3,
    "Outbreak Perfected": 1.6,
    "Thunderlord": 1.8,
    "Leviathan's Breath": 1.2,
    "Gyrfalcon's Hauberk": 1.2,
    "Cyrtarachne's Facade": 1.5,
    "Wormhusk Crown": 1.7,
    "Assassin's Cowl": 1.2,
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


def dedupe_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        name = str(value).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def to_float(value: object) -> float:
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
        if str(candidate.get(class_col, "")).strip().lower() == "hunter" and "equipped hunter" in str(candidate.get(name_col, "")).strip().lower():
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
        result[out_key] = str(row.get(col, "")).strip() if col else ""
    return result


def choose_profile(current: dict[str, str]) -> tuple[str, str]:
    weapons = to_float(current.get("weapons_stat", 0))
    health = to_float(current.get("health", 0))
    grenade = to_float(current.get("grenade", 0))
    legs = current.get("legs", "")
    power = current.get("power", "")
    if legs in {"Lucky Pants"} or power in {"Dragon's Breath", "Gjallarhorn"}:
        return "dps", "Boss DPS / burst-oriented shell"
    if current.get("kinetic", "") in {"Buried Bloodline", "Witherhoard"} or current.get("energy", "") in {"Le Monarque", "Outbreak Perfected"} or health < 60:
        return "gm", "GM / endgame-safe shell"
    if grenade >= 100 and weapons >= 140:
        return "dps", "Ability-assisted damage shell"
    return "survivability", "General survivability shell"


def build_stat_payload(current: dict[str, str]) -> dict:
    profile_key, profile_label = choose_profile(current)
    targets = STAT_PROFILES[profile_key]
    stats = {
        "Health": to_float(current.get("health", 0)),
        "Grenade": to_float(current.get("grenade", 0)),
        "Class": to_float(current.get("class_stat", 0)),
        "Weapons": to_float(current.get("weapons_stat", 0)),
        "Super": to_float(current.get("super", 0)),
        "Melee": to_float(current.get("melee", 0)),
    }
    detailed: dict[str, dict[str, float]] = {}
    recommendations: list[str] = []
    for stat in STAT_ORDER:
        low, high = targets[stat]
        cur = stats[stat]
        detailed[stat] = {"current": cur, "target_low": low, "target_high": high}
        if cur < low:
            recommendations.append(f"Increase {stat} from {cur:.0f} toward {low}-{high}.")
        elif cur > high:
            recommendations.append(f"Reduce {stat} from {cur:.0f} toward {low}-{high}.")
        else:
            recommendations.append(f"Keep {stat} in the current band.")
    if stats["Weapons"] >= 150 and stats["Health"] <= 60:
        recommendations.append("Weapons is over-allocated relative to survivability.")
    return {"profile_key": profile_key, "profile_label": profile_label, "targets": detailed, "recommendations": recommendations}


def choose_first_owned(priority: list[str], owned: set[str]) -> str:
    for item in priority:
        if item in owned:
            return item
    return "No clear pick"


def decision_reason(slot: str, selected: str, owned: set[str]) -> tuple[str, list[str]]:
    if slot == "kinetic" and selected == "Buried Bloodline":
        return "it gives the safest sustain and utility shell for hard endgame", [x for x in ["Witherhoard", "Arbalest"] if x in owned]
    if slot == "kinetic" and selected == "Witherhoard":
        return "it gives passive damage and area denial when sustain is less critical", [x for x in ["Buried Bloodline", "Arbalest"] if x in owned]
    if slot == "energy" and selected == "Le Monarque":
        return "it gives safer long-range pressure and overload utility than your other energy choices", [x for x in ["Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"] if x in owned]
    if slot == "energy" and selected == "Outbreak Perfected":
        return "it gives better ammo-efficient primary damage when direct champion utility matters less", [x for x in ["Le Monarque", "Graviton Lance", "Choir of One"] if x in owned]
    if slot == "power" and selected == "Leviathan's Breath":
        return "it combines safer heavy damage with champion utility", [x for x in ["Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"] if x in owned]
    if slot == "power" and selected == "Thunderlord":
        return "it gives lower-friction sustained damage and easier handling", [x for x in ["Leviathan's Breath", "Dragon's Breath", "Gjallarhorn"] if x in owned]
    if slot == "armor_exotic" and selected == "Gyrfalcon's Hauberk":
        return "it provides the strongest practical invis and volatile loop from your Hunter options", [x for x in ["Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Lucky Pants"] if x in owned]
    if slot == "armor_exotic" and selected == "Cyrtarachne's Facade":
        return "it stabilizes survivability through damage resistance instead of greedier burst options", [x for x in ["Gyrfalcon's Hauberk", "Orpheus Rig", "Assassin's Cowl", "Lucky Pants"] if x in owned]
    return "it best fits the current activity profile from your owned options", []


def build_reasoning(owned: set[str], stat_info: dict) -> dict:
    selected = {
        "kinetic": choose_first_owned(KINETIC_PRIORITY, owned),
        "energy": choose_first_owned(ENERGY_PRIORITY, owned),
        "power": choose_first_owned(POWER_PRIORITY, owned),
        "armor_exotic": choose_first_owned(ARMOR_PRIORITY, owned),
    }
    decision_log = []
    for slot, item in selected.items():
        reason, rejected = decision_reason(slot, item, owned)
        decision_log.append({"slot": slot, "selected": item, "rejected": rejected, "reason": reason})
    profile_key = stat_info["profile_key"]
    if profile_key == "gm":
        confidence = "high"
        stat_summary = "Stat targets skew survivability-first to avoid over-investing in Weapons at the cost of uptime."
    elif profile_key == "dps":
        confidence = "medium"
        stat_summary = "Stat targets skew damage-first, while still preserving enough survivability to avoid zero-DPS deaths."
    else:
        confidence = "medium"
        stat_summary = "Stat targets balance survivability and neutral utility for general play."
    return {"selected": selected, "decision_log": decision_log, "confidence": confidence, "stat_summary": stat_summary}


def build_context(owned: set[str], current: dict[str, str], stat_info: dict, reasoning: dict) -> dict:
    return {
        "current_loadout": current,
        "recommended_build": {
            "kinetic": reasoning["selected"]["kinetic"],
            "energy": reasoning["selected"]["energy"],
            "power": reasoning["selected"]["power"],
            "armor_exotic": reasoning["selected"]["armor_exotic"],
            "subclass": "Nightstalker",
        },
        "decision_log": reasoning["decision_log"],
        "stat_targets": stat_info["targets"],
        "profile": stat_info["profile_label"],
        "confidence": reasoning["confidence"],
        "owned": sorted(owned),
    }


def score_build(build: dict, stat_targets: dict, profile_label: str) -> dict:
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
        survivability += SURVIVABILITY_ITEMS.get(item, 0.0)
        dps += DPS_ITEMS.get(item, 0.0)
        ease += EASE_ITEMS.get(item, 0.0)

    if "GM" in profile_label or "endgame" in profile_label.lower():
        survivability += 0.8
        if weapons_stat > 135 and health < 70:
            survivability -= 1.0
    if "DPS" in profile_label:
        dps += 0.8
        if health < 55:
            dps -= 0.3

    result = {
        "survivability": clamp_1_10(survivability),
        "dps": clamp_1_10(dps),
        "ease_of_use": clamp_1_10(ease),
    }
    result["overall"] = clamp_1_10((result["survivability"] * 0.4) + (result["dps"] * 0.35) + (result["ease_of_use"] * 0.25))
    return result


def compare_scores(original: dict, new: dict) -> dict:
    delta = {k: round(new[k] - original[k], 1) for k in original.keys()}
    if delta["overall"] > 0.3:
        verdict = "Net improvement."
    elif delta["overall"] < -0.3:
        verdict = "Net downgrade."
    else:
        verdict = "Mostly sidegrade or situational shift."
    return {"delta": delta, "verdict": verdict}


def simulate_swap(context: dict, swap_out: str, swap_in: str) -> dict:
    owned = set(context["owned"])
    rb = dict(context["recommended_build"])
    slot_found = None
    for slot in ["kinetic", "energy", "power", "armor_exotic"]:
        if rb.get(slot, "").lower() == swap_out.lower():
            slot_found = slot
            break
    if slot_found is None:
        return {"success": False, "summary": f"Warmind could not find {swap_out} in the recommended build, so no swap simulation was performed."}
    if swap_in not in owned:
        return {"success": False, "summary": f"Warmind could not confirm ownership of {swap_in}, so the swap would be theoretical rather than vault-aware."}

    original_score = score_build(context["recommended_build"], context["stat_targets"], context["profile"])
    new_build = dict(rb)
    old = new_build[slot_found]
    new_build[slot_found] = swap_in
    new_score = score_build(new_build, context["stat_targets"], context["profile"])
    comparison = compare_scores(original_score, new_score)

    summary = (
        f"Swap simulation: {old} -> {swap_in}. Survivability {original_score['survivability']} -> {new_score['survivability']}, "
        f"DPS {original_score['dps']} -> {new_score['dps']}, Ease {original_score['ease_of_use']} -> {new_score['ease_of_use']}. {comparison['verdict']}"
    )
    return {
        "success": True,
        "slot": slot_found,
        "swap_out": old,
        "swap_in": swap_in,
        "original_score": original_score,
        "new_score": new_score,
        "comparison": comparison,
        "summary": summary,
    }


def simulate_stat_shift(context: dict, stat: str, delta: float) -> dict:
    stat_norm = stat.strip().title()
    if stat_norm not in STAT_ORDER:
        return {"success": False, "summary": f"Warmind does not recognize the stat '{stat}'."}

    original_targets = json.loads(json.dumps(context["stat_targets"]))
    new_targets = json.loads(json.dumps(context["stat_targets"]))
    new_targets[stat_norm]["current"] += delta

    original_score = score_build(context["recommended_build"], original_targets, context["profile"])
    new_score = score_build(context["recommended_build"], new_targets, context["profile"])
    comparison = compare_scores(original_score, new_score)

    summary = (
        f"Stat simulation: {stat_norm} {original_targets[stat_norm]['current']:.0f} -> {new_targets[stat_norm]['current']:.0f}. "
        f"Survivability {original_score['survivability']} -> {new_score['survivability']}, "
        f"DPS {original_score['dps']} -> {new_score['dps']}, Ease {original_score['ease_of_use']} -> {new_score['ease_of_use']}. {comparison['verdict']}"
    )
    return {
        "success": True,
        "stat": stat_norm,
        "delta_amount": delta,
        "original_score": original_score,
        "new_score": new_score,
        "comparison": comparison,
        "summary": summary,
    }


def parse_question(question: str, context: dict) -> dict:
    q = question.strip().lower()
    if "swap" in q and " for " in q:
        cleaned = q.replace("what if", "").replace("simulate", "").replace("swap", "").strip()
        left, right = cleaned.split(" for ", 1)
        swap_out = left.strip().title()
        swap_in = right.strip().title()
        return {"type": "swap", **simulate_swap(context, swap_out, swap_in)}

    if ("drop " in q or "add " in q or "increase " in q or "reduce " in q) and any(stat.lower() in q for stat in STAT_ORDER):
        amount = 0.0
        mode = None
        for token in q.replace("+", " ").replace("-", " -").split():
            try:
                amount = float(token)
                break
            except Exception:
                continue
        if "drop" in q or "reduce" in q:
            mode = -1
        elif "add" in q or "increase" in q:
            mode = 1
        if mode is None or amount == 0:
            return {"type": "error", "success": False, "summary": "Warmind saw a stat-change question, but could not parse the amount confidently."}
        for stat in STAT_ORDER:
            if stat.lower() in q:
                return {"type": "stat_shift", **simulate_stat_shift(context, stat, mode * abs(amount))}

    original_score = score_build(context["recommended_build"], context["stat_targets"], context["profile"])
    if "score" in q or "rate" in q:
        return {"type": "score", "success": True, "summary": f"Current Warmind build scores: Survivability {original_score['survivability']}, DPS {original_score['dps']}, Ease {original_score['ease_of_use']}, Overall {original_score['overall']}."}

    return {"type": "fallback", "success": True, "summary": "Warmind did not detect a simulation request. Try asking to swap X for Y, drop/add a stat amount, or ask for the current score."}


def render_scoring_md(context: dict, result: dict | None) -> str:
    current_score = score_build(context["recommended_build"], context["stat_targets"], context["profile"])
    rb = context["recommended_build"]
    lines = ["# Warmind Scoring", "", "## Recommended Build", f"- Kinetic: **{rb['kinetic']}**", f"- Energy: **{rb['energy']}**", f"- Power: **{rb['power']}**", f"- Exotic Armor: **{rb['armor_exotic']}**", f"- Subclass: **{rb['subclass']}**", "", "## Current Scores", f"- Survivability: **{current_score['survivability']} / 10**", f"- DPS: **{current_score['dps']} / 10**", f"- Ease of Use: **{current_score['ease_of_use']} / 10**", f"- Overall: **{current_score['overall']} / 10**"]
    if result:
        lines.extend(["", "## Simulation Result", f"- Type: **{result['type']}**", f"- Summary: {result['summary']}"])
        if result.get("success") and result["type"] in {"swap", "stat_shift"}:
            new_score = result["new_score"]
            delta = result["comparison"]["delta"]
            lines.extend([
                "", "## Recomputed Scores",
                f"- Survivability: **{new_score['survivability']} / 10** ({delta['survivability']:+.1f})",
                f"- DPS: **{new_score['dps']} / 10** ({delta['dps']:+.1f})",
                f"- Ease of Use: **{new_score['ease_of_use']} / 10** ({delta['ease_of_use']:+.1f})",
                f"- Overall: **{new_score['overall']} / 10** ({delta['overall']:+.1f})",
                f"- Verdict: **{result['comparison']['verdict']}**",
            ])
    else:
        lines.extend(["", "## Example Questions", "- score this build", "- swap le monarque for graviton lance", "- swap leviathan's breath for thunderlord", "- drop 20 weapons", "- add 20 health"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind scoring and recompute engine")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--question", required=False)
    args = parser.parse_args()

    df_w = pd.read_csv(args.weapons).fillna("")
    df_a = pd.read_csv(args.armor).fillna("")
    df = pd.concat([df_w, df_a], ignore_index=True).fillna("")
    ldf = pd.read_csv(args.loadouts).fillna("") if args.loadouts and Path(args.loadouts).exists() else None

    name_col = first_col(df, ["Name", "Item Name"])
    rarity_col = first_col(df, ["Rarity", "Tier Type Name"])
    if not name_col or not rarity_col:
        raise SystemExit("Could not detect required DIM columns.")

    exotics = df[df[rarity_col].astype(str).str.lower() == "exotic"].copy()
    owned = set(dedupe_names(exotics[name_col]))
    current = detect_current_hunter_loadout(ldf)
    stat_info = build_stat_payload(current)
    reasoning = build_reasoning(owned, stat_info)
    context = build_context(owned, current, stat_info, reasoning)
    result = parse_question(args.question, context) if args.question else None

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "Scoring.md", render_scoring_md(context, result))
    if result:
        write(out / "Scoring Answer.txt", result["summary"])
    (out / "scoring_context.json").write_text(json.dumps({"context": context, "result": result}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
