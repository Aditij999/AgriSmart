"""Unit tests for the Compare change summary (no server, DB or ML models needed).

Run:  python -m backend.test_compare_summary
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.compare_summary import build_change_summary  # noqa: E402
from modules.fertilizer_recommendation import recommend_fertilizer  # noqa: E402
from modules.soil_adjustment import compute_nutrient_gap  # noqa: E402


def make_entry(entry_id, crop, recommended, prob, n, p, k, ph, temp, rain, yld, label=None):
    soil = {"Nitrogen": n, "Phosphorus": p, "Potassium": k, "pH": ph}
    rating = "\U0001f7e1 Moderate yield \u2014 improvement possible."
    return {
        "id": entry_id,
        "created_at": None,
        "label": label,
        "soil_input": {
            "nitrogen": n, "phosphorus": p, "potassium": k,
            "ph": ph, "temperature": temp, "rainfall": rain,
        },
        "chosen_crop": crop,
        "recommended_crop": recommended,
        "recommended_crop_probability": prob,
        "predicted_yield_kg_ha": yld,
        "top_crops": [{"crop": recommended, "probability": prob}],
        "soil_analysis": compute_nutrient_gap(crop, soil),
        "fertilizer": recommend_fertilizer(crop, soil),
        "yield_prediction": {"predicted_yield_kg_ha": yld, "interpretation": rating},
    }


def texts(step):
    return [c["text"] for c in step["key_changes"]]


def test_user_example():
    previous = make_entry(1, "Jowar", "Jowar", 0.7, 58, 43, 37, 6.4, 27, 650, 1368.8)
    current = make_entry(2, "Wheat", "Wheat", 0.8, 63, 60, 42, 5.4, 27, 650, 1515.4)
    summary = build_change_summary([previous, current])
    step = summary["steps"][0]
    got = texts(step)

    for expected in [
        "Nitrogen increased by 5 kg/ha.",
        "Phosphorus increased by 17 kg/ha.",
        "Potassium increased by 5 kg/ha.",
        "Soil pH decreased from 6.4 to 5.4.",
        "Recommended crop changed from Jowar to Wheat.",
        "Predicted yield increased by 146.6 kg/ha.",
    ]:
        assert expected in got, f"missing: {expected}\n{json.dumps(got, indent=2)}"

    assert summary["overall"] is None
    assert step["yield_change"]["delta"] == 146.6
    assert step["yield_change"]["percent"] == 10.7
    # Unchanged readings must not be reported as changes.
    assert not any("Temperature" in t or "Rainfall" in t for t in got)
    # Followed the recommendation both times -> no duplicate "Target crop" bullet.
    assert not any(t.startswith("Target crop") for t in got)
    # Different target crops -> caveat shown and no better/worse colouring.
    assert any("different target crops" in n for n in step["notes"])
    assert all(c["tone"] == "neutral" for c in step["key_changes"])
    assert step["yield_change"]["delta"] == 146.6
    return step


def test_target_differs_from_recommendation():
    a = make_entry(1, "Wheat", "Jowar", 0.6, 58, 43, 37, 6.4, 27, 650, 1300.0)
    b = make_entry(2, "Cotton", "Jowar", 0.6, 58, 43, 37, 6.4, 27, 650, 1500.0)
    step = build_change_summary([a, b])["steps"][0]
    assert "Target crop changed from Wheat to Cotton." in texts(step)
    assert "Recommended crop changed" not in " ".join(texts(step))


def test_identical_analyses():
    a = make_entry(1, "Wheat", "Wheat", 0.8, 90, 53, 50, 6.7, 26, 700, 2000.0)
    b = make_entry(2, "Wheat", "Wheat", 0.8, 90, 53, 50, 6.7, 26, 700, 2000.0)
    step = build_change_summary([a, b])["steps"][0]
    assert not step["has_changes"] and step["key_changes"] == []
    assert "match in every value" in step["interpretation"][0]


def test_same_crop_fertilizer_and_status_changes():
    low = make_entry(1, "Wheat", "Wheat", 0.6, 30, 20, 15, 5.4, 25, 500, 1100.0)
    good = make_entry(2, "Wheat", "Wheat", 0.9, 92, 53, 50, 6.7, 25, 500, 2200.0)
    step = build_change_summary([low, good])["steps"][0]
    got = texts(step)
    assert "Nitrogen moved from Low to Optimal." in got
    assert any(t.startswith("Fertilizer advice no longer needed") for t in got)
    assert any(t.startswith("Nutrient imbalances decreased") for t in got)
    assert not any("different target crops" in n for n in step["notes"])
    assert any("Predicted yield is higher" in line and "fewer" in line for line in step["interpretation"])


def test_three_analyses_get_steps_and_overall():
    a = make_entry(1, "Wheat", "Wheat", 0.6, 30, 20, 15, 5.4, 25, 500, 1100.0)
    b = make_entry(2, "Wheat", "Wheat", 0.7, 60, 40, 30, 6.0, 25, 500, 1500.0)
    c = make_entry(3, "Wheat", "Wheat", 0.9, 92, 53, 50, 6.7, 25, 500, 2200.0)
    summary = build_change_summary([a, b, c])
    assert len(summary["steps"]) == 2
    assert summary["overall"]["from_entry"]["id"] == 1
    assert summary["overall"]["to_entry"]["id"] == 3


def test_missing_yield_does_not_crash():
    a = make_entry(1, "Wheat", "Wheat", 0.6, 30, 20, 15, 5.4, 25, 500, None)
    b = make_entry(2, "Wheat", "Wheat", 0.9, 92, 53, 50, 6.7, 25, 500, 2200.0)
    step = build_change_summary([a, b])["steps"][0]
    assert step["yield_change"] is None
    assert any("missing" in n for n in step["notes"])


if __name__ == "__main__":
    example = test_user_example()
    test_target_differs_from_recommendation()
    test_identical_analyses()
    test_same_crop_fertilizer_and_status_changes()
    test_three_analyses_get_steps_and_overall()
    test_missing_yield_does_not_crash()
    print("All compare-summary tests passed.\n")
    print("Key changes for the example:")
    for change in example["key_changes"]:
        print("  •", change["text"])
    print("\nInterpretation:")
    for line in example["interpretation"]:
        print("  ", line)
    print("\nNotes:")
    for note in example["notes"]:
        print("  ", note)
    print("\nDetail sections:")
    for section in example["sections"]:
        print(f"  [{section['title']}]")
        for item in section["items"]:
            print(f"    ({item['direction']}/{item['tone']}) {item['text']}")
