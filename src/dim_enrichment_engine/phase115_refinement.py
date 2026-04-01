from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

WEAPON_PROFILE_RULES = {
    "gm": {
        "preferred": {
            "reconstruction": 1.8,
            "envious arsenal": 1.8,
            "explosive light": 1.4,
            "vorpal weapon": 1.2,
            "kinetic tremors": 1.3,
            "chill clip": 1.7,
            "voltshot": 1.3,
            "incandescent": 1.1,
            "destabilizing rounds": 1.1,
            "frenzy": 1.2,
            "one for all": 1.0,
            "rapid hit": 0.9,
            "auto-loading holster": 1.5,
            "recombination": 1.6,
            "bait and switch": 1.3,
        },
        "avoid": {
            "air assault": -1.2,
            "under-over": -0.8,
            "offhand strike": -1.0,
            "hip-fire grip": -0.9,
        },
    },
    "dps": {
        "preferred": {
            "bait and switch": 2.0,
            "reconstruction": 1.8,
            "envious arsenal": 1.8,
            "vorpal weapon": 1.3,
            "firing line": 1.4,
            "controlled burst": 1.5,
            "recombination": 1.7,
            "explosive light": 1.8,
            "surrounded": 1.2,
            "auto-loading holster": 1.3,
        },
        "avoid": {
            "air assault": -1.2,
            "under-over": -0.8,
            "shoot to loot": -0.6,
            "hip-fire grip": -1.0,
        },
    },
}

ARMOR_STAT_WEIGHTS = {
    "gm": {"health": 1.4, "class": 1.2, "grenade": 1.0, "weapons": 0.8, "super": 0.5, "melee": 0.3},
    "dps": {"weapons": 1.4, "super": 1.1, "health": 0.9, "grenade": 0.7, "class": 0.6, "melee": 0.3},
    "survivability": {"health": 1.5, "class": 1.3, "grenade": 1.0, "weapons": 0.7, "super": 0.5, "melee": 0.3},
}

SET_KEYWORDS = {
    "survivability": {"twofold": 0.6, "ferropotent": 0.5, "cyrtarachne": 0.4},
    "dps": {"sage": 0.5, "volatile": 0.3, "surge": 0.4},
}

SLOT_BUCKETS = {
    "kinetic": ["kinetic"],
    "energy": ["energy"],
    "power": ["power", "heavy"],
    "legs": ["legs", "leg"],
}


def first_col(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n', encoding='utf-8')


def norm(value: Any) -> str:
    return str(value).strip()


def to_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def is_truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "masterworked", "equipped", "locked", "crafted", "enhanced"}


def detect_profile(loadouts_df: pd.DataFrame | None) -> str:
    if loadouts_df is None or loadouts_df.empty:
        return "gm"
    cols = {str(c).strip().lower(): c for c in loadouts_df.columns}
    class_col = cols.get("class type")
    name_col = cols.get("name")
    if not class_col or not name_col:
        return "gm"
    for _, row in loadouts_df.iterrows():
        if norm(row.get(class_col)).lower() == "hunter" and "equipped hunter" in norm(row.get(name_col)).lower():
            power = norm(row.get(cols.get("equipped power weapons")))
            legs = norm(row.get(cols.get("equipped leg armor")))
            health = to_float(row.get(cols.get("health")))
            weapons = to_float(row.get(cols.get("weapons")))
            if legs == "Lucky Pants" or power in {"Dragon's Breath", "Gjallarhorn"} or weapons >= 140:
                return "dps"
            if health < 70:
                return "gm"
            return "survivability"
    return "gm"


def column_map(df: pd.DataFrame) -> dict[str, str | None]:
    return {
        "name": first_col(df, ["Name", "Item Name"]),
        "id": first_col(df, ["Id", "Item Id", "Instance Id", "Item Instance Id"]),
        "hash": first_col(df, ["Hash", "Item Hash"]),
        "bucket": first_col(df, ["Bucket", "Bucket Name", "Slot"]),
        "owner": first_col(df, ["Owner", "Character"]),
        "power": first_col(df, ["Power", "Power Level", "Base Power"]),
        "masterwork": first_col(df, ["Masterwork", "Masterworked", "Is Masterworked"]),
        "crafted": first_col(df, ["Crafted", "Is Crafted"]),
        "enhanced": first_col(df, ["Enhanced", "Has Enhanced Traits"]),
        "equipped": first_col(df, ["Equipped", "Is Equipped"]),
        "locked": first_col(df, ["Locked", "Is Locked"]),
        "perk1": first_col(df, ["Perk 1", "Trait 1", "Column 3", "Perks 0"]),
        "perk2": first_col(df, ["Perk 2", "Trait 2", "Column 4", "Perks 1"]),
        "perk3": first_col(df, ["Perk 3", "Origin Trait", "Perks 2"]),
        "perk4": first_col(df, ["Perk 4", "Masterwork Type", "Perks 3"]),
        "type": first_col(df, ["Type", "Item Type"]),
        "health": first_col(df, ["Health"]),
        "class": first_col(df, ["Class"]),
        "grenade": first_col(df, ["Grenade"]),
        "weapons": first_col(df, ["Weapons"]),
        "super": first_col(df, ["Super"]),
        "melee": first_col(df, ["Melee"]),
        "total": first_col(df, ["Total", "Base Total", "Stat Total"]),
        "set": first_col(df, ["Set", "Armor Set", "Collection"]),
        "ammo": first_col(df, ["Ammo Type", "Ammo"]),
    }


def bucket_matches(raw_bucket: str, target_slot: str) -> bool:
    raw = raw_bucket.lower()
    for token in SLOT_BUCKETS.get(target_slot, [target_slot]):
        if token in raw:
            return True
    return False


def select_shell(owned_names: set[str]) -> dict[str, str]:
    def first_owned(options: list[str]) -> str:
        for item in options:
            if item in owned_names:
                return item
        return "No clear pick"

    return {
        "kinetic": first_owned(["Buried Bloodline", "Witherhoard", "Arbalest"]),
        "energy": first_owned(["Le Monarque", "Outbreak Perfected", "Graviton Lance", "Choir of One", "Trinity Ghoul"]),
        "power": first_owned(["Leviathan's Breath", "Thunderlord", "Dragon's Breath", "Gjallarhorn", "Microcosm"]),
        "armor_exotic": first_owned(["Gyrfalcon's Hauberk", "Cyrtarachne's Facade", "Orpheus Rig", "Assassin's Cowl", "Wormhusk Crown", "Lucky Pants"]),
        "subclass": "Nightstalker",
    }


def weapon_roll_score(row: pd.Series, cols: dict[str, str | None], profile: str) -> tuple[float, list[str]]:
    rules = WEAPON_PROFILE_RULES.get(profile, WEAPON_PROFILE_RULES["gm"])
    perks = " | ".join(norm(row.get(cols[k])) for k in ["perk1", "perk2", "perk3", "perk4"] if cols.get(k)).lower()
    score = 0.0
    reasons: list[str] = []
    for perk, value in rules["preferred"].items():
        if perk in perks:
            score += value
            reasons.append(f"preferred perk '{perk}' (+{value})")
    for perk, value in rules["avoid"].items():
        if perk in perks:
            score += value
            reasons.append(f"low-value perk '{perk}' ({value})")
    return score, reasons


def armor_stat_score(row: pd.Series, cols: dict[str, str | None], profile: str) -> tuple[float, list[str]]:
    weights = ARMOR_STAT_WEIGHTS.get(profile, ARMOR_STAT_WEIGHTS["gm"])
    score = 0.0
    reasons: list[str] = []
    for stat, weight in weights.items():
        col = cols.get(stat)
        if col:
            value = to_float(row.get(col))
            score += value * (weight / 20.0)
    total_col = cols.get("total")
    if total_col:
        total = to_float(row.get(total_col))
        score += total / 25.0
        reasons.append(f"total stat value {int(total)}")
    return score, reasons


def set_bonus_score(row: pd.Series, cols: dict[str, str | None], profile: str) -> tuple[float, list[str]]:
    set_col = cols.get("set")
    if not set_col:
        return 0.0, []
    set_name = norm(row.get(set_col)).lower()
    score = 0.0
    reasons: list[str] = []
    for keyword, value in SET_KEYWORDS.get(profile, {}).items():
        if keyword in set_name:
            score += value
            reasons.append(f"set synergy '{keyword}' (+{value})")
    return score, reasons


def ammo_economy_score(row: pd.Series, cols: dict[str, str | None], target_slot: str, profile: str) -> tuple[float, list[str]]:
    ammo_col = cols.get("ammo")
    if not ammo_col:
        return 0.0, []
    ammo = norm(row.get(ammo_col)).lower()
    score = 0.0
    reasons: list[str] = []
    if profile == "gm":
        if target_slot in {"kinetic", "energy"} and "primary" in ammo:
            score += 0.6
            reasons.append("primary ammo stability (+0.6)")
        if target_slot == "power" and "heavy" in ammo:
            score -= 0.2
            reasons.append("heavy ammo dependency (-0.2)")
    if profile == "dps" and target_slot == "power" and "heavy" in ammo:
        score += 0.2
        reasons.append("heavy ammo acceptable for DPS role (+0.2)")
    return score, reasons


def score_candidate(row: pd.Series, cols: dict[str, str | None], profile: str, target_slot: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    bucket = norm(row.get(cols.get("bucket"))) if cols.get("bucket") else ""
    if bucket and bucket_matches(bucket, target_slot):
        score += 2.0
        reasons.append(f"matches {target_slot} bucket (+2.0)")

    power_col = cols.get("power")
    if power_col:
        power = to_float(row.get(power_col))
        power_bonus = power / 100.0
        score += power_bonus
        reasons.append(f"power {int(power)} (+{round(power_bonus,2)})")

    if cols.get("equipped") and is_truthy(row.get(cols["equipped"])):
        score += 1.0
        reasons.append("already equipped (+1.0)")
    if cols.get("masterwork") and is_truthy(row.get(cols["masterwork"])):
        score += 0.8
        reasons.append("masterworked (+0.8)")
    if cols.get("crafted") and is_truthy(row.get(cols["crafted"])):
        score += 0.7
        reasons.append("crafted (+0.7)")
    if cols.get("enhanced") and is_truthy(row.get(cols["enhanced"])):
        score += 0.8
        reasons.append("enhanced traits (+0.8)")
    if cols.get("locked") and is_truthy(row.get(cols["locked"])):
        score += 0.2
        reasons.append("locked/favorited (+0.2)")

    item_type = norm(row.get(cols.get("type"))) if cols.get("type") else ""
    is_weapon = any(x in item_type.lower() for x in ["rifle", "bow", "launcher", "machine gun", "trace", "sidearm", "hand cannon", "shotgun", "fusion", "sniper", "glaive", "sword"])
    if target_slot in {"kinetic", "energy", "power"} or is_weapon:
        delta, detail = weapon_roll_score(row, cols, profile)
        score += delta
        reasons.extend(detail)
        delta, detail = ammo_economy_score(row, cols, target_slot, profile)
        score += delta
        reasons.extend(detail)
    else:
        delta, detail = armor_stat_score(row, cols, profile)
        score += delta
        reasons.extend(detail)
        delta, detail = set_bonus_score(row, cols, profile)
        score += delta
        reasons.extend(detail)

    return round(score, 2), reasons


def rank_item_copies(df: pd.DataFrame, item_name: str, target_slot: str, profile: str, cols: dict[str, str | None]) -> list[dict[str, Any]]:
    name_col = cols["name"]
    if not name_col:
        return []
    matches = df[df[name_col].astype(str).str.strip().eq(item_name)].copy()
    ranked: list[dict[str, Any]] = []
    for _, row in matches.iterrows():
        score, reasons = score_candidate(row, cols, profile, target_slot)
        ranked.append({
            "name": item_name,
            "slot": target_slot,
            "score": score,
            "instance_id": norm(row.get(cols.get("id"))) if cols.get("id") else None,
            "hash": norm(row.get(cols.get("hash"))) if cols.get("hash") else None,
            "owner": norm(row.get(cols.get("owner"))) if cols.get("owner") else None,
            "bucket": norm(row.get(cols.get("bucket"))) if cols.get("bucket") else None,
            "power": int(to_float(row.get(cols.get("power")))) if cols.get("power") else None,
            "crafted": is_truthy(row.get(cols.get("crafted"))) if cols.get("crafted") else False,
            "enhanced": is_truthy(row.get(cols.get("enhanced"))) if cols.get("enhanced") else False,
            "masterworked": is_truthy(row.get(cols.get("masterwork"))) if cols.get("masterwork") else False,
            "reasons": reasons,
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def build_selection_summary(shell: dict[str, str], ranked: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for slot, item_name in [("kinetic", shell["kinetic"]), ("energy", shell["energy"]), ("power", shell["power"]), ("legs", shell["armor_exotic"])]:
        candidates = ranked.get(slot, [])
        best = candidates[0] if candidates else {
            "name": item_name,
            "slot": slot,
            "score": None,
            "instance_id": None,
            "hash": None,
            "owner": None,
            "bucket": None,
            "power": None,
            "crafted": False,
            "enhanced": False,
            "masterworked": False,
            "reasons": ["no matching copy found"],
        }
        selected[slot] = best
    return selected


def render_md(profile: str, shell: dict[str, str], selected: dict[str, Any], ranked: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# Warmind Phase 11.5 Refinement",
        "",
        f"- Profile: **{profile}**",
        f"- Kinetic Choice: **{shell['kinetic']}**",
        f"- Energy Choice: **{shell['energy']}**",
        f"- Power Choice: **{shell['power']}**",
        f"- Exotic Armor Choice: **{shell['armor_exotic']}**",
        "",
        "## Best Copy Selected",
    ]
    for slot in ["kinetic", "energy", "power", "legs"]:
        item = selected[slot]
        lines.append(
            f"- **{slot}**: {item.get('name')} | score: {item.get('score')} | power: {item.get('power')} | crafted: {item.get('crafted')} | enhanced: {item.get('enhanced')} | masterworked: {item.get('masterworked')}"
        )
        for reason in item.get('reasons', [])[:6]:
            lines.append(f"  - {reason}")
    lines.extend(["", "## Ranked Candidates"])
    for slot in ["kinetic", "energy", "power", "legs"]:
        lines.append(f"### {slot}")
        candidates = ranked.get(slot, [])
        if not candidates:
            lines.append("- No candidate copies found")
            continue
        for candidate in candidates[:5]:
            lines.append(
                f"- {candidate['name']} | score {candidate['score']} | power {candidate.get('power')} | crafted {candidate.get('crafted')} | enhanced {candidate.get('enhanced')} | owner {candidate.get('owner')} | instance {candidate.get('instance_id')}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warmind Phase 11.5 refinement engine")
    parser.add_argument("--weapons", required=True)
    parser.add_argument("--armor", required=True)
    parser.add_argument("--loadouts", required=False)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    df_w = pd.read_csv(args.weapons).fillna("")
    df_a = pd.read_csv(args.armor).fillna("")
    df = pd.concat([df_w, df_a], ignore_index=True).fillna("")
    ldf = pd.read_csv(args.loadouts).fillna("") if args.loadouts and Path(args.loadouts).exists() else None

    cols = column_map(df)
    if not cols["name"]:
        raise SystemExit("Could not detect item name column in DIM exports.")

    rarity_col = first_col(df, ["Rarity", "Tier Type Name"])
    exotics = df[df[rarity_col].astype(str).str.lower() == "exotic"].copy() if rarity_col else df.copy()
    owned_names = set(norm(x) for x in exotics[cols["name"]] if norm(x))

    profile = detect_profile(ldf)
    shell = select_shell(owned_names)

    ranked = {
        "kinetic": rank_item_copies(df, shell["kinetic"], "kinetic", profile, cols),
        "energy": rank_item_copies(df, shell["energy"], "energy", profile, cols),
        "power": rank_item_copies(df, shell["power"], "power", profile, cols),
        "legs": rank_item_copies(df, shell["armor_exotic"], "legs", profile, cols),
    }
    selected = build_selection_summary(shell, ranked)

    payload = {
        "profile": profile,
        "recommended_shell": shell,
        "selected_best_copies": selected,
        "ranked_candidates": ranked,
        "enhancements": [
            "exact perk parsing",
            "crafted detection",
            "enhanced trait weighting",
            "set bonus scoring",
            "ammo economy scoring",
        ],
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase115_refinement.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write(out / "Phase115 Refinement.md", render_md(profile, shell, selected, ranked))


if __name__ == "__main__":
    main()
