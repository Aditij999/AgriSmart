"""Run history + crop-rotation advice for the website.

When a farmer saves a run they say which crop they finally grew (required) and,
optionally, a label for the field. When the backend
is online and the visitor is logged in, `app.py` stores it in their account
(same history the mobile app shows). Otherwise it is stored here, in a small
JSON file next to the project, so history is never silently lost.

On top of whichever history is in use, `rotation_advice()` looks for the same
crop (or the same crop family) being planned again and again on a field, so the
farmer can be told to rotate.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime

_PATH = os.path.join(os.path.dirname(__file__), "data", "field_history.json")
_LOCK = threading.Lock()

# Crop family — continuous cropping of one family is what drains the same
# nutrients and builds up the same pests/diseases.
FAMILY = {
    "Jowar": "cereal",
    "Wheat": "cereal",
    "Groundnut": "legume",
    "Cotton": "fibre",
    "Sugarcane": "cane",
}

# General agronomy guidance for the five crops this app covers.
ROTATE_TO = {
    "Jowar": ["Groundnut", "Cotton"],
    "Wheat": ["Groundnut", "Cotton"],
    "Groundnut": ["Jowar", "Wheat"],
    "Cotton": ["Groundnut", "Jowar"],
    "Sugarcane": ["Groundnut", "Wheat"],
}

REASON = {
    "Jowar": "Cereals draw heavily on nitrogen — follow with a legume such as Groundnut to restore it.",
    "Wheat": "Cereals draw heavily on nitrogen — follow with a legume such as Groundnut to restore it.",
    "Groundnut": "Legumes fix nitrogen — a cereal next makes good use of it and breaks legume pest cycles.",
    "Cotton": "Cotton repeated on the same soil builds up bollworm and wilt pressure — break it with a legume or cereal.",
    "Sugarcane": "Long-duration cane depletes soil structure and nutrients — a legume ratoon gap helps recovery.",
}


def _load() -> list[dict]:
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def list_runs() -> list[dict]:
    """Newest first."""
    return sorted(_load(), key=lambda r: r.get("created_at", ""), reverse=True)


def add_run(run: dict) -> bool:
    """Store a run (explicitly saved by the farmer, with the crop they grew)."""
    with _LOCK:
        rows = _load()
        rec = dict(run)
        rec["id"] = max((r.get("id", 0) for r in rows), default=0) + 1
        rec["created_at"] = datetime.now().isoformat(timespec="seconds")
        rows.append(rec)
        _save(rows)
        return True


def set_grown_crop(run_id: int, grown_crop: str) -> None:
    with _LOCK:
        rows = _load()
        for r in rows:
            if r.get("id") == run_id:
                r["grown_crop"] = grown_crop
        _save(rows)


def delete_run(run_id: int) -> None:
    with _LOCK:
        _save([r for r in _load() if r.get("id") != run_id])


def from_backend_items(items: list[dict]) -> list[dict]:
    """Shape backend history rows like local ones so one rotation check serves both."""
    return [
        {
            "id": it.get("id"),
            "created_at": str(it.get("created_at", "")),
            "field": it.get("label") or "",
            "grown_crop": it.get("grown_crop"),
        }
        for it in items
    ]


def rotation_advice(runs: list[dict], field: str = "") -> dict | None:
    """Look at the crops actually *grown* (not just analysed) on `field`, newest
    first. Runs saved without a grown crop are ignored.

    - the same crop grown in 2+ consecutive saved runs  -> warn (3+ -> stronger)
    - the same crop *family* in 3+ consecutive saved runs -> warn
    Returns None when the history looks varied enough.
    """
    field = (field or "").strip()
    mine = [r for r in runs if (r.get("field") or "").strip() == field and r.get("grown_crop")]
    mine.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    if len(mine) < 2:
        return None

    latest = mine[0]["grown_crop"]
    crop_streak = 0
    for r in mine:
        if r["grown_crop"] == latest:
            crop_streak += 1
        else:
            break

    fam = FAMILY.get(latest)
    fam_streak = 0
    for r in mine:
        if FAMILY.get(r["grown_crop"]) == fam:
            fam_streak += 1
        else:
            break

    where = f"“{field}”" if field else "this field"
    if crop_streak >= 2:
        level = "alert" if crop_streak >= 3 else "watch"
        headline = f"{latest} has been grown {crop_streak} times in a row on {where}."
    elif fam and fam_streak >= 3:
        level = "watch"
        headline = f"{fam_streak} {fam} crops grown in a row on {where} (latest: {latest})."
    else:
        return None

    return {
        "level": level,
        "crop": latest,
        "streak": max(crop_streak, fam_streak),
        "headline": headline,
        "reason": REASON.get(latest, "Repeating the same crop depletes the same nutrients and builds up pests."),
        "suggest": ROTATE_TO.get(latest, []),
        "field": field,
    }
