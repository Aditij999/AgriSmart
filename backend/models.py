"""SQLAlchemy models: users and their prediction history."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Prediction(Base):
    """One full pipeline run (soil input + all four module outputs)."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    nitrogen: Mapped[float] = mapped_column(Float)
    phosphorus: Mapped[float] = mapped_column(Float)
    potassium: Mapped[float] = mapped_column(Float)
    ph: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    rainfall: Mapped[float] = mapped_column(Float)

    chosen_crop: Mapped[str] = mapped_column(String(64))
    recommended_crop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The crop the farmer finally planted/grew (as opposed to chosen_crop, the one
    # the analysis was run for). Crop-rotation alerts are based on this.
    grown_crop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_crop_probability: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    predicted_yield_kg_ha: Mapped[float | None] = mapped_column(Float, nullable=True)

    top_crops: Mapped[list] = mapped_column(JSON, default=list)
    soil_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    fertilizer: Mapped[dict] = mapped_column(JSON, default=dict)
    yield_prediction: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="predictions")
