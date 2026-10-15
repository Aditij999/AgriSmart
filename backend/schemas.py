"""Pydantic request/response models for the AgriSmart API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = None
    full_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SoilInput(BaseModel):
    nitrogen: float = Field(ge=0, le=300)
    phosphorus: float = Field(ge=0, le=300)
    potassium: float = Field(ge=0, le=300)
    ph: float = Field(ge=0, le=14)
    temperature: float = Field(ge=-10, le=60)
    rainfall: float = Field(ge=0, le=5000)


class PredictionRequest(SoilInput):
    crop: str | None = Field(
        default=None,
        description="Target crop. When omitted the top recommended crop is used.",
    )
    label: str | None = Field(default=None, max_length=128)
    notes: str | None = None
    grown_crop: str | None = Field(
        default=None,
        description="The crop the farmer finally grew (drives crop-rotation alerts).",
    )
    save: bool = True


class CropScore(BaseModel):
    crop: str
    probability: float


class PredictionOut(BaseModel):
    id: int | None
    created_at: datetime | None
    label: str | None = None
    notes: str | None = None
    grown_crop: str | None = None
    soil_input: dict[str, float]
    chosen_crop: str
    recommended_crop: str | None
    recommended_crop_probability: float | None
    predicted_yield_kg_ha: float | None
    top_crops: list[CropScore]
    soil_analysis: dict[str, Any]
    fertilizer: dict[str, Any]
    yield_prediction: dict[str, Any]


class HistoryItem(BaseModel):
    id: int
    created_at: datetime
    label: str | None
    chosen_crop: str
    recommended_crop: str | None
    grown_crop: str | None = None
    predicted_yield_kg_ha: float | None
    nitrogen: float
    phosphorus: float
    potassium: float
    ph: float
    temperature: float
    rainfall: float

    model_config = ConfigDict(from_attributes=True)


class HistoryPage(BaseModel):
    total: int
    items: list[HistoryItem]


class HistoryUpdate(BaseModel):
    label: str | None = None
    notes: str | None = None
    grown_crop: str | None = None


class RotationAdvice(BaseModel):
    """One crop-rotation warning for one field (same shape history_store.rotation_advice returns)."""

    # "watch" = repeated crop/family; "alert" = same crop grown 3+ times in a row.
    level: Literal["watch", "alert"]
    crop: str
    streak: int
    headline: str
    reason: str
    suggest: list[str]
    field: str = ""


class RotationResponse(BaseModel):
    alerts: list[RotationAdvice]


class ComparisonField(BaseModel):
    field: str
    unit: str
    values: list[float | str | None]
    changed: bool


class ChangeItem(BaseModel):
    text: str
    # up | down | changed | same
    direction: str = "changed"
    # positive | negative | neutral — only "positive"/"negative" where the
    # analysis itself defines better/worse (yield, status moving to/from Optimal).
    tone: str = "neutral"


class KeyChange(ChangeItem):
    # soil | crop | yield | fertilizer | adjustment
    kind: str


class ChangeSection(BaseModel):
    id: str
    title: str
    items: list[ChangeItem]


class EntryRef(BaseModel):
    id: int | None
    name: str
    created_at: datetime | None = None


class YieldChange(BaseModel):
    before: float
    after: float
    delta: float
    percent: float | None = None
    tone: str = "neutral"


class CropChange(BaseModel):
    before: str
    after: str
    changed: bool


class ChangeStep(BaseModel):
    from_entry: EntryRef
    to_entry: EntryRef
    has_changes: bool
    key_changes: list[KeyChange]
    interpretation: list[str]
    crop_change: CropChange | None = None
    yield_change: YieldChange | None = None
    sections: list[ChangeSection]
    notes: list[str]


class ChangeSummary(BaseModel):
    # One step per consecutive pair (oldest -> newest).
    steps: list[ChangeStep]
    # First -> last, only when 3+ analyses are compared.
    overall: ChangeStep | None = None


class CompareResponse(BaseModel):
    # Entries are ordered oldest -> newest.
    entries: list[PredictionOut]
    summary: ChangeSummary
    rows: list[ComparisonField]


class ChatTurn(BaseModel):
    role: Literal["user", "model"]
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = Field(default_factory=list)
    prediction_id: int | None = Field(
        default=None,
        description="History entry to answer about. Defaults to the latest one.",
    )
    # Clients may say how the message was captured. Voice input is handled
    # entirely client-side by transcribing to text before calling this endpoint.
    input_mode: Literal["text", "voice"] = "text"
    # Reply language: "auto" (default) detects Hindi/Marathi/English from
    # the message itself; "en"/"hi"/"mr" forces a language regardless of
    # what script the user typed in.
    lang: Literal["auto", "en", "hi", "mr"] = "auto"


class ChatResponse(BaseModel):
    answer: str
    # Same answer with bullet/emoji decoration removed, for text-to-speech clients.
    answer_plain: str
    source: Literal["intent", "gemini", "fallback"]
    prediction_id: int | None
    # The language the reply was actually written in ("en"/"hi"/"mr"), so
    # clients can label the message or pick a matching TTS voice.
    lang: Literal["en", "hi", "mr"]


class DeleteResponse(BaseModel):
    deleted: int
