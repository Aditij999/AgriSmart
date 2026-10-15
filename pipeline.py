"""
pipeline.py — Main Pipeline
Focused on 5 Regional Crops: Jowar, Groundnut, Cotton, Sugarcane, Wheat
"""

import os, sys, json, joblib
import pandas as pd
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR  = os.path.join(BASE_DIR, "models")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
sys.path.insert(0, BASE_DIR)

from modules.soil_adjustment           import compute_nutrient_gap, print_adjustment_report, get_supported_crops
from modules.fertilizer_recommendation import recommend_fertilizer, print_fertilizer_report
from modules.yield_model               import predict_yield, load_model as load_yield_model

CROP_MODEL_PATH  = os.path.join(MODEL_DIR, "crop_model.pkl")
YIELD_MODEL_PATH = os.path.join(MODEL_DIR, "yield_model.pkl")


def recommend_crops(soil_input: dict) -> list:
    """Load model + features from .pkl, predict using DataFrame (no warning)."""
    if not os.path.exists(CROP_MODEL_PATH):
        print("⚠️  crop_model.pkl not found. Run: python crop_model.py")
        return []

    saved        = joblib.load(CROP_MODEL_PATH)
    model        = saved["model"]
    feature_cols = saved["features"]

    # Build DataFrame — exact column names from saved features
    sample_df = pd.DataFrame(
        [[soil_input[f] for f in feature_cols]],
        columns=feature_cols
    )

    probs   = model.predict_proba(sample_df)[0]
    ranked  = sorted(zip(model.classes_, probs), key=lambda x: x[1], reverse=True)
    return ranked[:5]


def run_pipeline(soil_input: dict, chosen_crop: str = None) -> dict:
    print("\n" + "="*65)
    print("   SOIL NUTRIENT ANALYSIS — DECISION SUPPORT PIPELINE")
    print("="*65)

    print(f"\n📥 Soil Input:")
    units = {"Nitrogen":"kg/ha","Phosphorus":"kg/ha","Potassium":"kg/ha",
             "Temperature":"°C","Rainfall":"mm","pH":""}
    for k, v in soil_input.items():
        print(f"   {k:<14}: {v} {units.get(k,'')}")

    # Step 1 — Crop Recommendation
    print("\n📌 Step 1: Crop Recommendation (5 regional crops)")
    print("-"*45)
    crop_recs = recommend_crops(soil_input)

    if crop_recs:
        print("   Top 5 for your soil:")
        for i, (crop, prob) in enumerate(crop_recs, 1):
            bar = "█" * int(prob * 30)
            print(f"   {i}. {crop:<14} {prob*100:5.1f}%  {bar}")
        if chosen_crop is None:
            chosen_crop = crop_recs[0][0]
            print(f"\n   ✅ Auto-selected: {chosen_crop}")
    else:
        chosen_crop = chosen_crop or "Jowar"
        print(f"   ℹ️  Defaulting to {chosen_crop}")

    # Step 2 — Soil Adjustment (only for supported crops)
    supported = get_supported_crops()
    if chosen_crop not in supported:
        print(f"\n📌 Step 2: Soil Adjustment")
        print(f"   ℹ️  '{chosen_crop}' not in soil adjustment DB yet.")
        print(f"   Supported: {supported}")
        gap_result = {}
    else:
        print(f"\n📌 Step 2: Soil Adjustment for '{chosen_crop}'")
        gap_result = compute_nutrient_gap(chosen_crop, soil_input)
        print_adjustment_report(chosen_crop, gap_result)

    # Step 3 — Fertilizer
    if chosen_crop in supported:
        print(f"📌 Step 3: Fertilizer Recommendation for '{chosen_crop}'")
        fert_result = recommend_fertilizer(chosen_crop, soil_input)
        print_fertilizer_report(chosen_crop, fert_result)
    else:
        fert_result = {"action_needed": False, "combined_summary": "N/A", "generic_recs": [], "crop_primary": None}

    # Step 4 — Yield
    print("📌 Step 4: Yield Prediction")
    print("-"*45)
    yield_result = {"predicted_yield_kg_ha": "N/A", "interpretation": "Model not found"}
    try:
        yield_model  = load_yield_model(YIELD_MODEL_PATH)
        yield_result = predict_yield(soil_input, model=yield_model, crop=chosen_crop)
        print(f"   🌾 Predicted Yield : {yield_result['predicted_yield_kg_ha']:,.1f} kg/ha")
        print(f"   {yield_result['interpretation']}")
    except FileNotFoundError:
        print("   ⚠️  Run: python modules/yield_model.py")

    # Save JSON report
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"report_{chosen_crop}_{timestamp}.json")
    report = {
        "timestamp": timestamp,
        "soil_input": soil_input,
        "chosen_crop": chosen_crop,

        "top_5_crops": [
            {
                "crop": c,
                "probability": round(p, 4)
            }
            for c, p in crop_recs
        ],

        "soil_adjustment": gap_result,

        "fertilizer": fert_result,

        "yield_prediction": yield_result,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n✅ Report saved → {report_path}")
    print("="*65 + "\n")
    return report


if __name__ == "__main__":
    # Soil input 1 — typical for Sugarcane (high N/K, warm, wet)
    run_pipeline({
        "Nitrogen": 130, "Phosphorus": 70, "Potassium": 110,
        "Temperature": 27, "Rainfall": 1000, "pH": 6.9,
    })
    # Soil input 2 — typical for Groundnut (moderate, semi-arid)
    run_pipeline({
        "Nitrogen": 58, "Phosphorus": 55, "Potassium": 52,
        "Temperature": 28, "Rainfall": 650, "pH": 6.2,
    })
    # Soil input 3 — typical for Wheat (cool, low rainfall)
    run_pipeline({
        "Nitrogen": 34, "Phosphorus": 39, "Potassium": 21,
        "Temperature": 22, "Rainfall": 600, "pH": 6.5,
    })