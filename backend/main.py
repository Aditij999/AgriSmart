"""AgriSmart DSS API — FastAPI layer between the Flutter app and the existing
Python/ML pipeline. Run with:  uvicorn backend.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS, GEMINI_API_KEY
from backend.database import init_db
from backend.routers import auth, chat, history, predictions

import sys
import sklearn


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AgriSmart DSS API",
    version="1.0.0",
    description="Crop recommendation, soil analysis, fertilizer advice, yield "
    "prediction, chatbot and per-user history for the AgriSmart mobile app.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(history.router)
app.include_router(chat.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, object]:
    return {"status": "ok", "gemini_configured": bool(GEMINI_API_KEY)}



@app.get("/debug/version")
def debug_version():
    return {
        "python_version": sys.version,
        "scikit_learn_version": sklearn.__version__
    }

