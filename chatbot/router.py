"""
Hybrid chat router for Smart Agri.

Tries the fast, free, offline TF-IDF intent classifier first (chatbot/
classifier.py + chatbot/intent_responder.py). Only when that isn't
confident about what's being asked does it fall back to the Gemini API
(chatbot/gemini_chat.py) for a free-form answer. Both paths are restricted
to crop recommendation, soil, fertilizer, and yield topics.
"""

from chatbot.classifier import train_classifier, predict_intent_with_confidence
from chatbot.crop_query import analysis_for_crop, mentioned_crop
from chatbot.intent_responder import generate_response as intent_response, NO_TEMPLATE_INTENTS
from chatbot.gemini_chat import ask_gemini
from chatbot.i18n import msg
from chatbot.language import resolve_language

# Shown when the offline intent classifier confidently detects an
# off-topic message. Kept per-language so the refusal itself is
# multilingual too, not just the on-topic answers.
_OFF_TOPIC_REFUSAL_BY_LANG = {
    "en": (
        "I'm built specifically for AgriSmart DSS. I can answer questions about "
        "your crop recommendation, soil analysis, fertilizer plan, and yield "
        "prediction — try asking about one of those."
    ),
    "hi": (
        "मैं विशेष रूप से AgriSmart DSS के लिए बना हूँ। मैं आपकी फसल सिफारिश, मिट्टी "
        "विश्लेषण, खाद योजना और उपज अनुमान से जुड़े प्रश्नों के उत्तर दे सकता हूँ — इनमें से "
        "किसी एक के बारे में पूछें।"
    ),
    "mr": (
        "मी विशेषतः AgriSmart DSS साठी बनवलेला आहे. मी तुमची पीक शिफारस, माती विश्लेषण, "
        "खत योजना आणि उत्पादन अंदाज याबद्दलच्या प्रश्नांची उत्तरे देऊ शकतो — यापैकी एखाद्या "
        "बद्दल विचारा."
    ),
}

# Below this confidence, the intent classifier's guess is treated as too
# unreliable to answer from a template — the message goes to Gemini instead.
# (Tuned against chatbot/intents.json: confident, close paraphrases of the
# training examples score ~0.18-0.25; vague or off-topic messages score
# lower and are better handled by Gemini's actual language understanding.)
CONFIDENCE_THRESHOLD = 0.16

# If the user clearly asked about yield, answer from this run's numbers
# instead of waiting on Gemini (which can 503 under high demand).
_YIELD_HINTS = ("yield", "harvest", "उपज", "उत्पादन", "उत्पन्न")
_YIELD_NOT_PREDICTION = (
    "mean", "explain", "factor", "model", "algorithm", "feature",
    "low yield", "high yield", "moderate yield", "good yield",
    "status", "categor", "व्याख्या", "कारण",
)

# Kept for backward compatibility with any existing English-only callers.
OFF_TOPIC_REFUSAL = _OFF_TOPIC_REFUSAL_BY_LANG["en"]


def _keyword_intent(user_message: str):
    text = (user_message or "").lower()
    if any(hint in text for hint in _YIELD_HINTS):
        if any(skip in text for skip in _YIELD_NOT_PREDICTION):
            return None
        return "YIELD_PREDICTION"
    return None


_classifier = None  # lazily trained once per process, reused after that


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = train_classifier()
    return _classifier


def answer_question(
    user_message: str,
    report: dict,
    history: list,
    api_key: str,
    lang: str | None = None,
):
    """
    Route a single chat message to the best available answer source.

    `lang` is the client's language preference: "en" / "hi" / "mr" to force
    a reply language, or "auto" / None (the default) to detect it from
    `user_message` (Devanagari script + Hindi/Marathi marker words). The
    same resolved language is used for both the offline template engine
    and the Gemini fallback, so the reply language is consistent no matter
    which path answers the question.

    Returns (answer_text, source), where source is one of:
      "intent"   — answered instantly from the offline template engine
      "gemini"   — answered by the Gemini API
      "fallback" — Gemini unavailable/failed; a static on-topic nudge
    """
    resolved_lang = resolve_language(user_message, preferred=lang)

    # Bind soil/fertilizer/yield numbers to the crop named in the question
    # (e.g. Groundnut) so we never quote this run's Jowar yield as Groundnut.
    asked_crop = mentioned_crop(user_message)
    report = analysis_for_crop(report, asked_crop)

    keyword_intent = _keyword_intent(user_message)
    if keyword_intent:
        templated = intent_response(
            keyword_intent, report, user_message, lang=resolved_lang
        )
        if templated:
            return templated, "intent"

    classifier = _get_classifier()
    intent, confidence = predict_intent_with_confidence(classifier, user_message)

    if confidence >= CONFIDENCE_THRESHOLD:
        if intent == "OUT_OF_SCOPE":
            # Confident, unambiguous off-topic match — refuse without
            # spending an API call.
            return _OFF_TOPIC_REFUSAL_BY_LANG.get(
                resolved_lang, _OFF_TOPIC_REFUSAL_BY_LANG["en"]
            ), "intent"
        if intent != "UNKNOWN":
            templated = intent_response(intent, report, user_message, lang=resolved_lang)
            if templated:
                return templated, "intent"

    # Less-common questions go to Gemini, with the crop-bound analysis so it
    # cannot invent a different crop's numbers. Templates remain the fallback.
    try:
        answer = ask_gemini(
            user_message=user_message,
            report=report,
            history=history,
            api_key=api_key,
            lang=resolved_lang,
        )
        return answer, "gemini"
    except RuntimeError as error:
        if intent not in NO_TEMPLATE_INTENTS:
            templated = intent_response(intent, report, user_message, lang=resolved_lang)
            if templated:
                return templated, "intent"
        if str(error) == "GEMINI_BUSY":
            return f"⚠️ {msg(resolved_lang, 'GEMINI_BUSY')}", "fallback"
        return f"⚠️ {error}", "fallback"
