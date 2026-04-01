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


def stat_payload(current: dict[str, str]) -> dict:
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
    advice: list[str] = []
    detailed: dict[str, dict[str, float]] = {}
    for stat in STAT_ORDER:
        low, high = targets[stat]
        cur = stats[stat]
        detailed[stat] = {"current": cur, "target_low": low, "target_high": high}
        if cur < low:
            advice.append(f"Increase {stat} from {cur:.0f} toward {low}-{high}.")
        elif cur > high:
            advice.append(f"Reduce {stat} from {cur:.0f} toward {low}-{high} to free budget.")
        else:
            advice.append(f"{stat} at {cur:.0f} is already in a strong range ({low}-{high}).")
    if stats["Weapons"] >= 150 and stats["Health"] <= 60:
        advice.append("This build is over-invested in Weapons at the cost of survivability.")
    return {"profile_key": profile_key, "profile_label": profile_label, "targets": detailed, "recommendations": advice}


def choose_first_owned(priority: list[str], owned: set[str]) -> str:
    for item in priority:
        if item in owned:
            return item
    return "No clear pick"


def decision_reason(slot: str, selected: str, owned: set[str]) -> tuple[str, list[str]]:
    if slot == "kinetic" and selected == "Buried Bloodline":
        rejected = [x for x in ["Witherhoard", "Arbalest"] if x in owned]
        return "it gives the safest sustain and utility shell for hard endgame", rejected
    if slot == "kinetic" and selected == "Witherhoard":
        rejected = [x for x in ["Buried Bloodline", "Arbalest"] if x in owned]
        return "it gives passive damage and area denial when sustain is less critical", rejected
    if slot == "energy" and selected == "Le Monarque":
        rejected = [x for x in ["Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"] if x in owned]
        return "it gives safer long-range pressure and overload utility than your other energy choices", rejected
    if slot == "energy" and selected == "Outbreak Perfected":
        rejected = [x for x in ["Le Monarque", "Graviton Lance", "Choir of One"] if x in owned]
        return "it gives better ammo-efficient primary damage when direct champion utility matters less", rejected
    if slot == "power" and selected == "Leviathan's Breath":
        rejected = [x for x in ["Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"] if x in owned]
        return "it combines safer heavy damage with champion utility", rejected
    if slot == "power" and selected == "Thunderlord":
        rejected = [x for x in ["Leviathan's Breath", "Dragon's Breath", "Gjallarhorn"] if x in owned]
        return "it gives lower-friction sustained damage and easier handling", rejected
    if slot == "armor_exotic" and selected == "Gyrfalcon's Hauberk":
        rejected = [x for x in ["Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Lucky Pants"] if x in owned]
        return "it provides the strongest practical invis and volatile loop from your Hunter options", rejected
    if slot == "armor_exotic" and selected == "Cyrtarachne's Facade":
        rejected = [x for x in ["Gyrfalcon's Hauberk", "Orpheus Rig", "Assassin's Cowl", "Lucky Pants"] if x in owned]
        return "it stabilizes survivability through damage resistance instead of greedier burst options", rejected
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
    profile_key = stat_info.get("profile_key", "gm")
    if profile_key == "gm":
        confidence = "high"
        stat_summary = "Stat targets skew survivability-first to avoid over-investing in Weapons at the cost of uptime."
    elif profile_key == "dps":
        confidence = "medium"
        stat_summary = "Stat targets skew toward burst or sustained damage, while preserving enough survivability to avoid zero-DPS deaths."
    else:
        confidence = "medium"
        stat_summary = "Stat targets balance survivability and neutral utility for general play."
    return {"selected": selected, "decision_log": decision_log, "confidence": confidence, "stat_summary": stat_summary}


def build_build_recommendation(reasoning: dict, stat_info: dict, current: dict[str, str]) -> tuple[str, dict]:
    selected = reasoning["selected"]
    lines = ["# Build Recommendation (GM)", "", f"- Kinetic: **{selected['kinetic']}**", f"- Energy: **{selected['energy']}**", f"- Heavy: **{selected['power']}**", f"- Exotic Armor: **{selected['armor_exotic']}**", "- Subclass: **Nightstalker**", "", "## Why This Build", f"- Confidence: **{reasoning['confidence']}**", f"- {reasoning['stat_summary']}"]
    for entry in reasoning["decision_log"]:
        lines.append(f"- **{entry['slot']}**: chose **{entry['selected']}** because {entry['reason']}.")
    lines.extend(["", "## Not Selected (But You Own)"])
    any_rejected = False
    for entry in reasoning["decision_log"]:
        if entry["rejected"]:
            any_rejected = True
            lines.append(f"- Instead of **{', '.join(entry['rejected'])}**, Warmind chose **{entry['selected']}** because {entry['reason']}.")
    if not any_rejected:
        lines.append("- No meaningful rejected alternatives were detected for this build shell.")
    lines.extend(["", "## Target Stats"])
    for stat in STAT_ORDER:
        target = stat_info["targets"][stat]
        lines.append(f"- **{stat}**: {int(target['target_low'])}-{int(target['target_high'])}")
    payload = {
        "profile": "gm",
        "activity": "GM",
        "class": "Hunter",
        "subclass": "Nightstalker",
        "weapons": [selected["kinetic"], selected["energy"], selected["power"]],
        "armor_exotic": selected["armor_exotic"],
        "stat_targets": stat_info["targets"],
        "decision_log": reasoning["decision_log"],
        "confidence": reasoning["confidence"],
        "stat_summary": reasoning["stat_summary"],
        "source_current_loadout": current,
    }
    return "\n".join(lines), payload


def build_dim_export(build_payload: dict) -> tuple[str, dict]:
    payload = {
        "app": "Warmind",
        "engine": "Destiny Intelligence Engine",
        "profile": build_payload["profile"],
        "activity": build_payload["activity"],
        "class": build_payload["class"],
        "subclass": build_payload["subclass"],
        "weapons": build_payload["weapons"],
        "armor_exotic": build_payload["armor_exotic"],
        "stat_targets": build_payload["stat_targets"],
        "decision_log": build_payload["decision_log"],
        "confidence": build_payload["confidence"],
        "stat_summary": build_payload["stat_summary"],
    }
    lines = ["# DIM Export", "", f"- Confidence: **{payload['confidence']}**", f"- {payload['stat_summary']}", "", "## Why These Picks"]
    for entry in payload["decision_log"]:
        lines.append(f"- **{entry['selected']}** chosen for **{entry['slot']}** because {entry['reason']}.")
    return "\n".join(lines), payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind reasoning layer")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
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
    stat_info = stat_payload(current)
    reasoning = build_reasoning(owned, stat_info)
    build_md, build_payload = build_build_recommendation(reasoning, stat_info, current)
    dim_md, dim_payload = build_dim_export(build_payload)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "Build Recommendation.md", build_md)
    write(out / "DIM Export.md", dim_md)
    write(out / "Reasoning.md", "# Reasoning\n\n" + json.dumps(reasoning, indent=2))
    (out / "recommendation_export.json").write_text(json.dumps({"reasoning": reasoning, "build_recommendation": build_payload, "dim_export": dim_payload}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
