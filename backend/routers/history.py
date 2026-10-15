"""Per-user prediction history: list, open, compare, annotate and delete."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Prediction, User
from backend.schemas import (
    ChangeSummary,
    CompareResponse,
    DeleteResponse,
    HistoryItem,
    HistoryPage,
    HistoryUpdate,
    PredictionOut,
    RotationResponse,
)
from backend.services import history_service, prediction_service
from backend.services.compare_summary import build_change_summary

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryPage)
def list_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    crop: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HistoryPage:
    total, entries = history_service.list_entries(db, user, limit, offset, crop)
    return HistoryPage(total=total, items=[HistoryItem.model_validate(e) for e in entries])


# Declared before "/{entry_id}" so "rotation" is never parsed as an entry id.
@router.get("/rotation", response_model=RotationResponse)
def rotation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RotationResponse:
    """Crop-rotation warnings for the signed-in user's own history only."""
    return RotationResponse(alerts=history_service.rotation_alerts(db, user))


@router.get("/compare", response_model=CompareResponse)
def compare(
    ids: list[int] = Query(min_length=2, max_length=4),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompareResponse:
    entries = []
    for entry_id in ids:
        entry = history_service.get_entry(db, user, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"History entry {entry_id} not found")
        entries.append(entry)

    # "Previous -> current" only makes sense in time order, whatever order the
    # client listed the ids in.
    entries.sort(key=lambda e: (e.created_at, e.id))
    entry_dicts = [history_service.entry_to_dict(e) for e in entries]

    return CompareResponse(
        entries=[PredictionOut(**d) for d in entry_dicts],
        summary=ChangeSummary(**build_change_summary(entry_dicts)),
        rows=history_service.build_comparison(entries),
    )


@router.get("/{entry_id}", response_model=PredictionOut)
def get_history_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionOut:
    entry = history_service.get_entry(db, user, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return PredictionOut(**history_service.entry_to_dict(entry))


@router.patch("/{entry_id}", response_model=PredictionOut)
def update_history_entry(
    entry_id: int,
    payload: HistoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionOut:
    entry = history_service.get_entry(db, user, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    if payload.label is not None:
        entry.label = payload.label
    if payload.notes is not None:
        entry.notes = payload.notes
    if payload.grown_crop is not None:
        if payload.grown_crop not in prediction_service.supported_crops():
            raise HTTPException(status_code=400, detail=f"Unsupported grown crop. Choose one of {prediction_service.supported_crops()}")
        entry.grown_crop = payload.grown_crop
    db.commit()
    db.refresh(entry)
    return PredictionOut(**history_service.entry_to_dict(entry))


@router.delete("/{entry_id}", response_model=DeleteResponse)
def delete_history_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteResponse:
    entry = history_service.get_entry(db, user, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    db.delete(entry)
    db.commit()
    return DeleteResponse(deleted=1)


@router.delete("", response_model=DeleteResponse)
def clear_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteResponse:
    result = db.execute(delete(Prediction).where(Prediction.user_id == user.id))
    db.commit()
    return DeleteResponse(deleted=result.rowcount or 0)
