"""Crop-aware chatbot routing: never quote Jowar yield as Groundnut."""

from chatbot.crop_query import analysis_for_crop, mentioned_crop
from chatbot.intent_responder import generate_response
from chatbot.router import answer_question


JOWAR_REPORT = {
    "chosen_crop": "Jowar",
    "top_5_crops": [{"crop": "Jowar", "probability": 0.55}],
    "soil_input": {
        "Nitrogen": 58,
        "Phosphorus": 43,
        "Potassium": 37,
        "pH": 6.4,
        "Temperature": 26.5,
        "Rainfall": 820,
    },
    "soil_adjustment": {},
    "fertilizer": {},
    "yield_prediction": {
        "predicted_yield_kg_ha": 2704.1,
        "interpretation": "Moderate",
    },
}


def test_mentioned_crop_english_and_indic():
    assert mentioned_crop("what would be expected yield for groundnut") == "Groundnut"
    assert mentioned_crop("expected yield for peanut") == "Groundnut"
    assert mentioned_crop("मूंगफली की उपज कितनी होगी") == "Groundnut"
    assert mentioned_crop("शेंगदाणा उत्पादन किती") == "Groundnut"
    assert mentioned_crop("what is my predicted yield") is None
    assert mentioned_crop("groundnut vs jowar yield") is None


def test_yield_question_does_not_return_jowar_when_asked_groundnut():
    answer, source = answer_question(
        "what would be expected yield for groundnut",
        JOWAR_REPORT,
        history=[],
        api_key="",
        lang="en",
    )
    assert "Jowar" not in answer
    assert "2,704.1" not in answer
    assert source == "intent"
    assert "Groundnut" in answer
    # Recomputed from the yield model — a real kg/ha figure.
    assert "kg/ha" in answer


def test_yield_for_this_run_still_uses_saved_number():
    answer, source = answer_question(
        "what is my predicted yield",
        JOWAR_REPORT,
        history=[],
        api_key="",
        lang="en",
    )
    assert source == "intent"
    assert "Jowar" in answer
    assert "2,704.1" in answer


def test_bind_keeps_crop_recommendation_as_this_run():
    bound = analysis_for_crop(JOWAR_REPORT, "Groundnut")
    rec = generate_response("CROP_RECOMMENDATION", bound, lang="en")
    assert "Jowar" in rec
    assert bound["chosen_crop"] == "Jowar"
    assert bound.get("query_crop") == "Groundnut"
