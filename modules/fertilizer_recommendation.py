"""
fertilizer_recommendation.py
-----------------------------
Fertilizer Recommendation Module — Phase II Module 2

Rule-based system covering the 5 regional crops:
Jowar, Groundnut, Cotton, Sugarcane, Wheat
Works on top of the Soil Adjustment Engine output.
"""

from modules.soil_adjustment import compute_nutrient_gap, get_supported_crops

# ─────────────────────────────────────────────
# GENERIC NUTRIENT → FERTILIZER RULES
# Same logic applies to all crops
# ─────────────────────────────────────────────
GENERIC_FERTILIZER_RULES = [
    {
        "nutrient": "Nitrogen", "condition": "Low",
        "fertilizer": "Urea", "npk_ratio": "46-0-0",
        "dose_note": "Apply in 2 splits — basal + top-dress at 30 days",
        "reason": "Urea is the most concentrated and economical N source (46% N).",
    },
    {
        "nutrient": "Phosphorus", "condition": "Low",
        "fertilizer": "DAP (Di-Ammonium Phosphate)", "npk_ratio": "18-46-0",
        "dose_note": "Apply as basal dose at sowing",
        "reason": "DAP provides both N and P; ideal for root development.",
    },
    {
        "nutrient": "Potassium", "condition": "Low",
        "fertilizer": "MOP (Muriate of Potash)", "npk_ratio": "0-0-60",
        "dose_note": "Apply at basal or after 30 days of sowing",
        "reason": "MOP is the most concentrated and affordable K source (60% K₂O).",
    },
    {
        "nutrient": "Nitrogen", "condition": "High",
        "fertilizer": "None — Reduce N application", "npk_ratio": "-",
        "dose_note": "Skip N fertilizer this season; allow soil to deplete naturally",
        "reason": "Excess N causes vegetative overgrowth and reduces grain yield.",
    },
    {
        "nutrient": "Phosphorus", "condition": "High",
        "fertilizer": "None — Skip P fertilizer", "npk_ratio": "-",
        "dose_note": "Avoid phosphate fertilizers this season",
        "reason": "Excess P locks out zinc and iron micronutrients.",
    },
    {
        "nutrient": "Potassium", "condition": "High",
        "fertilizer": "None — Skip K fertilizer", "npk_ratio": "-",
        "dose_note": "Skip potash fertilizer this season",
        "reason": "Excess K inhibits magnesium and calcium uptake.",
    },
    {
        "nutrient": "pH", "condition": "Low",
        "fertilizer": "Hydrated Lime — Ca(OH)₂", "npk_ratio": "-",
        "dose_note": "Apply 1–2 tonnes/ha and incorporate into soil before sowing",
        "reason": "Acidic soil makes P unavailable; lime raises pH toward neutral.",
    },
    {
        "nutrient": "pH", "condition": "High",
        "fertilizer": "Elemental Sulphur or Ammonium Sulphate", "npk_ratio": "-",
        "dose_note": "Apply elemental sulphur @ 20–30 kg/ha",
        "reason": "Alkaline soil reduces Fe/Mn availability; sulphur acidifies soil.",
    },
]

# ─────────────────────────────────────────────
# CROP-SPECIFIC PRIMARY FERTILIZER — 5 crops only
# ─────────────────────────────────────────────
CROP_PRIMARY_FERTILIZER = {
    "Cotton":    {"fertilizer": "DAP",                    "note": "Preferred basal fertilizer for Cotton in Black Soil"},
    "Groundnut": {"fertilizer": "Chelated Micronutrient", "note": "Groundnut often needs micronutrient support alongside NPK"},
    "Jowar":     {"fertilizer": "10:26:26 NPK",           "note": "High P+K ratio supports Jowar's grain and stem development"},
    "Sugarcane": {"fertilizer": "MOP",                    "note": "Sugarcane is K-hungry; MOP is the standard choice"},
    "Wheat":     {"fertilizer": "19:19:19 NPK",           "note": "Equal ratio NPK suits Wheat's balanced N/P/K demand"},
}


# ─────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────
def _get_triggered_rules(gap_result: dict) -> list:
    """Match nutrient status to fertilizer rules."""
    triggered = []
    for rule in GENERIC_FERTILIZER_RULES:
        nutrient  = rule["nutrient"]
        condition = rule["condition"]
        if nutrient in gap_result and gap_result[nutrient]["status"] == condition:
            triggered.append(rule)
    return triggered


def recommend_fertilizer(crop: str, current_soil: dict) -> dict:
    """
    Generate fertilizer recommendation for a crop and soil reading.

    Parameters
    ----------
    crop         : str  — any of the 16 supported crops
    current_soil : dict — Nitrogen, Phosphorus, Potassium, pH

    Returns
    -------
    dict with gap_analysis, generic_recs, crop_primary,
         combined_summary, action_needed
    """
    gap_result   = compute_nutrient_gap(crop, current_soil)
    generic_recs = _get_triggered_rules(gap_result)
    crop_primary = CROP_PRIMARY_FERTILIZER.get(crop)

    action_needed = any(
        info["status"] != "Optimal" for info in gap_result.values()
    )

    # Build plain-English summary
    lines = []
    if not action_needed:
        lines.append(f"✅ Soil is well-balanced for {crop}. No corrections needed.")
    else:
        for rec in generic_recs:
            if rec["condition"] == "Low":
                lines.append(
                    f"• [{rec['nutrient']} LOW] → Apply {rec['fertilizer']} "
                    f"({rec['npk_ratio']}). {rec['dose_note']}."
                )
            else:
                lines.append(
                    f"• [{rec['nutrient']} HIGH] → {rec['fertilizer']}. "
                    f"{rec['dose_note']}."
                )
        if crop_primary:
            lines.append(
                f"\n🌾 Primary fertilizer for {crop}: {crop_primary['fertilizer']}"
                f" — {crop_primary['note']}"
            )

    return {
        "gap_analysis":     gap_result,
        "generic_recs":     generic_recs,
        "crop_primary":     crop_primary,
        "combined_summary": "\n".join(lines),
        "action_needed":    action_needed,
    }


def print_fertilizer_report(crop: str, result: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  FERTILIZER RECOMMENDATION — Crop: {crop}")
    print(f"{'='*60}")

    gap = result["gap_analysis"]
    print(f"\n📊 Nutrient Status:")
    icons = {"Optimal": "✅", "Low": "🔴", "High": "🟡"}
    for nutrient, info in gap.items():
        print(f"  {icons.get(info['status'],'')} {nutrient:<14}: {info['status']:7}  "
              f"(Current: {info['current']:.1f}, Ideal: {info['ideal']:.1f}, "
              f"Gap: {info['gap']:+.1f})")

    print(f"\n💊 Fertilizer Actions:")
    if result["generic_recs"]:
        for rec in result["generic_recs"]:
            icon = "⬆️" if rec["condition"] == "Low" else "⬇️"
            print(f"\n  {icon} {rec['nutrient']} is {rec['condition']}")
            print(f"     Fertilizer : {rec['fertilizer']} ({rec['npk_ratio']})")
            print(f"     Dosage     : {rec['dose_note']}")
            print(f"     Why        : {rec['reason']}")
    else:
        print("  ✅ No corrections needed.")

    if result["crop_primary"]:
        cp = result["crop_primary"]
        print(f"\n🌾 Crop-Specific Primary Fertilizer:")
        print(f"   {cp['fertilizer']} — {cp['note']}")

    print(f"\n📋 Summary:\n{result['combined_summary']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Test Cotton
    sample = {"Nitrogen": 88, "Phosphorus": 50, "Potassium": 60, "pH": 6.7}
    result = recommend_fertilizer("Cotton", sample)
    print_fertilizer_report("Cotton", result)

    # Test Wheat
    sample2 = {"Nitrogen": 34, "Phosphorus": 39, "Potassium": 21, "pH": 6.5}
    result2 = recommend_fertilizer("Wheat", sample2)
    print_fertilizer_report("Wheat", result2)
