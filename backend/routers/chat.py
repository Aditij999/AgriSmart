"""Chatbot endpoint — reuses the existing hybrid intent/Gemini router.

The Gemini key stays on the server: clients never send or receive it.
Voice clients transcribe speech to text before calling this endpoint and may
speak `answer_plain` back, so no change is needed here to add voice/TTS.
"""

import re
import sys

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import GEMINI_API_KEY
from backend.database import get_db
from backend.models import User
from backend.schemas import ChatRequest, ChatResponse
from backend.services import history_service
from backend.services.prediction_service import PROJECT_ROOT, to_chatbot_report

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from chatbot.router import answer_question  # noqa: E402
from chatbot.language import detect_language, resolve_language  # noqa: E402

router = APIRouter(prefix="/api/chat", tags=["chat"])

_DECORATION = re.compile(r"[•\-\*]{1,2}\s|[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def _plain_text(answer: str) -> str:
    stripped = _DECORATION.sub("", answer)
    return re.sub(r"\s+", " ", stripped).strip()


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    if payload.prediction_id is not None:
        entry = history_service.get_entry(db, user, payload.prediction_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="History entry not found")
    else:
        entry = history_service.latest_entry(db, user)

    report = to_chatbot_report(history_service.entry_to_dict(entry)) if entry else {}

    answer, source = answer_question(
        user_message=payload.message,
        report=report,
        history=[turn.model_dump() for turn in payload.history],
        api_key=GEMINI_API_KEY,
        lang=payload.lang,
    )
    resolved_lang = resolve_language(payload.message, preferred=payload.lang)
    # The model sometimes answers in Marathi/Hindi to a message typed in Latin
    # letters (so the message itself resolves to "en"). `lang` is documented as the
    # language the reply was written in — clients use it to pick a TTS voice — so
    # trust the reply's script in that one case.
    if resolved_lang == "en" and any("\u0900" <= ch <= "\u097f" for ch in answer):
        resolved_lang = detect_language(answer, fallback="hi")
    return ChatResponse(
        answer=answer,
        answer_plain=_plain_text(answer),
        source=source,
        prediction_id=entry.id if entry else None,
        lang=resolved_lang,
    )
