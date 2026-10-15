"""Persistence and comparison helpers for prediction history."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Prediction, User
# prediction_service puts the project root on sys.path, which is what makes the
# website's existing rotation logic importable here.
from backend.services.prediction_service import UNITS

import history_store  # noqa: E402  (project root — the website's crop-rotation rules)


def save_prediction(
    db: Session,
    user: User,
    result: dict[str, Any],
    label: str | None = None,
    notes: str | None = None,
    grown_crop: str | None = None,
) -> Prediction:
    soil = result["soil_input"]
    entry = Prediction(
        user_id=user.id,
        label=label,
        notes=notes,
        grown_crop=grown_crop,
        nitrogen=soil["nitrogen"],
        phosphorus=soil["phosphorus"],
        potassium=soil["potassium"],
        ph=soil["ph"],
        temperature=soil["temperature"],
        rainfall=soil["rainfall"],
        chosen_crop=result["chosen_crop"],
        recommended_crop=result["recommended_crop"],
        recommended_crop_probability=result["recommended_crop_probability"],
        predicted_yield_kg_ha=result["predicted_yield_kg_ha"],
        top_crops=result["top_crops"],
        soil_analysis=result["soil_analysis"],
        fertilizer=result["fertilizer"],
        yield_prediction=result["yield_prediction"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def entry_to_dict(entry: Prediction) -> dict[str, Any]:
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "label": entry.label,
        "notes": entry.notes,
        "grown_crop": entry.grown_crop,
        "soil_input": {
            "nitrogen": entry.nitrogen,
            "phosphorus": entry.phosphorus,
            "potassium": entry.potassium,
            "ph": entry.ph,
            "temperature": entry.temperature,
            "rainfall": entry.rainfall,
        },
        "chosen_crop": entry.chosen_crop,
        "recommended_crop": entry.recommended_crop,
        "recommended_crop_probability": entry.recommended_crop_probability,
        "predicted_yield_kg_ha": entry.predicted_yield_kg_ha,
        "top_crops": entry.top_crops or [],
        "soil_analysis": entry.soil_analysis or {},
        "fertilizer": entry.fertilizer or {},
        "yield_prediction": entry.yield_prediction or {},
    }


def get_entry(db: Session, user: User, entry_id: int) -> Prediction | None:
    return db.scalar(
        select(Prediction).where(Prediction.id == entry_id, Prediction.user_id == user.id)
    )


def list_entries(
    db: Session, user: User, limit: int, offset: int, crop: str | None = None
) -> tuple[int, list[Prediction]]:
    filters = [Prediction.user_id == user.id]
    if crop:
        filters.append(Prediction.chosen_crop == crop)

    total = db.scalar(select(func.count()).select_from(Prediction).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Prediction)
            .where(*filters)
            .order_by(Prediction.created_at.desc(), Prediction.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return total, items


def latest_entry(db: Session, user: User) -> Prediction | None:
    return db.scalar(
        select(Prediction)
        .where(Prediction.user_id == user.id)
        .order_by(Prediction.created_at.desc(), Prediction.id.desc())
        .limit(1)
    )


COMPARE_FIELDS: list[tuple[str, str, str]] = [
    ("nitrogen", "Nitrogen", UNITS["nitrogen"]),
    ("phosphorus", "Phosphorus", UNITS["phosphorus"]),
    ("potassium", "Potassium", UNITS["potassium"]),
    ("ph", "pH", UNITS["ph"]),
    ("temperature", "Temperature", UNITS["temperature"]),
    ("rainfall", "Rainfall", UNITS["rainfall"]),
]


def build_comparison(entries: list[Prediction]) -> list[dict[str, Any]]:
    """Row-per-field comparison table across the selected history entries."""
    rows: list[dict[str, Any]] = []

    for attr, label, unit in COMPARE_FIELDS:
        values = [getattr(entry, attr) for entry in entries]
        rows.append(
            {
                "field": label,
                "unit": unit,
                "values": values,
                "changed": len(set(values)) > 1,
            }
        )

    for attr, label, unit in [
        ("chosen_crop", "Target crop", ""),
        ("recommended_crop", "Recommended crop", ""),
        ("predicted_yield_kg_ha", "Predicted yield", "kg/ha"),
    ]:
        values = [getattr(entry, attr) for entry in entries]
        rows.append(
            {
                "field": label,
                "unit": unit,
                "values": values,
                "changed": len(set(values)) > 1,
            }
        )

    fertilizer_values = [
        ", ".join(
            rec.get("fertilizer", "")
            for rec in (entry.fertilizer or {}).get("generic_recs", [])
        )
        or "No correction needed"
        for entry in entries
    ]
    rows.append(
        {
            "field": "Fertilizers",
            "unit": "",
            "values": fertilizer_values,
            "changed": len(set(fertilizer_values)) > 1,
        }
    )

    imbalance_values = [
        str(
            sum(
                1
                for info in (entry.soil_analysis or {}).values()
                if info.get("status") != "Optimal"
            )
        )
        for entry in entries
    ]
    rows.append(
        {
            "field": "Nutrient imbalances",
            "unit": "",
            "values": imbalance_values,
            "changed": len(set(imbalance_values)) > 1,
        }
    )

    return rows


def rotation_alerts(db: Session, user: User) -> list[dict[str, Any]]:
    """Crop-rotation warnings for one user, one per field that needs attention.

    Reuses `history_store.rotation_advice` — the exact logic the website runs — so
    both clients always give the same advice. Only `user`'s own runs are read.
    """
    _, entries = list_entries(db, user, limit=200, offset=0)
    runs = [
        {
            "id": entry.id,
            "created_at": entry.created_at.isoformat() if entry.created_at else "",
            "label": entry.label,
            "grown_crop": entry.grown_crop,
        }
        for entry in entries
    ]
    runs = history_store.from_backend_items(runs)
    fields = sorted({(run.get("field") or "").strip() for run in runs})
    alerts = []
    for field in fields:
        advice = history_store.rotation_advice(runs, field)
        if advice:
            alerts.append(advice)
    return alerts
