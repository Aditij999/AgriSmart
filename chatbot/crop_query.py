"""Detect a named crop in a chat question and, when needed, recompute

soil / fertilizer / yield for that crop from this run's soil readings.

The chatbot must never answer a Groundnut question with this run's Jowar
numbers. When the farmer names a supported crop that is not the run's
target crop, we reuse the same ML modules the pipeline already uses
(`compute_nutrient_gap`, `recommend_fertilizer`, `predict_yield`) on the
same soil dict — no invented figures, no second copy of the business rules.
"""

from __future__ import annotations

import copy
import re

SUPPORTED_CROPS = ["Cotton", "Groundnut", "Jowar", "Sugarcane", "Wheat"]

# Longer / more specific aliases first so "sugar cane" wins over a stray "cane".
_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Groundnut",
        (
            "groundnut",
            "ground nut",
            "peanut",
            "peanuts",
            "मूंगफली",
            "मुंगफली",
            "मूँगफली",
            "शेंगदाणा",
            "शेंगदाणे",
            "शेंगदाण्या",
        ),
    ),
    (
        "Sugarcane",
        ("sugarcane", "sugar cane", "गन्ना", "ऊस"),
    ),
    (
        "Cotton",
        ("cotton", "कपास", "कापूस"),
    ),
    (
        "Wheat",
        ("wheat", "गेहूं", "गेहूँ", "गहू"),
    ),
    (
        "Jowar",
        ("jowar", "sorghum", "ज्वार", "ज्वारी"),
    ),
]


def mentioned_crop(user_message: str) -> str | None:
    """Return the one supported crop named in the message, or None.

    None also means "more than one crop was named" — we refuse to guess
    which yield they wanted.
    """
    raw = user_message or ""
    lower = raw.lower()
    hits: list[str] = []
    for crop, aliases in _ALIASES:
        for alias in aliases:
            if alias.isascii():
                if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lower):
                    hits.append(crop)
                    break
            elif alias in raw:
                hits.append(crop)
                break
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    return None


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def analysis_for_crop(report: dict | None, asked_crop: str | None) -> dict:
    """Return a report whose soil/fertilizer/yield numbers match `asked_crop`.

    `chosen_crop` and `top_5_crops` stay as they were (this run's target and
    the crop-model ranking). Numeric blocks are recomputed only when the
    asked crop differs from the run's target and soil readings are present.
    """
    report = dict(report or {})
    if not asked_crop:
        return report

    report["query_crop"] = asked_crop
    chosen = report.get("chosen_crop")
    if chosen and str(chosen).lower() == asked_crop.lower():
        return report

    soil = report.get("soil_input") or {}
    if not all(key in soil for key in ("Nitrogen", "Phosphorus", "Potassium", "pH")):
        report["_bind_failed"] = True
        return report

    try:
        from modules.fertilizer_recommendation import recommend_fertilizer
        from modules.soil_adjustment import compute_nutrient_gap
        from modules.yield_model import predict_yield

        bound = copy.deepcopy(report)
        bound["query_crop"] = asked_crop
        bound["soil_adjustment"] = _jsonable(compute_nutrient_gap(asked_crop, soil))
        bound["fertilizer"] = _jsonable(recommend_fertilizer(asked_crop, soil))
        bound["yield_prediction"] = _jsonable(predict_yield(soil, crop=asked_crop))
        bound["_crop_override"] = True
        bound["_original_crop"] = chosen
        bound.pop("_bind_failed", None)
        return bound
    except Exception:
        report["_bind_failed"] = True
        return report


def crop_for_numbers(report: dict | None) -> str | None:
    report = report or {}
    return report.get("query_crop") or report.get("chosen_crop")
