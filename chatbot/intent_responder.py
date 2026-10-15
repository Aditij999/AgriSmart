"""
Template-based responses for the Smart Agri chatbot's "intent" fast path.

This is a rewrite of the original chatbot/response_engine.py, adapted to the
report dict that app.py / backend/services/prediction_service.py assembles
(crop recommendation, soil status, fertilizer plan, yield prediction) rather
than the report_*.json files the old CLI chatbot read from disk. Every field
is read defensively with .get(), since demo/fallback data won't always have
every key that the full ML pipeline produces.

Multilingual support (English / Hindi / Marathi) is layered on top via
chatbot/language.py (script + keyword based language detection) and
chatbot/i18n.py (translated message templates and crop/nutrient/status
names). The caller (chatbot/router.py) may pass an explicit `lang`
("en"/"hi"/"mr"/"auto"/None); when it isn't a forced supported language,
the reply language is detected from the user's own message, so someone
typing in Hindi or Marathi gets a Hindi or Marathi answer even on their
first message.

Used by chatbot/router.py as the first thing tried for a user message; if no
handler matches (or the intent classifier wasn't confident enough), the
caller falls back to chatbot/gemini_chat.py.
"""

from chatbot.crop_query import crop_for_numbers
from chatbot.language import resolve_language
from chatbot.i18n import crop_name, fert_phrase, format_crop_list, msg, nutrient_name, status_name

SUPPORTED_CROPS = ["Jowar", "Groundnut", "Cotton", "Sugarcane", "Wheat"]

NUTRIENT_INTENTS = {
    "SOIL_NITROGEN": "Nitrogen",
    "SOIL_PHOSPHORUS": "Phosphorus",
    "SOIL_POTASSIUM": "Potassium",
    "SOIL_PH": "pH",
}

# Yield thresholds (kg/ha) mirror modules/yield_model.py's predict_yield().
YIELD_EMOJI = {
    "YIELD_LOW": "⚠️ ",
    "YIELD_MOD": "🟡 ",
    "YIELD_GOOD": "🟢 ",
    "YIELD_HIGH": "🟢 ",
}

# Intents that should never trigger a template — always handed to Gemini
# (or refused outright), because a canned line can't really do them justice.
NO_TEMPLATE_INTENTS = {"OUT_OF_SCOPE", "UNKNOWN"}


def _fmt(value, digits=1):
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _yield_interp_key(predicted_yield_kg_ha):
    try:
        pred = float(predicted_yield_kg_ha)
    except (TypeError, ValueError):
        return None
    if pred < 1000:
        return "YIELD_LOW"
    if pred < 3000:
        return "YIELD_MOD"
    if pred < 15000:
        return "YIELD_GOOD"
    return "YIELD_HIGH"


def generate_response(intent, report, user_message="", lang=None):
    """
    Return a canned answer for `intent` using `report`, or None if this
    intent isn't one the template engine handles (caller should fall back
    to the Gemini API in that case).

    `lang` may be "en" / "hi" / "mr" / "auto" / None. When it isn't a
    forced supported language, the reply language is detected from
    `user_message` (Devanagari script + Hindi/Marathi marker words).
    """
    report = report or {}
    lang = resolve_language(user_message, preferred=lang)
    crop = report.get("chosen_crop")
    number_crop = crop_for_numbers(report) or crop
    override_prefix = ""
    if report.get("_crop_override") and report.get("_original_crop"):
        override_prefix = msg(
            lang,
            "CROP_RECOMPUTED",
            original=crop_name(report.get("_original_crop"), lang),
            crop=crop_name(number_crop, lang),
        )
    if (
        report.get("query_crop")
        and crop
        and str(report.get("query_crop")).lower() != str(crop).lower()
        and not report.get("_crop_override")
    ):
        unavailable = msg(
            lang,
            "CROP_DATA_UNAVAILABLE",
            asked=crop_name(report.get("query_crop"), lang),
            original=crop_name(crop, lang),
        )
    else:
        unavailable = None

    # ---- Small talk / meta ---------------------------------------------
    if intent == "GREETING":
        return msg(lang, "GREETING")

    if intent == "HELP":
        return msg(lang, "HELP")

    if intent == "SYSTEM_OVERVIEW":
        return msg(lang, "SYSTEM_OVERVIEW")

    if intent == "HOW_TO_USE":
        return msg(lang, "HOW_TO_USE")

    if intent == "DASHBOARD":
        return msg(lang, "DASHBOARD")

    if intent == "ML_MODEL_EXPLANATION":
        return msg(lang, "ML_MODEL_EXPLANATION")

    if intent == "SUPPORTED_CROPS":
        return msg(lang, "SUPPORTED_CROPS", crops=format_crop_list(SUPPORTED_CROPS, lang))

    # ---- Crop recommendation --------------------------------------------
    if intent == "CROP_RECOMMENDATION":
        if not crop:
            return None
        return msg(lang, "CROP_RECOMMENDATION", crop=crop_name(crop, lang))

    if intent == "CROP_RECOMMENDATION_EXPLANATION":
        top5 = report.get("top_5_crops") or []
        if not top5:
            return None
        top = top5[0]
        probability = (top.get("probability") or 0) * 100
        return msg(
            lang,
            "CROP_RECOMMENDATION_EXPLANATION",
            crop=crop_name(top.get("crop", crop), lang),
            probability=probability,
        )

    if intent == "CROP_PROBABILITY":
        top5 = report.get("top_5_crops") or []
        if not top5:
            return None
        lines = [msg(lang, "CROP_PROBABILITY_HEADER")]
        for item in top5:
            probability = (item.get("probability") or 0) * 100
            lines.append(
                msg(
                    lang,
                    "CROP_PROBABILITY_LINE",
                    crop=crop_name(item.get("crop"), lang),
                    probability=probability,
                )
            )
        return "\n".join(lines)

    if intent == "CROP_SOIL_MISMATCH":
        top5 = report.get("top_5_crops") or []
        if not top5 or not crop:
            return None
        top_crop = top5[0].get("crop")
        if top_crop and top_crop != crop:
            return msg(
                lang,
                "CROP_MISMATCH_BETTER",
                top_crop=crop_name(top_crop, lang),
                crop=crop_name(crop, lang),
            )
        return msg(lang, "CROP_MISMATCH_BEST", crop=crop_name(crop, lang))

    # ---- Soil -------------------------------------------------------------
    if intent == "SOIL_ANALYSIS":
        if unavailable:
            return unavailable
        soil = report.get("soil_input")
        if not soil:
            return None
        return override_prefix + msg(
            lang,
            "SOIL_ANALYSIS",
            n=soil.get("Nitrogen"),
            p=soil.get("Phosphorus"),
            k=soil.get("Potassium"),
            ph=soil.get("pH"),
            temp=soil.get("Temperature"),
            rain=soil.get("Rainfall"),
        )

    if intent in NUTRIENT_INTENTS:
        if unavailable:
            return unavailable
        nutrient = NUTRIENT_INTENTS[intent]
        soil_adjustment = report.get("soil_adjustment") or {}
        unit = "" if nutrient == "pH" else " kg/ha"
        label_crop = number_crop or crop

        if nutrient not in soil_adjustment:
            current_value = (report.get("soil_input") or {}).get(nutrient)
            if current_value is None or not label_crop:
                return None
            return override_prefix + msg(
                lang,
                "NUTRIENT_NO_ADJUSTMENT",
                nutrient=nutrient_name(nutrient, lang),
                value=current_value,
                unit=unit,
                crop=crop_name(label_crop, lang),
            )

        info = soil_adjustment[nutrient]
        return override_prefix + msg(
            lang,
            "NUTRIENT_STATUS",
            prefix="",
            nutrient=nutrient_name(nutrient, lang),
            current=info.get("current"),
            unit=unit,
            crop=crop_name(label_crop, lang) if label_crop else "",
            ideal=info.get("ideal"),
            status=status_name(info.get("status"), lang),
        )

    if intent == "SOIL_STATUS_EXPLANATION":
        return msg(lang, "SOIL_STATUS_EXPLANATION")

    # ---- Fertilizer ---------------------------------------------------
    fertilizer = report.get("fertilizer") or {}
    recs = fertilizer.get("generic_recs") or []

    if intent == "FERTILIZER_RECOMMENDATION":
        if unavailable:
            return unavailable
        if not fertilizer:
            return None
        fert_crop = number_crop or crop
        if not fertilizer.get("action_needed", bool(recs)):
            return override_prefix + msg(
                lang, "FERTILIZER_BALANCED", prefix="", crop=crop_name(fert_crop, lang) if fert_crop else ""
            )
        lines = [override_prefix + msg(lang, "FERTILIZER_BASED", prefix="")]
        for rec in recs:
            lines.append(
                msg(
                    lang,
                    "FERTILIZER_CONDITION_LINE",
                    nutrient=nutrient_name(rec.get("nutrient"), lang),
                    status=status_name(rec.get("condition"), lang),
                    label=rec.get("fertilizer"),
                )
            )
        crop_primary = fertilizer.get("crop_primary")
        if crop_primary:
            lines.append(
                msg(
                    lang,
                    "FERTILIZER_PRIMARY",
                    crop=crop_name(fert_crop, lang) if fert_crop else "",
                    fertilizer=crop_primary.get("fertilizer"),
                )
            )
        return "\n".join(lines)

    if intent == "FERTILIZER_DOSAGE":
        if unavailable:
            return unavailable
        fert_crop = number_crop or crop
        if not recs:
            return override_prefix + msg(
                lang, "FERTILIZER_DOSAGE_NONE", prefix="", crop=crop_name(fert_crop, lang) if fert_crop else ""
            )
        lines = [override_prefix + msg(lang, "FERTILIZER_DOSAGE_HEADER", prefix="")]
        for rec in recs:
            lines.append(
                msg(
                    lang,
                    "FERTILIZER_DOSAGE_LINE",
                    label=rec.get("fertilizer"),
                    dose=fert_phrase(rec.get("dose_note"), lang),
                )
            )
        return "\n".join(lines)

    if intent == "WHY_FERTILIZER_NEEDED":
        if unavailable:
            return unavailable
        fert_crop = number_crop or crop
        if not recs:
            return override_prefix + msg(
                lang, "WHY_FERT_NONE", prefix="", crop=crop_name(fert_crop, lang) if fert_crop else ""
            )
        lines = [override_prefix + msg(lang, "WHY_FERT_HEADER", prefix="")]
        for rec in recs:
            lines.append(
                msg(
                    lang,
                    "WHY_FERT_LINE",
                    label=rec.get("fertilizer"),
                    reason=fert_phrase(rec.get("reason"), lang),
                )
            )
        return "\n".join(lines)

    if intent == "FERTILIZER_EXPLANATION":
        if unavailable:
            return unavailable
        fert_crop = number_crop or crop
        if not recs:
            return override_prefix + msg(
                lang, "FERT_EXPLAIN_NONE", prefix="", crop=crop_name(fert_crop, lang) if fert_crop else ""
            )
        lines = [override_prefix + msg(lang, "FERT_EXPLAIN_HEADER", prefix="")]
        for rec in recs:
            lines.append(
                msg(
                    lang,
                    "FERT_EXPLAIN_LINE",
                    label=rec.get("fertilizer"),
                    npk=rec.get("npk_ratio"),
                    reason=fert_phrase(rec.get("reason"), lang),
                )
            )
        return "\n".join(lines)

    # ---- Yield --------------------------------------------------------
    yield_info = report.get("yield_prediction") or {}

    if intent == "YIELD_PREDICTION":
        if unavailable:
            return unavailable
        predicted = yield_info.get("predicted_yield_kg_ha")
        yield_crop = number_crop or crop
        if not yield_crop:
            return msg(lang, "YIELD_NO_RUN")
        if predicted is None:
            return msg(lang, "YIELD_NONE", crop=crop_name(yield_crop, lang))
        return msg(
            lang,
            "YIELD_PREDICTION",
            prefix=override_prefix,
            crop=crop_name(yield_crop, lang),
            yield_kg=predicted,
        )

    if intent == "YIELD_EXPLANATION":
        interp_key = _yield_interp_key(yield_info.get("predicted_yield_kg_ha"))
        if not interp_key:
            return yield_info.get("interpretation")
        return YIELD_EMOJI.get(interp_key, "") + msg(lang, interp_key)

    if intent == "YIELD_FACTORS":
        return msg(lang, "YIELD_FACTORS")

    if intent == "YIELD_STATUS_EXPLANATION":
        return msg(lang, "YIELD_STATUS_EXPLANATION")

    # No template for this intent (includes OUT_OF_SCOPE / UNKNOWN).
    return None
