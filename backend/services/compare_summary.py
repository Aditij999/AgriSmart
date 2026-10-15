"""Plain-language change summary for the Compare feature.

Given two or more saved analyses (as produced by ``history_service.entry_to_dict``)
this builds a farmer-readable description of what changed between them:
soil/weather readings, recommended crop, predicted yield, fertilizer advice
and soil-adjustment status.

Everything written here is derived from values actually stored in the
analyses. Nothing is looked up, assumed or invented: no agronomic causes, no
extra recommendations. The "interpretation" lines only restate how the
stored numbers moved relative to each other, and the summary always carries a
note that it describes differences, not causes.

This module is deliberately independent of the database and the ML pipeline
so it can be tested with plain dictionaries.

Compare is not Crop Rotation. ``recommended_crop`` here is the model's
suggestion for that one analysis and is only ever compared, never treated as
a crop the farmer actually grew.
"""

from __future__ import annotations

import re
from typing import Any

# (key in soil_input, display label, unit, how a change is worded)
#   "delta" -> "Nitrogen increased by 5 kg/ha."
#   "value" -> "Soil pH decreased from 6.4 to 5.4."
SOIL_FIELDS: list[tuple[str, str, str, str]] = [
    ("nitrogen", "Nitrogen", "kg/ha", "delta"),
    ("phosphorus", "Phosphorus", "kg/ha", "delta"),
    ("potassium", "Potassium", "kg/ha", "delta"),
    ("ph", "Soil pH", "", "value"),
    ("temperature", "Temperature", "°C", "delta"),
    ("rainfall", "Rainfall", "mm", "delta"),
]

# Names used by soil_analysis / fertilizer records -> display label + unit.
NUTRIENT_DISPLAY: dict[str, tuple[str, str]] = {
    "Nitrogen": ("Nitrogen", "kg/ha"),
    "Phosphorus": ("Phosphorus", "kg/ha"),
    "Potassium": ("Potassium", "kg/ha"),
    "pH": ("Soil pH", ""),
}

# A change in the model's confidence in its top crop is listed under "key
# changes" only when it moves by at least this many percentage points; smaller
# moves still appear in the crop detail section.
CONFIDENCE_KEY_CHANGE_PP = 5.0

MINUS = "\u2212"


# ── formatting helpers ──────────────────────────────────────────────────
def _num(value: float, places: int = 2) -> str:
    """1515.40 -> '1515.4', 63.0 -> '63', -0.0 -> '0'."""
    text = f"{round(float(value), places):.{places}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _signed(value: float) -> str:
    return f"+{_num(value)}" if value > 0 else f"{MINUS}{_num(abs(value))}"


def _with_unit(value: float, unit: str) -> str:
    return f"{_num(value)} {unit}" if unit else _num(value)


def _pct(probability: float) -> str:
    return f"{_num(probability * 100, 1)}%"


def _clean_rating(text: str) -> str:
    """Drop the leading emoji/spacing from a yield interpretation string."""
    return re.sub(r"^[^\w]+", "", text or "").strip()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _item(text: str, direction: str = "changed", tone: str = "neutral") -> dict[str, str]:
    """direction: up | down | changed | same.  tone: positive | negative | neutral."""
    return {"text": text, "direction": direction, "tone": tone}


def _entry_ref(entry: dict[str, Any]) -> dict[str, Any]:
    label = entry.get("label")
    return {
        "id": entry.get("id"),
        "name": label if label else f"Analysis #{entry.get('id')}",
        "created_at": entry.get("created_at"),
    }


# ── sections ────────────────────────────────────────────────────────────
def _soil_section(before: dict, after: dict, key_changes: list) -> list[dict]:
    items: list[dict] = []
    soil_b = before.get("soil_input") or {}
    soil_a = after.get("soil_input") or {}

    for attr, label, unit, style in SOIL_FIELDS:
        old, new = soil_b.get(attr), soil_a.get(attr)
        if not (_is_number(old) and _is_number(new)):
            continue

        delta = round(new - old, 2)
        if delta == 0:
            items.append(_item(f"{label} unchanged at {_with_unit(new, unit)}.", "same"))
            continue

        direction = "up" if delta > 0 else "down"
        verb = "increased" if delta > 0 else "decreased"

        if style == "value":
            headline = f"{label} {verb} from {_num(old)} to {_num(new)}."
            detail = f"{label} {verb} from {_num(old)} to {_num(new)} ({_signed(delta)})."
        else:
            headline = f"{label} {verb} by {_with_unit(abs(delta), unit)}."
            detail = (
                f"{label} {verb} from {_num(old)} to {_with_unit(new, unit)} "
                f"({_signed(delta)})."
            )

        items.append(_item(detail, direction))
        key_changes.append({"kind": "soil", "direction": direction, "tone": "neutral", "text": headline})

    return items


def _crop_section(before: dict, after: dict, key_changes: list, notes: list) -> list[dict]:
    items: list[dict] = []

    rec_b, rec_a = before.get("recommended_crop"), after.get("recommended_crop")
    prob_b = before.get("recommended_crop_probability")
    prob_a = after.get("recommended_crop_probability")

    if rec_b and rec_a:
        if rec_b != rec_a:
            text = f"Recommended crop changed from {rec_b} to {rec_a}."
            items.append(_item(text))
            key_changes.append({"kind": "crop", "direction": "changed", "tone": "neutral", "text": text})
            if _is_number(prob_b) and _is_number(prob_a):
                items.append(
                    _item(
                        f"Model confidence in its top pick: {_pct(prob_b)} for {rec_b} "
                        f"before, {_pct(prob_a)} for {rec_a} now.",
                        "same",
                    )
                )
        else:
            items.append(_item(f"Recommended crop stays {rec_a}.", "same"))
            if _is_number(prob_b) and _is_number(prob_a):
                diff_pp = round((prob_a - prob_b) * 100, 1)
                if diff_pp != 0:
                    direction = "up" if diff_pp > 0 else "down"
                    text = (
                        f"Model confidence in {rec_a} {'rose' if diff_pp > 0 else 'fell'} "
                        f"from {_pct(prob_b)} to {_pct(prob_a)}."
                    )
                    items.append(_item(text, direction))
                    if abs(diff_pp) >= CONFIDENCE_KEY_CHANGE_PP:
                        key_changes.append(
                            {"kind": "crop", "direction": direction, "tone": "neutral", "text": text}
                        )

    chosen_b, chosen_a = before.get("chosen_crop"), after.get("chosen_crop")
    if chosen_b and chosen_a:
        followed_recommendation = chosen_b == rec_b and chosen_a == rec_a
        if chosen_b != chosen_a:
            # When the farmer simply followed the recommendation both times, the
            # "Recommended crop changed" line above already says it.
            if not followed_recommendation:
                text = f"Target crop changed from {chosen_b} to {chosen_a}."
                items.append(_item(text))
                key_changes.append({"kind": "crop", "direction": "changed", "tone": "neutral", "text": text})
            notes.append(
                f"These analyses were run for different target crops ({chosen_b} and {chosen_a}). "
                "Predicted yield, soil-adjustment status and fertilizer advice are each "
                "calculated for that analysis's own target crop, so read those differences "
                "with that in mind."
            )
        elif not followed_recommendation:
            items.append(_item(f"Target crop is {chosen_a} in both analyses.", "same"))

    top_b = [c.get("crop") for c in before.get("top_crops") or []]
    top_a = [c.get("crop") for c in after.get("top_crops") or []]
    entered = [c for c in top_a if c not in top_b]
    left = [c for c in top_b if c not in top_a]
    if entered or left:
        parts = []
        if entered:
            parts.append(f"newly in the top {len(top_a)}: {', '.join(entered)}")
        if left:
            parts.append(f"no longer in the top {len(top_b)}: {', '.join(left)}")
        items.append(_item("Crop shortlist changed — " + "; ".join(parts) + "."))

    return items


def _yield_section(
    before: dict, after: dict, key_changes: list, notes: list
) -> tuple[list[dict], dict | None]:
    items: list[dict] = []
    # Yields of two different target crops aren't like-for-like, so don't
    # colour the change as better/worse in that case.
    same_target = before.get("chosen_crop") == after.get("chosen_crop")
    yield_b = before.get("predicted_yield_kg_ha")
    yield_a = after.get("predicted_yield_kg_ha")
    change: dict | None = None

    if _is_number(yield_b) and _is_number(yield_a):
        delta = round(yield_a - yield_b, 2)
        percent = round(delta / yield_b * 100, 1) if yield_b else None
        change = {
            "before": float(yield_b),
            "after": float(yield_a),
            "delta": delta,
            "percent": percent,
            "tone": "neutral",
        }

        if delta == 0:
            items.append(_item(f"Predicted yield unchanged at {_num(yield_a)} kg/ha.", "same"))
        else:
            direction = "up" if delta > 0 else "down"
            tone = ("positive" if delta > 0 else "negative") if same_target else "neutral"
            change["tone"] = tone
            verb = "increased" if delta > 0 else "decreased"
            pct_text = f", {_signed(percent)}%" if percent is not None else ""
            items.append(
                _item(
                    f"Predicted yield {verb} from {_num(yield_b)} to {_num(yield_a)} kg/ha "
                    f"({_signed(delta)} kg/ha{pct_text}).",
                    direction,
                    tone,
                )
            )
            key_changes.append(
                {
                    "kind": "yield",
                    "direction": direction,
                    "tone": tone,
                    "text": f"Predicted yield {verb} by {_num(abs(delta))} kg/ha.",
                }
            )
    elif _is_number(yield_b) != _is_number(yield_a):
        notes.append("Predicted yield is missing from one of the two analyses, so it could not be compared.")

    rating_b = _clean_rating((before.get("yield_prediction") or {}).get("interpretation", ""))
    rating_a = _clean_rating((after.get("yield_prediction") or {}).get("interpretation", ""))
    if rating_b and rating_a and rating_b != rating_a:
        items.append(_item(f"Yield rating changed from \u201c{rating_b}\u201d to \u201c{rating_a}\u201d."))

    return items, change


def _rec_label(rec: dict) -> str:
    return f"{rec.get('nutrient', '')} {str(rec.get('condition', '')).lower()}: {rec.get('fertilizer', '')}"


def _sentence(text: str | None) -> str:
    text = (text or "").strip()
    return text if not text or text.endswith((".", "!", "?")) else text + "."


def _rec_key(rec: dict) -> tuple:
    return (rec.get("nutrient"), rec.get("condition"), rec.get("fertilizer"))


def _fertilizer_section(before: dict, after: dict, key_changes: list) -> list[dict]:
    items: list[dict] = []
    fert_b = before.get("fertilizer") or {}
    fert_a = after.get("fertilizer") or {}
    recs_b = fert_b.get("generic_recs") or []
    recs_a = fert_a.get("generic_recs") or []

    keys_b = {_rec_key(r) for r in recs_b}
    keys_a = {_rec_key(r) for r in recs_a}
    added = [r for r in recs_a if _rec_key(r) not in keys_b]
    removed = [r for r in recs_b if _rec_key(r) not in keys_a]
    kept = [r for r in recs_a if _rec_key(r) in keys_b]

    if not recs_b and not recs_a:
        items.append(_item("No corrective fertilizer is advised in either analysis.", "same"))

    for rec in added:
        ratio = rec.get("npk_ratio")
        ratio_text = f" ({ratio})" if ratio and ratio != "-" else ""
        items.append(_item(f"New advice \u2014 {_rec_label(rec)}{ratio_text}. {_sentence(rec.get('dose_note'))}".strip(), "up"))
    for rec in removed:
        items.append(_item(f"No longer applies \u2014 {_rec_label(rec)}.", "down"))
    for rec in kept:
        items.append(_item(f"Unchanged \u2014 {_rec_label(rec)}.", "same"))

    if added:
        key_changes.append(
            {
                "kind": "fertilizer",
                "direction": "up",
                "tone": "neutral",
                "text": "Fertilizer advice added — " + "; ".join(_rec_label(r) for r in added) + ".",
            }
        )
    if removed:
        key_changes.append(
            {
                "kind": "fertilizer",
                "direction": "down",
                "tone": "neutral",
                "text": "Fertilizer advice no longer needed — " + "; ".join(_rec_label(r) for r in removed) + ".",
            }
        )

    primary_b = (fert_b.get("crop_primary") or {}).get("fertilizer")
    primary_a = (fert_a.get("crop_primary") or {}).get("fertilizer")
    if primary_b and primary_a:
        if primary_b != primary_a:
            text = f"Crop-specific primary fertilizer changed from {primary_b} to {primary_a}."
            items.append(_item(text))
            key_changes.append({"kind": "fertilizer", "direction": "changed", "tone": "neutral", "text": text})
        else:
            items.append(_item(f"Crop-specific primary fertilizer stays {primary_a}.", "same"))

    return items


def _adjustment_section(before: dict, after: dict, key_changes: list) -> tuple[list[dict], tuple[int, int] | None]:
    items: list[dict] = []
    sa_b = before.get("soil_analysis") or {}
    sa_a = after.get("soil_analysis") or {}
    same_target = before.get("chosen_crop") == after.get("chosen_crop")

    shared = [name for name in NUTRIENT_DISPLAY if name in sa_b and name in sa_a]
    for name in shared:
        label, unit = NUTRIENT_DISPLAY[name]
        old, new = sa_b[name], sa_a[name]
        status_b, status_a = old.get("status"), new.get("status")

        if status_b != status_a:
            # Status is measured against the target crop's ideal values, so
            # "better/worse" is only meaningful when the target crop is the same.
            if not same_target:
                tone = "neutral"
            elif status_a == "Optimal":
                tone = "positive"
            elif status_b == "Optimal":
                tone = "negative"
            else:
                tone = "neutral"
            text = f"{label} moved from {status_b} to {status_a}."
            items.append(_item(text, "changed", tone))
            key_changes.append({"kind": "adjustment", "direction": "changed", "tone": tone, "text": text})
        elif status_a == "Optimal":
            items.append(_item(f"{label} stays Optimal.", "same"))
        elif same_target and _is_number(old.get("gap")) and _is_number(new.get("gap")):
            gap_b, gap_a = abs(old["gap"]), abs(new["gap"])
            if round(gap_a - gap_b, 2) == 0:
                items.append(_item(f"{label} is still {status_a}, with the same gap to the ideal value.", "same"))
            else:
                narrowed = gap_a < gap_b
                tone = "positive" if narrowed else "negative"
                direction = "down" if narrowed else "up"
                text = (
                    f"{label} is still {status_a}, but the gap to the ideal value "
                    f"{'narrowed' if narrowed else 'widened'} from {_with_unit(gap_b, unit)} "
                    f"to {_with_unit(gap_a, unit)}."
                )
                items.append(_item(text, direction, tone))
                key_changes.append({"kind": "adjustment", "direction": direction, "tone": tone, "text": text})
        else:
            items.append(_item(f"{label} is {status_a} in both analyses.", "same"))

    counts: tuple[int, int] | None = None
    if shared:
        count_b = sum(1 for n in shared if sa_b[n].get("status") != "Optimal")
        count_a = sum(1 for n in shared if sa_a[n].get("status") != "Optimal")
        counts = (count_b, count_a)
        if count_b != count_a:
            fewer = count_a < count_b
            text = (
                f"Nutrient imbalances {'decreased' if fewer else 'increased'} "
                f"from {count_b} to {count_a}."
            )
            tone = ("positive" if fewer else "negative") if same_target else "neutral"
            direction = "down" if fewer else "up"
            items.append(_item(text, direction, tone))
            key_changes.append({"kind": "adjustment", "direction": direction, "tone": tone, "text": text})

    return items, counts


# ── interpretation ──────────────────────────────────────────────────────
def _interpretation(
    before: dict,
    after: dict,
    yield_change: dict | None,
    counts: tuple[int, int] | None,
    fertilizer_changed: bool,
    adjustment_status_changed: bool,
) -> list[str]:
    """Short readout that only restates how the stored values moved together."""
    lines: list[str] = []

    yield_delta = yield_change["delta"] if yield_change else 0
    same_target = before.get("chosen_crop") == after.get("chosen_crop")
    if yield_delta and counts and counts[0] != counts[1] and same_target:
        yield_word = "higher" if yield_delta > 0 else "lower"
        fewer = counts[1] < counts[0]
        imbalance_word = "fewer" if fewer else "more"
        together = (yield_delta > 0) == fewer
        connector = "and" if together else "but"
        lines.append(
            f"Predicted yield is {yield_word} ({_signed(yield_delta)} kg/ha) {connector} "
            f"there are {imbalance_word} nutrient imbalances ({counts[0]} \u2192 {counts[1]})."
        )
    elif yield_delta:
        lines.append(
            f"Predicted yield is {'higher' if yield_delta > 0 else 'lower'} "
            f"by {_num(abs(yield_delta))} kg/ha in the later analysis."
        )

    rec_b, rec_a = before.get("recommended_crop"), after.get("recommended_crop")
    if rec_b and rec_a and rec_b != rec_a:
        lines.append(
            f"With the later analysis's soil and weather readings, the model's top recommendation "
            f"is {rec_a} rather than {rec_b}."
        )

    if fertilizer_changed and adjustment_status_changed:
        lines.append("Fertilizer advice changed along with the nutrient status changes listed above.")

    return lines


# ── public API ──────────────────────────────────────────────────────────
def summarize_pair(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Describe what changed going from ``before`` to ``after``."""
    key_changes: list[dict] = []
    notes: list[str] = []

    soil_items = _soil_section(before, after, key_changes)
    crop_items = _crop_section(before, after, key_changes, notes)
    yield_items, yield_change = _yield_section(before, after, key_changes, notes)

    fert_start = len(key_changes)
    fert_items = _fertilizer_section(before, after, key_changes)
    fertilizer_changed = len(key_changes) > fert_start

    adj_start = len(key_changes)
    adj_items, counts = _adjustment_section(before, after, key_changes)
    adjustment_status_changed = any(
        c["kind"] == "adjustment" and " moved from " in c["text"] for c in key_changes[adj_start:]
    )

    sections = [
        {"id": "soil", "title": "Soil and weather readings", "items": soil_items},
        {"id": "crop", "title": "Crop", "items": crop_items},
        {"id": "yield", "title": "Predicted yield", "items": yield_items},
        {"id": "fertilizer", "title": "Fertilizer advice", "items": fert_items},
        {"id": "adjustment", "title": "Soil adjustment status", "items": adj_items},
    ]
    sections = [s for s in sections if s["items"]]

    crop_change = None
    if before.get("recommended_crop") and after.get("recommended_crop"):
        crop_change = {
            "before": before["recommended_crop"],
            "after": after["recommended_crop"],
            "changed": before["recommended_crop"] != after["recommended_crop"],
        }

    interpretation = _interpretation(
        before, after, yield_change, counts, fertilizer_changed, adjustment_status_changed
    )
    if not key_changes:
        interpretation = ["The two analyses match in every value that was compared."]

    notes.append(
        "This summary lists how the saved values differ. It does not show what caused a change."
    )

    return {
        "from_entry": _entry_ref(before),
        "to_entry": _entry_ref(after),
        "has_changes": bool(key_changes),
        "key_changes": key_changes,
        "interpretation": interpretation,
        "crop_change": crop_change,
        "yield_change": yield_change,
        "sections": sections,
        "notes": notes,
    }


def build_change_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise 2+ analyses, ordered oldest -> newest.

    Every consecutive pair gets its own step. With three or more analyses an
    ``overall`` step (first -> last) is added as well.
    """
    steps = [summarize_pair(entries[i], entries[i + 1]) for i in range(len(entries) - 1)]
    overall = summarize_pair(entries[0], entries[-1]) if len(entries) > 2 else None
    return {"steps": steps, "overall": overall}
