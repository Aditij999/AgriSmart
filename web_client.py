"""
Thin HTTP client for the AgriSmart FastAPI backend (backend/main.py), used by
the Streamlit website (app.py) so it can share the same accounts, saved
history, and compare feature as the Flutter mobile app instead of being a
disconnected, session-only demo.

Mirrors mobile/lib/api_client.dart's shape (same endpoints, same auth
header) on purpose — the two clients should behave identically.

Base URL defaults to the local dev server and can be overridden with the
API_BASE_URL environment variable, e.g.:
    API_BASE_URL=http://192.168.1.10:8000 streamlit run app.py
"""

from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
_TIMEOUT = 20  # seconds; predict can be slower, see ApiClient.predict()


class ApiError(Exception):
    """Raised for any non-2xx response or unreachable-server condition."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _headers(token: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(method: str, path: str, token: str | None = None, timeout: int = _TIMEOUT, **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        response = requests.request(method, url, headers=_headers(token), timeout=timeout, **kwargs)
    except requests.RequestException:
        raise ApiError(f"Cannot reach the server at {BASE_URL}. Is the backend running?")

    body = None
    if response.content:
        try:
            body = response.json()
        except ValueError:
            body = None

    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else None
        raise ApiError(detail or f"Request failed ({response.status_code})", status_code=response.status_code)
    return body


def is_backend_online() -> bool:
    try:
        _request("GET", "/health", timeout=3)
        return True
    except ApiError:
        return False


# ── Auth ─────────────────────────────────────────────────────────────
def register(username: str, password: str, email: str | None = None, full_name: str | None = None) -> dict:
    payload = {"username": username, "password": password}
    if email:
        payload["email"] = email
    if full_name:
        payload["full_name"] = full_name
    return _request("POST", "/api/auth/register", json=payload)


def login(username: str, password: str) -> dict:
    return _request("POST", "/api/auth/login", json={"username": username, "password": password})


def me(token: str) -> dict:
    return _request("GET", "/api/auth/me", token=token)


# ── Predictions ──────────────────────────────────────────────────────
def supported_crops(token: str | None = None) -> list[str]:
    return _request("GET", "/api/crops", token=token)


def predict(
    token: str,
    *,
    nitrogen: float,
    phosphorus: float,
    potassium: float,
    ph: float,
    temperature: float,
    rainfall: float,
    crop: str | None = None,
    label: str | None = None,
    notes: str | None = None,
    grown_crop: str | None = None,
    save: bool = True,
) -> dict:
    payload = {
        "nitrogen": nitrogen,
        "phosphorus": phosphorus,
        "potassium": potassium,
        "ph": ph,
        "temperature": temperature,
        "rainfall": rainfall,
        "crop": crop,
        "label": label,
        "notes": notes,
        "grown_crop": grown_crop,
        "save": save,
    }
    return _request("POST", "/api/predict", token=token, json=payload, timeout=60)


# ── History & compare ────────────────────────────────────────────────
def list_history(token: str, limit: int = 50, offset: int = 0, crop: str | None = None) -> dict:
    params = {"limit": limit, "offset": offset}
    if crop:
        params["crop"] = crop
    return _request("GET", "/api/history", token=token, params=params)


def get_history_entry(token: str, entry_id: int) -> dict:
    return _request("GET", f"/api/history/{entry_id}", token=token)


def update_history_entry(
    token: str, entry_id: int, label: str | None = None, notes: str | None = None,
    grown_crop: str | None = None,
) -> dict:
    payload = {}
    if grown_crop is not None:
        payload["grown_crop"] = grown_crop
    if label is not None:
        payload["label"] = label
    if notes is not None:
        payload["notes"] = notes
    return _request("PATCH", f"/api/history/{entry_id}", token=token, json=payload)


def delete_history_entry(token: str, entry_id: int) -> dict:
    return _request("DELETE", f"/api/history/{entry_id}", token=token)


def compare(token: str, ids: list[int]) -> dict:
    return _request("GET", "/api/history/compare", token=token, params=[("ids", i) for i in ids])


# ── Chat (kept for parity; app.py currently answers chat in-process via
# chatbot/router.py, which works with or without the backend running) ──
def chat(token: str | None, message: str, history: list, prediction_id: int | None = None, lang: str = "auto") -> dict:
    payload = {"message": message, "history": history, "lang": lang}
    if prediction_id is not None:
        payload["prediction_id"] = prediction_id
    return _request("POST", "/api/chat", token=token, json=payload, timeout=60)
