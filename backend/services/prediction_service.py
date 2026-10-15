"""Thin adapter around the existing ML pipeline.

Nothing here re-implements or re-trains anything: `pipeline.run_pipeline` is
the same entry point the Streamlit app's modules use, and it already chains
crop recommendation -> soil adjustment -> fertilizer rules -> yield model.
This module only converts between the API's JSON shapes and the pipeline's
dicts, and silences the pipeline's console report.
"""

import contextlib
import io
import os
import sys
from typing import Any

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.soil_adjustment import get_supported_crops  # noqa: E402
from pipeline import run_pipeline  # noqa: E402

FIELD_TO_PIPELINE_KEY = {
    "nitrogen": "Nitrogen",
    "phosphorus": "Phosphorus",
    "potassium": "Potassium",
    "ph": "pH",
    "temperature": "Temperature",
    "rainfall": "Rainfall",
}

UNITS = {
    "nitrogen": "kg/ha",
    "phosphorus": "kg/ha",
    "potassium": "kg/ha",
    "ph": "",
    "temperature": "°C",
    "rainfall": "mm",
}


def supported_crops() -> list[str]:
    return get_supported_crops()


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def run_analysis(soil: dict[str, float], crop: str | None = None) -> dict[str, Any]:
    """Run the full pipeline for one soil reading and return a JSON-safe report."""
    soil_input = {FIELD_TO_PIPELINE_KEY[field]: float(soil[field]) for field in FIELD_TO_PIPELINE_KEY}

    with contextlib.redirect_stdout(io.StringIO()):
        report = run_pipeline(soil_input, chosen_crop=crop)

    report = _to_jsonable(report)

    top_crops = [
        {"crop": item["crop"], "probability": float(item["probability"])}
        for item in report.get("top_5_crops", [])
    ]
    yield_prediction = report.get("yield_prediction") or {}
    raw_yield = yield_prediction.get("predicted_yield_kg_ha")
    predicted_yield = float(raw_yield) if isinstance(raw_yield, (int, float)) else None

    return {
        "soil_input": {field: float(soil[field]) for field in FIELD_TO_PIPELINE_KEY},
        "chosen_crop": report.get("chosen_crop"),
        "recommended_crop": top_crops[0]["crop"] if top_crops else None,
        "recommended_crop_probability": top_crops[0]["probability"] if top_crops else None,
        "predicted_yield_kg_ha": predicted_yield,
        "top_crops": top_crops,
        "soil_analysis": report.get("soil_adjustment") or {},
        "fertilizer": report.get("fertilizer") or {},
        "yield_prediction": yield_prediction,
    }


def to_chatbot_report(entry: dict[str, Any]) -> dict[str, Any]:
    """Reshape a stored/returned prediction into the dict the chatbot expects."""
    return {
        "chosen_crop": entry.get("chosen_crop"),
        "top_5_crops": entry.get("top_crops") or [],
        "soil_input": {
            FIELD_TO_PIPELINE_KEY[field]: value
            for field, value in (entry.get("soil_input") or {}).items()
            if field in FIELD_TO_PIPELINE_KEY
        },
        "soil_adjustment": entry.get("soil_analysis") or {},
        "fertilizer": entry.get("fertilizer") or {},
        "yield_prediction": entry.get("yield_prediction") or {},
    }
