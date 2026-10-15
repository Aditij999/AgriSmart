"""
soil_adjustment.py
------------------
Soil Adjustment Engine — Phase II Module 1

Compares current soil readings against ideal values for the 5 regional crops:
Jowar, Groundnut, Cotton, Sugarcane, Wheat

Ideal values are computed from Dataset 1 (crop_fertilizer_data.csv) means.

Formula: gap = Ideal − Current
  + gap → need to INCREASE
  - gap → need to DECREASE
  within tolerance → OPTIMAL
"""

# ─────────────────────────────────────────────
# IDEAL VALUES — 5 regional crops
# Source: mean of crop_fertilizer_data.csv per crop
# Units: N, P, K in kg/ha | pH dimensionless
# ─────────────────────────────────────────────
IDEAL_VALUES = {
    "Cotton":    {"Nitrogen": 117.6, "Phosphorus": 56.7, "Potassium":  60.8, "pH": 7.0},
    "Groundnut": {"Nitrogen":  29.4, "Phosphorus": 41.4, "Potassium":  27.9, "pH": 6.5},
    "Jowar":     {"Nitrogen":  54.6, "Phosphorus": 37.0, "Potassium":  36.6, "pH": 6.8},
    "Sugarcane": {"Nitrogen": 131.6, "Phosphorus": 70.6, "Potassium": 114.0, "pH": 6.9},
    "Wheat":     {"Nitrogen":  91.8, "Phosphorus": 53.1, "Potassium":  49.7, "pH": 6.7},
}

# Tolerance bands — gap within ±TOLERANCE is treated as OPTIMAL
TOLERANCE = {
    "Nitrogen":   10.0,
    "Phosphorus":  5.0,
    "Potassium":   5.0,
    "pH":          0.3,
}


def get_supported_crops() -> list:
    return list(IDEAL_VALUES.keys())


def compute_nutrient_gap(crop: str, current: dict) -> dict:
    """
    Compare current soil values against ideal for the given crop.

    Parameters
    ----------
    crop    : str  — any of the 16 supported crops
    current : dict — keys: Nitrogen, Phosphorus, Potassium, pH

    Returns
    -------
    dict per nutrient: current, ideal, gap, action, status
    """
    if crop not in IDEAL_VALUES:
        raise ValueError(
            f"Crop '{crop}' not supported.\nSupported crops: {get_supported_crops()}"
        )

    ideal  = IDEAL_VALUES[crop]
    result = {}

    for nutrient in ["Nitrogen", "Phosphorus", "Potassium", "pH"]:
        if nutrient not in current:
            raise KeyError(f"Missing '{nutrient}' in soil input.")

        curr_val  = float(current[nutrient])
        ideal_val = float(ideal[nutrient])
        gap       = round(ideal_val - curr_val, 2)
        tol       = TOLERANCE[nutrient]

        if abs(gap) <= tol:
            action, status = "OPTIMAL", "Optimal"
        elif gap > 0:
            action, status = "INCREASE", "Low"
        else:
            action, status = "DECREASE", "High"

        result[nutrient] = {
            "current": curr_val,
            "ideal":   ideal_val,
            "gap":     gap,
            "action":  action,
            "status":  status,
        }

    return result


def print_adjustment_report(crop: str, gap_result: dict) -> None:
    print(f"\n{'='*55}")
    print(f"  SOIL ADJUSTMENT REPORT — Crop: {crop}")
    print(f"{'='*55}")
    print(f"{'Nutrient':<14} {'Current':>8} {'Ideal':>8} {'Gap':>8}  Action")
    print(f"{'-'*55}")

    icons = {"INCREASE": "⬆ ADD", "DECREASE": "⬇ REDUCE", "OPTIMAL": "✅ OK"}
    for nutrient, info in gap_result.items():
        unit = "" if nutrient == "pH" else ""
        print(
            f"{nutrient:<14} {info['current']:>8.1f}  "
            f"{info['ideal']:>7.1f}  "
            f"{info['gap']:>+7.1f}  {icons[info['action']]}"
        )
    print(f"{'='*55}\n")


if __name__ == "__main__":
    sample = {"Nitrogen": 88, "Phosphorus": 50, "Potassium": 60, "pH": 6.7}
    for crop in get_supported_crops():
        result = compute_nutrient_gap(crop, sample)
        print_adjustment_report(crop, result)
