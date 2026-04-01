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


def weakest_link(current: dict[str, str], stat_info: dict) -> dict:
    deltas = {}
    for stat in STAT_ORDER:
        cur = stat_info["targets"][stat]["current"]
        low = stat_info["targets"][stat]["target_low"]
        high = stat_info["targets"][stat]["target_high"]
        if cur < low:
            deltas[stat] = low - cur
        elif cur > high:
            deltas[stat] = cur - high
        else:
            deltas[stat] = 0
    worst_stat = max(deltas, key=deltas.get)
    if deltas[worst_stat] == 0:
        summary = "No major stat weakness detected. The next gains come from item quality or activity tuning."
    elif worst_stat == "Weapons":
        summary = "Weapons is the weakest part of the shell because it is over-allocated relative to the target band, which steals budget from survivability."
    else:
        summary = f"{worst_stat} is the weakest part of the shell because it is furthest from the target range."
    return {"weakest_stat": worst_stat, "gap": deltas[worst_stat], "summary": summary}


def build_qa_context(owned: set[str], current: dict[str, str], stat_info: dict, reasoning: dict) -> dict:
    wl = weakest_link(current, stat_info)
    selected = reasoning["selected"]
    selected_names = {selected["kinetic"], selected["energy"], selected["power"], selected["armor_exotic"]}
    best_swap_candidates = [item for item in ["Buried Bloodline", "Le Monarque", "Leviathan's Breath", "Gyrfalcon's Hauberk", "Witherhoard", "Outbreak Perfected", "Cyrtarachne's Facade"] if item in owned and item not in selected_names]
    farm_targets = [item for item in CHASE_PRIORITY if item not in owned][:3]
    return {
        "current_loadout": current,
        "recommended_build": {"kinetic": selected["kinetic"], "energy": selected["energy"], "power": selected["power"], "armor_exotic": selected["armor_exotic"], "subclass": "Nightstalker"},
        "decision_log": reasoning["decision_log"],
        "stat_targets": stat_info["targets"],
        "profile": stat_info["profile_label"],
        "confidence": reasoning["confidence"],
        "weakest_link": wl,
        "best_swap_candidates": best_swap_candidates,
        "farm_targets": farm_targets,
        "qa_answers": {
            "why_selected": {entry["selected"]: f"{entry['selected']} was selected for {entry['slot']} because {entry['reason']}." for entry in reasoning["decision_log"]},
            "why_not_selected": {rejected: f"{rejected} was not selected because Warmind preferred {entry['selected']} for {entry['slot']}, since {entry['reason']}." for entry in reasoning["decision_log"] for rejected in entry["rejected"]},
            "weakest_link": wl["summary"],
            "stat_change_first": f"Change {wl['weakest_stat']} first. {wl['summary']}",
            "best_swap": f"Best owned swap candidates after the current recommendation are: {', '.join(best_swap_candidates) if best_swap_candidates else 'no strong owned alternatives detected beyond the current recommendation'}.",
            "next_farm": f"Best farm targets to improve this shell next are: {', '.join(farm_targets) if farm_targets else 'no high-priority chase gaps detected'}.",
            "more_survivability": "For more survivability, keep the core safe shell and move budget out of excess Weapons into Health and Class first.",
            "more_dps": "For more DPS, keep the survivability floor intact, then push Weapons and Super toward the top of their target bands and consider burst-oriented swaps only if the activity allows it.",
        },
    }


def answer_question(question: str, context: dict) -> str:
    q = question.strip().lower()
    qa = context["qa_answers"]
    recommended = context["recommended_build"]

    for item, answer in qa["why_selected"].items():
        if item.lower() in q and ("why" in q or "chosen" in q or "pick" in q):
            return answer
    for item, answer in qa["why_not_selected"].items():
        if item.lower() in q and ("why not" in q or "instead of" in q or "swap" in q):
            return answer

    if "weakest" in q or "weak point" in q:
        return qa["weakest_link"]
    if "stat" in q and ("first" in q or "change" in q or "fix" in q):
        return qa["stat_change_first"]
    if "farm" in q or "chase" in q or "next" in q:
        return qa["next_farm"]
    if "swap" in q or "best alternative" in q or "best swap" in q:
        return qa["best_swap"]
    if "survivability" in q or "survive" in q or "tankier" in q:
        return qa["more_survivability"]
    if "dps" in q or "damage" in q:
        return qa["more_dps"]
    if "build" in q and "why" in q:
        return f"Warmind selected {recommended['kinetic']}, {recommended['energy']}, {recommended['power']}, and {recommended['armor_exotic']} because the current profile is {context['profile']} and the system confidence is {context['confidence']}."

    return (
        "Warmind did not find a tight match for that question yet. Try asking about why an item was selected, why an item was not selected, "
        "what stat to change first, best swap, weakest link, survivability, DPS, or what to farm next."
    )


def render_build_qa_md(context: dict, question: str | None = None, answer: str | None = None) -> str:
    lines = ["# Build Q&A", "", "## Quick Answers"]
    qa = context["qa_answers"]
    lines.append(f"- **Why was the kinetic chosen?** {qa['why_selected'].get(context['recommended_build']['kinetic'], '')}")
    lines.append(f"- **Why was the energy chosen?** {qa['why_selected'].get(context['recommended_build']['energy'], '')}")
    lines.append(f"- **Why was the heavy chosen?** {qa['why_selected'].get(context['recommended_build']['power'], '')}")
    lines.append(f"- **What is the weakest part of this build?** {qa['weakest_link']}")
    lines.append(f"- **What stat should change first?** {qa['stat_change_first']}")
    lines.append(f"- **What is the best owned swap?** {qa['best_swap']}")
    lines.append(f"- **What should I farm next?** {qa['next_farm']}")
    lines.extend(["", "## Why Not Selected"])
    if context["qa_answers"]["why_not_selected"]:
        for item, response in sorted(context["qa_answers"]["why_not_selected"].items()):
            lines.append(f"- **{item}**: {response}")
    else:
        lines.append("- No rejected owned alternatives were detected.")
    lines.extend(["", "## What If"])
    lines.append(f"- **What if I want more survivability?** {qa['more_survivability']}")
    lines.append(f"- **What if I want more DPS?** {qa['more_dps']}")
    if question and answer:
        lines.extend(["", "## Interactive Question", f"- **Question:** {question}", f"- **Answer:** {answer}"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind interactive Build Q&A layer")
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
    qa_context = build_qa_context(owned, current, stat_info, reasoning)
    answer = answer_question(args.question, qa_context) if args.question else None

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "Build QA.md", render_build_qa_md(qa_context, args.question, answer))
    if answer:
        write(out / "Question Answer.txt", answer)
    (out / "qa_context.json").write_text(json.dumps(qa_context, indent=2), encoding="utf-8")
    (out / "recommendation_export.json").write_text(json.dumps({"qa_context": qa_context, "reasoning": reasoning, "stat_optimization": stat_info, "interactive_question": args.question, "interactive_answer": answer}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
