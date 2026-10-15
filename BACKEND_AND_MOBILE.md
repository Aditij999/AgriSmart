# AgriSmart DSS — FastAPI backend + Flutter Android app

Adds history monitoring and a mobile client on top of the existing project.
The Streamlit app, the ML models, the prediction pipeline and the chatbot are
unchanged — the backend calls them.

```
Flutter (mobile/)  →  FastAPI (backend/)  →  pipeline.run_pipeline
                            │                 chatbot.router.answer_question
                            └── SQLite (agrismart.db): users + prediction history
```

## 1. Run the backend

```bash
cd <project root>
pip install -r backend/requirements.txt          # plus the existing ML deps
export GEMINI_API_KEY=<your key>                 # or put it in .env
export AGRISMART_JWT_SECRET=<random string>      # default is a dev placeholder
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

* Interactive docs: http://localhost:8000/docs
* Health: `GET /health`
* SQLite file `agrismart.db` is created automatically in the project root
  (override with `AGRISMART_DATABASE_URL`).
* Bind to `0.0.0.0` so an emulator or phone on the same Wi-Fi can reach it.

End-to-end API check (backend must be running):

```bash
python backend/smoke_test.py http://127.0.0.1:8000
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | returns a JWT |
| GET | `/api/auth/me` | current user |
| GET | `/api/crops` | supported crops |
| POST | `/api/predict` | runs the existing pipeline, saves to history |
| GET | `/api/history` | list own history |
| GET | `/api/history/{id}` | open one entry |
| GET | `/api/history/rotation` | crop-rotation warnings for the signed-in user (same rules as the website — `history_store.rotation_advice`) |
| GET | `/api/history/compare?ids=1&ids=2` | compare 2–4 entries: plain-language change `summary` + raw field `rows` (see below) |
| PATCH | `/api/history/{id}` | rename / add notes |
| DELETE | `/api/history/{id}`, `/api/history` | delete one / clear all |
| POST | `/api/chat` | existing intent + Gemini chatbot |

**Compare response.** `entries` are returned oldest → newest regardless of the
order of `ids`. `summary` is the primary payload: one `step` per consecutive
pair (plus an `overall` first → last step when 3+ runs are compared), each with
`key_changes` (e.g. "Nitrogen increased by 5 kg/ha."), a short `interpretation`,
structured `crop_change` / `yield_change`, per-topic `sections` (soil & weather,
crop, yield, fertilizer, soil-adjustment status) and `notes`. `rows` is the
original field-by-field table, kept as supporting detail. The wording is built
only from values stored in the runs (`backend/services/compare_summary.py`;
tests: `python -m backend.test_compare_summary`). Compare is separate from crop
rotation: `recommended_crop` is only ever compared between runs, never treated
as a crop the farmer grew.

**Crop rotation.** Alerts are based on the crop the farmer actually grew
(`grown_crop`, set with `PATCH /api/history/{id}` or at predict time), per field
label, exactly like the website. `GET /api/history/rotation` runs the website's
own `history_store.rotation_advice`, so there is one set of rules; the mobile
Dashboard, History and Result screens render its output as in-app alert cards
and reload when the user's history changes.

Every history query is filtered by the JWT's user id, so history is private.
The Gemini key is read from the server environment and is never sent to the app.

## 2. Run the Flutter app

```bash
cd mobile
flutter pub get
flutter run                                   # Android emulator → http://10.0.2.2:8000
flutter run --dart-define=API_BASE_URL=http://<your-LAN-IP>:8000   # physical phone
flutter build apk --debug                     # build/app/outputs/flutter-apk/app-debug.apk
flutter analyze && flutter test
```

Screens: login/register → dashboard → soil input & predict → result (crop
recommendation, soil analysis, fertilizer plan, yield) → history (open, compare
2–4 with a "what changed" summary, delete, clear) → chat.

## 3. Streamlit (unchanged)

```bash
streamlit run app.py
```

## Voice / TTS

Speech-to-text (`speech_to_text`) and text-to-speech (`flutter_tts`) run in the
Flutter layer only (`mobile/lib/voice/`); the website uses the browser's Web
Speech API instead (`web_voice.py`) — in both cases no audio ever leaves the
device. `POST /api/chat` returns both `answer` (markdown) and `answer_plain`
(speech-friendly), and the app sends transcribed text to the existing
endpoint (tagging `input_mode: "voice"`) and speaks `answer_plain` back, so
the backend itself is unchanged. Voice input is dictation only — recognized
text lands in the input field and the user still sends it — and `lang`
(reply language) works the same way whether the question was typed or
spoken.

## Remaining TODOs

* Put a real `GEMINI_API_KEY` in `.env` — the checked-in value is a placeholder,
  so the chatbot currently falls back to the offline intent responses.
  `/health`'s `gemini_configured` only reports that a key is set, not valid.
* Set `AGRISMART_JWT_SECRET` before any non-local deployment; don't commit `.env`.
* No password reset / token refresh; tokens expire after the configured window.
* Serve the API over HTTPS for release builds — the Android manifest currently
  allows cleartext traffic so local HTTP development works.
