"""Run the ML pipeline and (optionally) persist the run to the user's history."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.schemas import PredictionOut, PredictionRequest
from backend.services import history_service, prediction_service

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/crops", response_model=list[str])
def crops() -> list[str]:
    return prediction_service.supported_crops()


@router.post("/predict", response_model=PredictionOut)
def predict(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionOut:
    if payload.crop and payload.crop not in prediction_service.supported_crops():
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported crop. Choose one of {prediction_service.supported_crops()}",
        )

    if payload.grown_crop and payload.grown_crop not in prediction_service.supported_crops():
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported grown crop. Choose one of {prediction_service.supported_crops()}",
        )

    soil = payload.model_dump(include=set(prediction_service.FIELD_TO_PIPELINE_KEY))
    try:
        result = prediction_service.run_analysis(soil, payload.crop)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=f"Model not available: {error}")

    if not payload.save:
        return PredictionOut(id=None, created_at=None, **result)

    entry = history_service.save_prediction(
        db, user, result, label=payload.label, notes=payload.notes, grown_crop=payload.grown_crop
    )
    return PredictionOut(**history_service.entry_to_dict(entry))
