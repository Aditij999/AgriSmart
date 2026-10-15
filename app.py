"""
Smart Agriculture Decision Support System
Single-page dashboard: input → results in one scroll.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import html, os, sys, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))
from chatbot.router import answer_question  # noqa: E402  (hybrid intent-classifier + Gemini API chatbot)
import history_store  # noqa: E402  (local run history + crop-rotation advice)
import web_client  # noqa: E402  (talks to backend/main.py — same accounts/history/compare the mobile app uses)
from web_voice import voice_input_component, speak_button, to_plain_text  # noqa: E402  (browser mic + read-aloud, matching the mobile app's voice features)

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads GEMINI_API_KEY from a local .env file, if present
except ImportError:
    pass  # python-dotenv not installed — GEMINI_API_KEY can still be set as a real env var

# ── Page config ─────────────────────────────
st.set_page_config(
    page_title="AgriSmart DSS",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Gemini API key ────────────────────────────
# Priority: .env / real environment variable > Streamlit secret > manual
# override typed into the chat dialog (session-only, never saved to disk).
def get_gemini_api_key():
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return st.session_state.get("gemini_api_key_override", "")


# ── Account / backend session state ───────────
# The website is a full peer of the mobile app: when the FastAPI backend
# (backend/main.py) is reachable, logging in here shares the exact same
# account, saved history, and compare feature as mobile/lib. When the
# backend isn't running, the dashboard below still works standalone (as a
# local, session-only calculator) — only History/Compare/account features
# are unavailable.
for _key, _default in {
    "auth_token": None,
    "auth_user": None,
    "history_selection": [],
}.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default


@st.cache_data(ttl=15, show_spinner=False)
def _backend_online() -> bool:
    return web_client.is_backend_online()


def _is_logged_in() -> bool:
    return bool(st.session_state.auth_token)


def render_login_page():
    """Full-page login/register gate — the website's equivalent of
    mobile/lib/screens/login_screen.dart. Shown before anything else when
    the backend is reachable and the visitor isn't signed in yet."""
    st.markdown("""
    <div style='padding:30px 32px; margin:40px auto 22px; max-width:520px; border-radius:20px;
                background:#1E3A2B; box-shadow:0 14px 40px rgba(33,51,41,0.18); text-align:center'>
        <p class="page-eyebrow" style='color:#E9B84B !important; opacity:1'>Field companion</p>
        <h1 style='margin:8px 0 0; font-size:2.4rem; color:#F2EFE6 !important'>
            AgriSmart <span style='color:#E9B84B !important'>DSS</span> 🌾
        </h1>
        <p style='color:#F2EFE6 !important; opacity:0.7; font-size:0.9rem; margin:12px 0 0; font-weight:500'>
            Log in to save runs and see the same History &amp; Compare as the mobile app.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        tab_login, tab_register = st.tabs(["Log in", "Create account"])

        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                lu = st.text_input("Username", key="login_username")
                lp = st.text_input("Password", type="password", key="login_password")
                if st.form_submit_button("Log in", use_container_width=True):
                    try:
                        result = web_client.login(lu.strip(), lp)
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.rerun()
                    except web_client.ApiError as error:
                        st.error(str(error))

        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                ru = st.text_input("Username", key="register_username")
                rp = st.text_input("Password (min 6 characters)", type="password", key="register_password")
                rn = st.text_input("Full name (optional)", key="register_full_name")
                re_ = st.text_input("Email (optional)", key="register_email")
                if st.form_submit_button("Create account", use_container_width=True):
                    try:
                        result = web_client.register(
                            ru.strip(),
                            rp,
                            email=re_.strip() or None,
                            full_name=rn.strip() or None,
                        )
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.rerun()
                    except web_client.ApiError as error:
                        st.error(str(error))

        st.markdown("<div style='text-align:center; margin-top:6px'>", unsafe_allow_html=True)
        if st.button("Continue without an account", use_container_width=True):
            st.session_state.guest_mode = True
            st.rerun()
        st.caption(
            "Guest mode still gives you the full crop/soil/fertilizer/yield "
            "dashboard and chat — you just won't be able to save runs to "
            "History or use Compare until you log in."
        )
        st.markdown("</div>", unsafe_allow_html=True)


def _display_name(raw) -> str:
    """Capitalise the first letter of each word ("dia" -> "Dia", "ravi kumar" -> "Ravi Kumar").

    Usernames are stored lower-case (the backend lower-cases them on sign-up), so
    anything shown to the person goes through here. Only the first letter of each
    word is changed, so names like "McDonald" are left alone. Mirrors
    `displayName()` in mobile/lib/widgets.dart.
    """
    return " ".join(w[:1].upper() + w[1:] for w in str(raw or "").split())


def render_page_topbar():
    """Slim header strip: tagline on the left, who's signed in on the right."""
    user = (st.session_state.get("auth_user") or {}) if _is_logged_in() else {}
    name = html.escape(_display_name(user.get("full_name") or user.get("username")) or "Guest")
    initials = (name[:2] or "G").upper()
    sub = "Synced with the mobile app" if user else "Local session"
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-l"><span class="topbar-dot"></span>Field intelligence, made practical</div>
        <div class="topbar-r">
            <span class="topbar-who"><b>{name}</b><small>{sub}</small></span>
            <span class="topbar-avatar">{initials}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_top_bar():
    """Compact status strip shown above the page nav once past the login
    gate (or immediately, when the backend is offline)."""
    online = _backend_online()
    left, right = st.columns([3, 1])
    with left:
        if not online:
            st.caption(
                f"⚪ Backend offline (`{web_client.BASE_URL}`) — running as a local calculator. "
                "History and Compare need `uvicorn backend.main:app --reload` running."
            )
        elif _is_logged_in():
            user = st.session_state.auth_user or {}
            st.caption(f"🟢 Signed in as **{_display_name(user.get('full_name') or user.get('username'))}** — same account as the mobile app.")
        else:
            st.caption("🟡 Browsing as a guest — runs won't be saved.")
    with right:
        if online and _is_logged_in():
            if st.button("Log out", key="logout_btn", use_container_width=True):
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                st.rerun()
        elif online and st.session_state.get("guest_mode"):
            if st.button("Log in", key="guest_login_btn", use_container_width=True):
                st.session_state.guest_mode = False
                st.rerun()


def _history_row_label(item: dict) -> str:
    when = str(item.get("created_at", ""))[:16].replace("T", " ")
    label = item.get("label") or item.get("chosen_crop", "")
    yld = item.get("predicted_yield_kg_ha")
    yld_txt = f" · {yld:,.0f} kg/ha" if yld is not None else ""
    return f"#{item['id']} · {when} · {label}{yld_txt}"


def _history_unavailable_notice():
    if not _backend_online():
        st.info(
            "Backend offline — start it with `uvicorn backend.main:app --reload` "
            "to save runs and use History/Compare, same as the mobile app."
        )
        return True
    if not _is_logged_in():
        st.info("Log in (top of page) to save runs and browse/compare your history.")
        return True
    return False


def _render_rotation_banner(advice: dict):
    """Crop-rotation alert card (shared by the Dashboard and the History page)."""
    chips = "".join(f"<span>{html.escape(c)}</span>" for c in advice["suggest"])
    cls = "rot-alert" if advice["level"] == "alert" else "rot-watch"
    st.markdown(f"""
    <div class="rot-card {cls}">
        <div class="rot-head"><span class="rot-ico"></span><b>Crop rotation alert</b></div>
        <p class="rot-line">{html.escape(advice["headline"])}</p>
        <p class="rot-why">{html.escape(advice["reason"])}</p>
        <div class="rot-sug"><small>Consider next season</small>{chips}</div>
    </div>
    """, unsafe_allow_html=True)


def _history_runs() -> list[dict]:
    """Runs from the account when logged in to a live backend, else from the local file."""
    if _backend_online() and _is_logged_in():
        try:
            page = web_client.list_history(st.session_state.auth_token, limit=50)
            return history_store.from_backend_items(page.get("items", []))
        except Exception:
            pass
    return history_store.list_runs()


def _current_rotation_advice(field: str):
    try:
        return history_store.rotation_advice(_history_runs(), field)
    except Exception:
        return None


def _save_run(label: str, crop: str, grown_crop: str, recommended: str, predicted: float, soil_values: dict) -> str:
    """Store one saved run with the crop the farmer finally grew. Returns 'account' or 'local'."""
    if _backend_online() and _is_logged_in():
        try:
            web_client.predict(
                st.session_state.auth_token, **soil_values, crop=crop, label=label or None,
                grown_crop=grown_crop, save=True,
            )
            st.cache_data.clear()
            return "account"
        except Exception:
            pass  # backend hiccup — keep the run locally rather than lose it
    history_store.add_run({
        "field": label, "crop": crop, "grown_crop": grown_crop, "recommended": recommended,
        "yield_kg_ha": round(float(predicted), 1), **soil_values,
    })
    return "local"


def render_history_page():
    """History tab. Runs are stored automatically each time Run analysis is
    pressed — in the account (shared with the mobile app) when logged in to a
    live backend, otherwise in a local file — and are checked for repeated
    crops so the farmer can be advised to rotate."""
    st.markdown('<div class="section-header">📜 History</div>', unsafe_allow_html=True)

    to_account = _backend_online() and _is_logged_in()
    if to_account:
        st.caption(
            "Runs you save here also show up in the mobile app's History tab, "
            "since it's the same account and the same data."
        )
    else:
        st.caption(
            "Runs you save are kept on this computer. Log in with the backend "
            "running to keep history in your account and share it with the mobile app."
        )

    token = st.session_state.get("auth_token")
    rows = []
    if to_account:
        try:
            items = web_client.list_history(token, limit=50).get("items", [])
        except web_client.ApiError as error:
            st.error(str(error))
            return
        for it in items:
            rows.append({
                "ID": it["id"], "Saved": str(it["created_at"])[:16].replace("T", " "),
                "Label": it.get("label") or "—", "Grown": it.get("grown_crop") or "—",
                "Analysed for": it["chosen_crop"],
                "Recommended": it.get("recommended_crop") or "—",
                "Yield (kg/ha)": it.get("predicted_yield_kg_ha"),
                "N": it["nitrogen"], "P": it["phosphorus"], "K": it["potassium"],
                "pH": it["ph"], "Temp °C": it["temperature"], "Rain mm": it["rainfall"],
            })
    else:
        for it in history_store.list_runs():
            rows.append({
                "ID": it["id"], "Saved": str(it["created_at"])[:16].replace("T", " "),
                "Label": it.get("field") or "—", "Grown": it.get("grown_crop") or "—",
                "Analysed for": it["crop"],
                "Recommended": it.get("recommended") or "—",
                "Yield (kg/ha)": it.get("yield_kg_ha"),
                "N": it.get("nitrogen"), "P": it.get("phosphorus"), "K": it.get("potassium"),
                "pH": it.get("ph"), "Temp °C": it.get("temperature"), "Rain mm": it.get("rainfall"),
            })

    if not rows:
        st.info("No saved runs yet — run an analysis on the Dashboard, then use **Save to field record** to store it here.")
        return

    # Rotation watch — one check per field
    st.markdown("**Rotation watch** — based on the crop actually grown")
    runs = _history_runs()
    fields = sorted({(r.get("field") or "").strip() for r in runs})
    shown = False
    for fld in fields:
        advice = history_store.rotation_advice(runs, fld)
        if advice:
            _render_rotation_banner(advice)
            shown = True
    if not shown:
        st.caption("✅ No repeated crops detected — the rotation across your runs looks healthy.")

    missing = [r for r in rows if r["Grown"] == "—"]
    if missing:
        with st.expander(f"{len(missing)} saved run(s) have no grown crop — not counted for rotation"):
            miss_options = {f"#{r['ID']} · {r['Saved']} · {r['Label']} · analysed for {r['Analysed for']}": r["ID"] for r in missing}
            miss_pick = st.selectbox("Run", list(miss_options.keys()), key="miss_pick")
            miss_crop = st.selectbox("Crop that was finally grown *", ALL_CROPS, index=None,
                                     placeholder="Select the crop", key="miss_crop")
            if st.button("Record grown crop", disabled=miss_crop is None):
                try:
                    if to_account:
                        web_client.update_history_entry(token, miss_options[miss_pick], grown_crop=miss_crop)
                    else:
                        history_store.set_grown_crop(miss_options[miss_pick], miss_crop)
                    st.cache_data.clear()
                    st.rerun()
                except web_client.ApiError as error:
                    st.error(str(error))

    st.markdown("<hr style='margin:20px 0'>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    options = {f"#{r['ID']} · {r['Saved']} · {r['Label']} · {r['Grown']}": r["ID"] for r in rows}
    delete_label = st.selectbox("Delete a saved run", ["—"] + list(options.keys()), key="delete_select")
    if st.button("🗑️ Delete", disabled=delete_label == "—"):
        try:
            if to_account:
                web_client.delete_history_entry(token, options[delete_label])
            else:
                history_store.delete_run(options[delete_label])
            st.success("Deleted.")
            st.cache_data.clear()
            st.rerun()
        except web_client.ApiError as error:
            st.error(str(error))


_DIRECTION_ICON = {"up": "⬆️", "down": "⬇️", "changed": "🔄", "same": "➖"}
_TONE_ICON = {"positive": "🟢", "negative": "🔴"}


def _fmt_num(value: float) -> str:
    """Up to two decimals, trailing zeros dropped: 1515.40 -> '1515.4', 5.00 -> '5'."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _change_bullet(item: dict) -> str:
    """One summary line, with a green/red dot only where the analysis itself
    defines better/worse (yield, status moving to/from Optimal)."""
    icon = _TONE_ICON.get(item.get("tone")) or _DIRECTION_ICON.get(item.get("direction"), "•")
    return f"- {icon} {item['text']}"


def _entry_caption(ref: dict, caption: str) -> str:
    when = str(ref.get("created_at") or "")[:16].replace("T", " ")
    return f"{caption}: **{ref['name']}**" + (f" ({when})" if when else "")


def _render_change_step(step: dict, heading: str, from_caption: str, to_caption: str) -> None:
    """Plain-language 'what changed' view for one earlier -> later pair."""
    st.markdown(f"#### {heading}")
    st.caption(
        f"{_entry_caption(step['from_entry'], from_caption)}  →  "
        f"{_entry_caption(step['to_entry'], to_caption)}"
    )

    crop_change = step.get("crop_change")
    yield_change = step.get("yield_change")
    if crop_change or yield_change:
        col_crop, col_yield = st.columns(2)
        if crop_change:
            with col_crop:
                if crop_change["changed"]:
                    st.metric("Recommended crop", f"{crop_change['before']} → {crop_change['after']}")
                    st.caption("Changed")
                else:
                    st.metric("Recommended crop", crop_change["after"])
                    st.caption("No change")
        if yield_change:
            with col_yield:
                delta = yield_change["delta"]
                if delta == 0:
                    st.metric("Predicted yield", f"{_fmt_num(yield_change['after'])} kg/ha")
                    st.caption("No change")
                else:
                    percent = yield_change.get("percent")
                    delta_text = f"{'+' if delta > 0 else '-'}{_fmt_num(abs(delta))} kg/ha"
                    if percent is not None:
                        delta_text += f" ({'+' if percent > 0 else '-'}{_fmt_num(abs(percent))}%)"
                    st.metric(
                        "Predicted yield",
                        f"{_fmt_num(yield_change['after'])} kg/ha",
                        delta=delta_text,
                        # Green/red only when the analysis defines better/worse.
                        delta_color="off" if yield_change.get("tone") == "neutral" else "normal",
                    )

    st.markdown("**Key changes**")
    if step["key_changes"]:
        st.markdown("\n".join(_change_bullet(item) for item in step["key_changes"]))
    else:
        st.caption("No differences were found between these analyses.")

    if step["interpretation"]:
        st.info("**What this means**\n\n" + "\n".join(f"- {line}" for line in step["interpretation"]))

    if step["sections"]:
        with st.expander("Full breakdown"):
            for section in step["sections"]:
                st.markdown(f"**{section['title']}**")
                st.markdown("\n".join(_change_bullet(item) for item in section["items"]))

    for note in step["notes"]:
        st.caption(f"ℹ️ {note}")


def render_compare_page():
    """Compare tab — the website's equivalent of
    mobile/lib/screens/compare_screen.dart. Pick 2–4 saved runs and get a
    plain-language summary of what changed between them (soil readings,
    recommended crop, yield, fertilizer advice, soil-adjustment status), with
    the raw field-by-field table underneath as supporting detail.

    Compare is not crop-rotation analysis: "recommended crop" is only the
    model's suggestion for each saved run."""
    st.markdown('<div class="section-header">⚖️ Compare</div>', unsafe_allow_html=True)
    st.caption("Pick 2–4 saved runs from your History to see what changed between them.")

    if _history_unavailable_notice():
        return

    token = st.session_state.auth_token
    try:
        page = web_client.list_history(token, limit=50)
    except web_client.ApiError as error:
        st.error(str(error))
        return

    items = page.get("items", [])
    if len(items) < 2:
        st.caption("Save at least 2 runs on the 📜 History tab first, then come back here to compare them.")
        return

    options = {_history_row_label(it): it["id"] for it in items}
    chosen_labels = st.multiselect(
        "Select 2–4 saved runs to compare",
        options=list(options.keys()),
        max_selections=4,
        key="compare_multiselect",
    )
    if st.button("⚖️ Compare selected", disabled=len(chosen_labels) < 2):
        ids = [options[lbl] for lbl in chosen_labels]
        try:
            st.session_state["last_compare"] = web_client.compare(token, ids)
        except web_client.ApiError as error:
            st.error(str(error))

    compare_result = st.session_state.get("last_compare")
    if compare_result:
        st.markdown("<hr style='margin:20px 0'>", unsafe_allow_html=True)

        # The API returns runs oldest -> newest, whatever order they were picked in.
        summary = compare_result.get("summary")
        if summary:
            steps = summary["steps"]
            if summary.get("overall"):
                _render_change_step(summary["overall"], "Overall: first to last", "First", "Last")
                st.markdown("<hr style='margin:20px 0'>", unsafe_allow_html=True)
            for index, step in enumerate(steps, start=1):
                if len(steps) == 1:
                    _render_change_step(step, "What changed", "Previous", "Current")
                else:
                    _render_change_step(step, f"Step {index} of {len(steps)}", "Earlier", "Later")
                st.markdown("<hr style='margin:20px 0'>", unsafe_allow_html=True)

        with st.expander("Detailed comparison (field by field)", expanded=not summary):
            entry_labels = [
                e.get("label") or f"#{e['id']} ({e['chosen_crop']})" for e in compare_result["entries"]
            ]
            rows = []
            for row in compare_result["rows"]:
                record = {"Field": row["field"], "Unit": row["unit"] or ""}
                for lbl, val in zip(entry_labels, row["values"]):
                    record[lbl] = val
                record["Changed"] = "✅" if row["changed"] else ""
                rows.append(record)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════
#  CHAT ASSISTANT — defined early (not at the bottom of the script) since
#  the History/Compare pages above may call chat_launcher() before the
#  Predict page's code further down the script ever runs.
# ═══════════════════════════════════════════════
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of {"role": "user"|"model", "text": str}
if "chat_lang" not in st.session_state:
    st.session_state.chat_lang = "auto"  # "auto" | "en" | "hi" | "mr"

# Matches the mobile app's reply-language chips (mobile/lib/screens/chat_screen.dart)
# so the two clients behave the same way: "Auto" replies in whatever language the
# message was typed in; the others force a language regardless of the input script.
_CHAT_LANG_LABELS = {"auto": "Auto", "en": "English", "hi": "हिंदी", "mr": "मराठी"}

# Backing key for the draft question box. A widget's session-state value can
# only be changed *before* that widget is instantiated in a given run — never
# after — so both the mic (which prepends dictated text) and "clear it once
# Send is pressed" have to write here ahead of the st.text_input() call below,
# same trick either way, just on different runs.
_CHAT_DRAFT_KEY = "chat_draft_text"


def _rerun_dialog():
    """Redraw only the chat dialog, so it stays open.

    A plain `st.rerun()` restarts the whole page script, and a full rerun always
    closes an `st.dialog`. `scope="fragment"` (Streamlit >= 1.37) re-runs just the
    dialog, which is its own fragment. Falls back to a full rerun on a Streamlit
    that doesn't support it, so the chat degrades to the old behaviour instead of
    erroring.
    """
    try:
        st.rerun(scope="fragment")
    except (TypeError, st.errors.StreamlitAPIException):
        st.rerun()


@st.dialog("💬 Ask Smart Agri", width="large")
def open_chat_dialog(report):
    st.caption(
        "Ask about this run's crop recommendation, soil status, fertilizer "
        "plan, or yield prediction — in English, Hindi, or Marathi. Common "
        "questions are answered instantly; anything else is handled by the "
        "Gemini API. Tap the mic to speak your question, or type below."
    )

    st.radio(
        "Reply language",
        options=list(_CHAT_LANG_LABELS.keys()),
        format_func=lambda code: _CHAT_LANG_LABELS[code],
        horizontal=True,
        key="chat_lang",
        label_visibility="collapsed",
    )

    api_key = get_gemini_api_key()
    with st.expander("🔑 Gemini API key (optional — only needed for less common questions)", expanded=False):
        st.caption(
            "Put GEMINI_API_KEY in a .env file next to app.py to load it "
            "automatically, or paste a key below just for this session."
        )
        manual_key = st.text_input(
            "Gemini API key", value="", type="password", label_visibility="collapsed",
            placeholder="Paste your Gemini API key",
        )
        if manual_key and manual_key != st.session_state.get("gemini_api_key_override"):
            st.session_state["gemini_api_key_override"] = manual_key
            _rerun_dialog()  # redraw just this dialog — a full st.rerun() would close it
        if api_key:
            st.caption("✅ A key is currently configured.")

    if not report:
        st.info("Run an analysis on the Dashboard first for crop-specific answers.")

    for i, turn in enumerate(st.session_state.chat_history):
        with st.chat_message("user" if turn["role"] == "user" else "assistant"):
            st.markdown(turn["text"])
            if turn["role"] == "model":
                # Read-aloud control — the web equivalent of the app's speaker
                # icon under each assistant reply (mobile/lib/voice/tts_service.dart).
                speak_button(to_plain_text(turn["text"]), key=f"hist_{i}")

    # A Send just happened on the *previous* run — clear the draft now,
    # before the text_input below is created, per the note above.
    if st.session_state.pop("_chat_clear_pending", False):
        st.session_state[_CHAT_DRAFT_KEY] = ""
    if _CHAT_DRAFT_KEY not in st.session_state:
        st.session_state[_CHAT_DRAFT_KEY] = ""

    # Browser-based voice input (Web Speech API) — the website's equivalent
    # of the mobile app's mic button (mobile/lib/voice/speech_input_service.dart).
    # Runs entirely client-side; no audio reaches this server. The transcript
    # is *appended into the same draft box below*, exactly like the mobile
    # app's `_onSpeechResult`: dictation fills the field, it stays editable,
    # and the person still presses Send — nothing here auto-submits.
    dictated = voice_input_component(key="chat_mic")
    if dictated:
        existing = st.session_state[_CHAT_DRAFT_KEY].strip()
        st.session_state[_CHAT_DRAFT_KEY] = f"{existing} {dictated}".strip() if existing else dictated

    field_col, send_col = st.columns([9, 1], vertical_alignment="bottom")
    with field_col:
        st.text_input(
            "Ask about your crop, soil, fertilizer, or yield results…",
            key=_CHAT_DRAFT_KEY,
            label_visibility="collapsed",
            placeholder="Ask about your crop, soil, fertilizer, or yield results…",
        )
    with send_col:
        send_clicked = st.button("➤", key="chat_send", help="Send")

    user_question = None
    if send_clicked:
        candidate = st.session_state[_CHAT_DRAFT_KEY].strip()
        if candidate:
            user_question = candidate
            st.session_state["_chat_clear_pending"] = True

    if user_question:
        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                answer, source = answer_question(
                    user_message=user_question,
                    report=report,
                    history=st.session_state.chat_history,
                    api_key=api_key,
                    lang=st.session_state.chat_lang,
                )
            st.markdown(answer)
            if source == "intent":
                st.caption("⚡ Answered instantly — no API call needed.")
            speak_button(to_plain_text(answer), key=f"live_{len(st.session_state.chat_history)}")

        st.session_state.chat_history.append({"role": "user", "text": user_question})
        st.session_state.chat_history.append({"role": "model", "text": answer})
        # Redraw with the draft box actually cleared, not just cosmetically emptied.
        # Re-runs only this dialog (see _rerun_dialog), so the chat stays open with its
        # history, language choice and scroll position. The old plain st.rerun() re-ran
        # the entire app script, and a full rerun always closes an st.dialog — that was
        # the "chat resets / goes back after every reply" bug.
        _rerun_dialog()


@st.fragment
def chat_launcher(report):
    """Wrapped in a fragment so clicking the floating icon only reruns this
    tiny bit of the page — not the sliders, models, and charts above it."""
    if st.button("💬", key="chat_fab", help="Ask Smart Agri about your results"):
        open_chat_dialog(report)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,500;6..72,600;6..72,700&display=swap');

/* AgriSmart look: warm paper background, forest-green primary, gold accent,
   Newsreader display serif, Manrope body, DM Mono eyebrow labels. */

.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 1rem !important;
    max-width: 1440px;
}

:root {
    --bg:           #F8F6EF;
    --surface:      #FCFAF5;
    --surface-warm: #FCFAF5;
    --secondary:    #EEE8D9;
    --linen:        #EEE8D9;
    --muted:        #EBE7DC;
    --border:       #DCD8CC;
    --input:        #C9C5B8;
    --dark:         #213329;
    --mid:          #4D5D54;
    --soft:         #68756D;
    --primary:      #244F3B;
    --primary-dark: #1B3D2E;
    --accent:       #E9B84B;
    --accent-ink:   #213329;
    --sidebar:      #1E3A2B;
    --sidebar-hi:   #2F4B3B;
    --sidebar-line: #37503F;
    --sidebar-text: #F2EFE6;
    --destructive:  #B9483D;
    --green:        #244F3B;
    --red:          #B9483D;
    --yellow:       #8A6414;
    --radius:       14px;
    --paper-shadow: 0 14px 40px rgba(33,51,41,0.08), 0 2px 8px rgba(33,51,41,0.04);
}

/* ───────────────────────────────────────── */
/* GLOBAL APP */
/* ───────────────────────────────────────── */

.stApp {
    background: var(--bg);
    color: var(--dark);
}

html,
body,
[class*="css"],
label,
p,
span,
div {
    font-family: 'Manrope', sans-serif;
    color: var(--dark) !important;
}

h1, h2, h3 {
    font-family: 'Newsreader', Georgia, serif !important;
    color: var(--primary) !important;
    letter-spacing: -0.01em;
}

::selection { background: var(--accent); color: var(--accent-ink); }

[data-testid="stHeader"] { background: transparent; }

.mono-label {
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ───────────────────────────────────────── */
/* SIDEBAR — dark forest rail with brand + nav */
/* ───────────────────────────────────────── */

[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: none;
    min-width: 272px !important;
    max-width: 272px !important;
}

[data-testid="stSidebar"] > div:first-child {
    background: var(--sidebar) !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding: 1.4rem 1.1rem;
}

[data-testid="stSidebar"] *,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label {
    color: var(--sidebar-text) !important;
}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="collapsedControl"] button {
    color: var(--sidebar-text) !important;
}

.brand-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 8px 0;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: var(--accent);
    font-size: 20px;
}

.brand-name {
    display: block;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: -0.01em;
    line-height: 1.15;
}

.brand-sub {
    display: block;
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.55;
    margin-top: 2px;
}

.side-label {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.42;
    padding: 34px 12px 8px;
    margin: 0;
}

.side-note {
    margin-top: 28px;
    border: 1px solid var(--sidebar-line);
    background: rgba(47,75,59,0.6);
    border-radius: 16px;
    padding: 14px 16px;
    font-size: 11px;
    line-height: 1.55;
}

.side-note b {
    color: var(--accent) !important;
    font-size: 12px;
}

/* Section nav (the st.radio in the sidebar) → vertical nav pills.
   Selectors cover both Streamlit's older (baseweb) and newer (react-aria)
   radio markup. */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"] {
    gap: 4px;
    flex-direction: column;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] {
    width: 100%;
    margin: 0;
    padding: 11px 14px;
    border-radius: 12px;
    cursor: pointer;
    transition: background 0.18s ease;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:hover,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {
    background: var(--sidebar-hi);
}

/* hide the round radio dot — the pill itself shows the selection */
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {
    display: none !important;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {
    font-size: 13px;
    font-weight: 600;
    opacity: 0.72;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) {
    background: var(--accent);
    box-shadow: 0 1px 2px rgba(0,0,0,0.18);
}

[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) *,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) * {
    color: var(--accent-ink) !important;
    opacity: 1;
    font-weight: 700;
}

/* ───────────────────────────────────────── */
/* PAGE HERO */
/* ───────────────────────────────────────── */

.page-eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--primary) !important;
    opacity: 0.72;
}

.page-title {
    font-family: 'Newsreader', Georgia, serif !important;
    font-size: 3rem;
    line-height: 0.98;
    letter-spacing: -0.02em;
    color: var(--primary) !important;
    margin: 8px 0 0;
    font-weight: 600;
}

.page-title em {
    font-style: normal;
    color: var(--accent) !important;
}

.page-desc {
    margin: 14px 0 0;
    max-width: 620px;
    font-size: 0.88rem;
    line-height: 1.6;
    color: var(--soft) !important;
}

.crop-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
}

.crop-chips span {
    border-radius: 999px;
    background: var(--secondary);
    padding: 5px 12px;
    font-size: 10px;
    font-weight: 700;
    color: var(--primary) !important;
}

/* ───────────────────────────────────────── */
/* METRICS — paper cards */
/* ───────────────────────────────────────── */

[data-testid="metric-container"],
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    min-height: 112px;
    box-shadow: var(--paper-shadow);
    transition: box-shadow 0.18s ease, transform 0.3s ease;
}

[data-testid="metric-container"]:hover,
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
}

[data-testid="stMetricValue"] {
    font-family: 'Manrope', sans-serif;
    font-weight: 800;
    letter-spacing: -0.02em;
    font-size: 1.7rem !important;
    color: var(--primary) !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--soft) !important;
    font-size: 0.66rem;
}

/* ───────────────────────────────────────── */
/* BUTTONS */
/* ───────────────────────────────────────── */

.stButton > button {
    background: var(--primary) !important;
    color: #F8F6EF !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 28px !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.9rem !important;
    box-shadow: 0 1px 2px rgba(33,51,41,0.18);
    transition: all 0.18s ease;
}

.stButton > button *,
.stButton > button p {
    color: #F8F6EF !important;
    font-weight: 800 !important;
}

.stButton > button:hover {
    background: var(--primary-dark) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 14px rgba(33,51,41,0.22);
}

/* ───────────────────────────────────────── */
/* SLIDERS */
/* ───────────────────────────────────────── */

.stSlider label {
    color: var(--dark) !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
}

.stSlider span {
    color: var(--dark) !important;
}

.stSlider [data-baseweb="slider"] {
    accent-color: var(--primary);
}

.stSlider [role="slider"] {
    background-color: var(--primary) !important;
    border-color: var(--primary) !important;
}

/* ───────────────────────────────────────── */
/* SELECTBOX */
/* ───────────────────────────────────────── */

.stSelectbox label {
    color: var(--dark) !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
}

[data-baseweb="select"] * {
    color: var(--dark) !important;
}

[data-baseweb="select"] {
    border-radius: 12px !important;
    background-color: var(--bg) !important;
}

[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] div,
[data-baseweb="select"] span,
[data-baseweb="select"] input {
    background-color: var(--bg) !important;
    color: var(--dark) !important;
}

[data-testid="stSelectbox"] [role="group"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: var(--bg) !important;
    border: 1px solid var(--input) !important;
    border-radius: 12px !important;
}

[data-testid="stSelectbox"] input {
    color: var(--dark) !important;
    -webkit-text-fill-color: var(--dark) !important;
    background: transparent !important;
}

[data-baseweb="popover"] {
    background-color: var(--surface) !important;
}

[data-baseweb="popover"] * {
    background-color: var(--surface) !important;
    color: var(--dark) !important;
}

[data-baseweb="menu"] {
    background-color: var(--surface) !important;
}

[data-baseweb="menu"] li:hover {
    background-color: var(--secondary) !important;
}

/* ───────────────────────────────────────── */
/* INPUTS */
/* ───────────────────────────────────────── */

input,
textarea {
    color: var(--dark) !important;
}

[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {
    border: 1px solid var(--input) !important;
    border-radius: 12px !important;
    background: var(--bg) !important;
    color: var(--dark) !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(36,79,59,0.15) !important;
}

/* ───────────────────────────────────────── */
/* DIVIDERS */
/* ───────────────────────────────────────── */

hr {
    border-color: var(--border) !important;
}

/* ───────────────────────────────────────── */
/* STATUS BADGES */
/* ───────────────────────────────────────── */

.ok {
    background: #E3EEE6;
    color: #244F3B !important;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.low {
    background: #F8E6E3;
    color: #B9483D !important;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.high {
    background: #FBF1D6;
    color: #8A6414 !important;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ───────────────────────────────────────── */
/* SECTION HEADERS */
/* ───────────────────────────────────────── */

.section-header {
    font-family: 'Newsreader', Georgia, serif !important;
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--primary) !important;
    border-left: 4px solid var(--accent);
    padding-left: 14px;
    margin: 30px 0 18px;
    letter-spacing: -0.01em;
}

/* ───────────────────────────────────────── */
/* DATAFRAME STYLING */
/* ───────────────────────────────────────── */

[data-testid="stDataFrame"] {
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border);
}

/* ───────────────────────────────────────── */
/* PLOTLY */
/* ───────────────────────────────────────── */

.js-plotly-plot .plotly .modebar {
    background: rgba(252,250,245,0.8) !important;
    border-radius: 8px;
}

/* ───────────────────────────────────────── */
/* ALERTS / EXPANDERS / CAPTIONS */
/* ───────────────────────────────────────── */

[data-testid="stAlert"],
[data-testid="stAlert"] > div {
    border-radius: var(--radius);
    background: var(--secondary) !important;
}

[data-testid="stAlert"] {
    border: 1px solid var(--border);
}

[data-testid="stExpander"] {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

[data-testid="stCaptionContainer"] {
    color: var(--soft) !important;
}

/* ───────────────────────────────────────── */
/* TABS (login / register) */
/* ───────────────────────────────────────── */

[data-baseweb="tab-list"] {
    background: var(--muted);
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
}

[data-baseweb="tab"] {
    border-radius: 9px;
    font-weight: 800;
}

[data-baseweb="tab-highlight"] {
    background: var(--surface) !important;
    border-radius: 9px;
    height: 100% !important;
    z-index: 0;
    box-shadow: 0 1px 2px rgba(33,51,41,0.12);
}

[data-baseweb="tab-border"] { display: none; }

/* ───────────────────────────────────────── */
/* SCROLLBAR */
/* ───────────────────────────────────────── */

::-webkit-scrollbar {
    width: 10px;
}

::-webkit-scrollbar-track {
    background: #EBE7DC;
}

::-webkit-scrollbar-thumb {
    background: #C3BEAE;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: #A9A493;
}

/* ───────────────────────────────────────── */
/* CHAT — floating action button + dialog    */
/* ───────────────────────────────────────── */

.st-key-chat_fab button {
    position: fixed !important;
    left: auto !important;
    right: 28px !important;
    bottom: 28px;
    z-index: 9999;
    width: 58px !important;
    height: 58px !important;
    border-radius: 50% !important;
    padding: 0 !important;
    background: var(--accent) !important;
    font-size: 1.5rem !important;
    line-height: 1 !important;
    box-shadow: 0 8px 22px rgba(33,51,41,0.30) !important;
    display: flex;
    align-items: center;
    justify-content: center;
}

.st-key-chat_fab button * { color: var(--accent-ink) !important; }

.st-key-chat_fab button:hover {
    background: #DDA932 !important;
    transform: translateY(-2px) scale(1.04);
    box-shadow: 0 10px 26px rgba(33,51,41,0.36) !important;
}

[data-testid="stChatMessage"] {
    background: var(--secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
}

/* ───────────────────────────────────────── */
/* CHAT DIALOG — the modal renders in its own portal, */
/* outside .stApp, so it needs the theme pinned here. */
/* ───────────────────────────────────────── */

[data-testid="stDialog"] div[role="dialog"] {
    background: var(--surface) !important;
    border-radius: 20px;
}

[data-testid="stDialog"] div[role="dialog"] * {
    color: var(--dark) !important;
}

[data-testid="stDialog"] div[role="dialog"] h1,
[data-testid="stDialog"] div[role="dialog"] h2 {
    font-family: 'Newsreader', Georgia, serif !important;
    color: var(--primary) !important;
}

[data-testid="stDialog"] [data-testid="stCaptionContainer"],
[data-testid="stDialog"] [data-testid="stCaptionContainer"] * {
    color: var(--mid) !important;
    opacity: 1 !important;
}
/* ═════════ REFERENCE-STYLE REFINEMENTS ═════════ */

/* sidebar: round gold logo, icon nav, chevron on active, pinned note */
.brand-mark {
    width: 42px; height: 42px; border-radius: 50%;
    background: transparent !important;
    border: 2px solid var(--accent);
    position: relative;
}
.brand-mark::after {
    content: ""; position: absolute; inset: 9px;
    background: var(--accent);
    -webkit-mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='2.2'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M11%2020A7%207%200%200%201%209.8%206.1C15.5%205%2017%204.48%2019%202c1%202%202%204.18%202%208%200%205.5-4.78%2010-10%2010Z'/%3E%3Cpath%20d='M2%2021c0-3%201.85-5.36%205.08-6C9.5%2014.52%2012%2013%2013%2012'/%3E%3C/svg%3E") center/contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='2.2'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M11%2020A7%207%200%200%201%209.8%206.1C15.5%205%2017%204.48%2019%202c1%202%202%204.18%202%208%200%205.5-4.78%2010-10%2010Z'/%3E%3Cpath%20d='M2%2021c0-3%201.85-5.36%205.08-6C9.5%2014.52%2012%2013%2013%2012'/%3E%3C/svg%3E") center/contain no-repeat;
}
.side-label { padding: 38px 12px 10px; }

[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] {
    display: flex; align-items: center; gap: 12px;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]::before,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]::before {
    content: ""; width: 18px; height: 18px; flex: 0 0 18px;
    background: currentColor; opacity: .75;
    -webkit-mask: var(--nav-ico) center/contain no-repeat;
            mask: var(--nav-ico) center/contain no-repeat;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked)::before,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)::before {
    background: var(--accent-ink); opacity: 1;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]::after,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]::after {
    content: ""; margin-left: auto; width: 16px; height: 16px; display: none;
    background: var(--accent-ink);
    -webkit-mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='m9%2018%206-6-6-6'/%3E%3C/svg%3E") center/contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='m9%2018%206-6-6-6'/%3E%3C/svg%3E") center/contain no-repeat;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked)::after,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)::after {
    display: block;
}
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:nth-child(1) [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:nth-of-type(1) { --nav-ico: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M7%2020h10'/%3E%3Cpath%20d='M10%2020c5.5-2.5.8-6.4%203-10'/%3E%3Cpath%20d='M9.5%209.4c1.1.8%201.8%202.2%202.3%203.7-2%20.4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2%202.8-.5%204.4%200%205.5.8z'/%3E%3Cpath%20d='M14.1%206a7%207%200%200%200-1.1%204c1.9-.1%203.3-.6%204.3-1.4%201-1%201.6-2.3%201.7-4.6-2.7.1-4%201-4.9%202z'/%3E%3C/svg%3E"); }
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:nth-child(2) [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:nth-of-type(2) { --nav-ico: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M3%2012a9%209%200%201%200%209-9%209.75%209.75%200%200%200-6.74%202.74L3%208'/%3E%3Cpath%20d='M3%203v5h5'/%3E%3Cpath%20d='M12%207v5l4%202'/%3E%3C/svg%3E"); }
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:nth-child(3) [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:nth-of-type(3) { --nav-ico: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='m16%2016%203-8%203%208c-.87.65-1.92%201-3%201s-2.13-.35-3-1Z'/%3E%3Cpath%20d='m2%2016%203-8%203%208c-.87.65-1.92%201-3%201s-2.13-.35-3-1Z'/%3E%3Cpath%20d='M7%2021h10'/%3E%3Cpath%20d='M12%203v18'/%3E%3Cpath%20d='M3%207h2c2%200%205-1%207-2%202%201%205%202%207%202h2'/%3E%3C/svg%3E"); }

.side-note {
    position: fixed; left: 20px; bottom: 22px; width: 232px; margin: 0;
    border-radius: 18px; padding: 16px 18px;
}
.side-note-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.side-note-ico {
    width: 16px; height: 16px; background: var(--accent);
    -webkit-mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M20%2013c0%205-3.5%207.5-7.66%208.95a1%201%200%200%201-.67-.01C7.5%2020.5%204%2018%204%2013V6a1%201%200%200%201%201-1c2%200%204.5-1.2%206.24-2.72a1.17%201.17%200%200%201%201.52%200C14.51%203.81%2017%205%2019%205a1%201%200%200%201%201%201z'/%3E%3Cpath%20d='m9%2012%202%202%204-4'/%3E%3C/svg%3E") center/contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M20%2013c0%205-3.5%207.5-7.66%208.95a1%201%200%200%201-.67-.01C7.5%2020.5%204%2018%204%2013V6a1%201%200%200%201%201-1c2%200%204.5-1.2%206.24-2.72a1.17%201.17%200%200%201%201.52%200C14.51%203.81%2017%205%2019%205a1%201%200%200%201%201%201z'/%3E%3Cpath%20d='m9%2012%202%202%204-4'/%3E%3C/svg%3E") center/contain no-repeat;
}

/* top bar */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 4px 4px 14px; margin-bottom: 18px;
    border-bottom: 1px solid var(--border);
}
.topbar-l { display: flex; align-items: center; gap: 10px; font-size: .82rem; color: var(--mid) !important; }
.topbar-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); display: inline-block; }
.topbar-dot.gold { background: var(--accent); }
.topbar-r { display: flex; align-items: center; gap: 12px; }
.topbar-who { text-align: right; line-height: 1.2; }
.topbar-who b { display: block; font-size: .8rem; }
.topbar-who small { font-size: .66rem; color: var(--soft) !important; }
.topbar-avatar {
    width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center;
    background: var(--secondary); font-size: .72rem; font-weight: 800; color: var(--primary) !important;
}

/* white cards (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    box-shadow: var(--paper-shadow);
    padding: 10px 14px 14px;
}
.card-head { display: flex; justify-content: space-between; gap: 16px; margin: 6px 4px 18px; }
.card-title { margin: 0; font-size: 1.02rem; font-weight: 800; color: var(--primary) !important; }
.card-sub { margin: 4px 0 0; font-size: .8rem; line-height: 1.5; color: var(--soft) !important; max-width: 430px; }
.card-tag { font-size: 9px; color: var(--soft) !important; white-space: nowrap; padding-top: 8px; }

/* big run button */
.st-key-run_btn button {
    height: 52px; border-radius: 16px !important; font-size: .95rem !important;
    background: var(--primary) !important;
}

/* right panel: empty state */
.empty-panel {
    min-height: 600px; display: flex; flex-direction: column; justify-content: space-between;
    border: 1px solid var(--border); border-radius: 20px;
    background: linear-gradient(180deg, rgba(238,232,217,.55), rgba(238,232,217,.18));
    padding: 30px;
}
.empty-ico {
    display: block; width: 50px; height: 50px; border-radius: 16px; background: var(--accent);
    position: relative; margin-bottom: 26px;
}
.empty-ico::after {
    content: ""; position: absolute; inset: 14px; background: var(--accent-ink);
    -webkit-mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M7%2020h10'/%3E%3Cpath%20d='M10%2020c5.5-2.5.8-6.4%203-10'/%3E%3Cpath%20d='M9.5%209.4c1.1.8%201.8%202.2%202.3%203.7-2%20.4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2%202.8-.5%204.4%200%205.5.8z'/%3E%3Cpath%20d='M14.1%206a7%207%200%200%200-1.1%204c1.9-.1%203.3-.6%204.3-1.4%201-1%201.6-2.3%201.7-4.6-2.7.1-4%201-4.9%202z'/%3E%3C/svg%3E") center/contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='1.8'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M7%2020h10'/%3E%3Cpath%20d='M10%2020c5.5-2.5.8-6.4%203-10'/%3E%3Cpath%20d='M9.5%209.4c1.1.8%201.8%202.2%202.3%203.7-2%20.4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2%202.8-.5%204.4%200%205.5.8z'/%3E%3Cpath%20d='M14.1%206a7%207%200%200%200-1.1%204c1.9-.1%203.3-.6%204.3-1.4%201-1%201.6-2.3%201.7-4.6-2.7.1-4%201-4.9%202z'/%3E%3C/svg%3E") center/contain no-repeat;
}
.empty-panel h2 { font-size: 2.5rem; line-height: 1.02; margin: 0 0 18px; font-weight: 500; max-width: 420px; }
.empty-panel p { font-size: .95rem; line-height: 1.6; color: var(--soft) !important; max-width: 400px; margin: 0; }
.empty-foot { display: flex; align-items: center; gap: 10px; font-size: .8rem; font-weight: 700; }

/* right panel: decision returned */
.res-card {
    min-height: 600px; border-radius: 20px; overflow: hidden; display: flex; flex-direction: column;
    background: var(--primary); box-shadow: var(--paper-shadow);
}
.res-card, .res-card div, .res-card span, .res-card p, .res-card small, .res-card b, .res-card h2, .res-card i {
    color: #F2EFE6 !important;
}
.res-top { padding: 30px; flex: 1; }
.res-row { display: flex; justify-content: space-between; align-items: center; }
.res-card .res-eyebrow { font-size: 10px; color: var(--accent) !important; }
.res-pill { background: rgba(255,255,255,.12); border-radius: 999px; padding: 4px 12px; font-size: 10px; font-weight: 800; }
.res-main { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-top: 70px; }
.res-label { margin: 0; font-size: .8rem; opacity: .65; }
.res-card .res-crop { font-size: 3.4rem; line-height: 1; margin: 8px 0 12px; font-weight: 500; color: var(--accent) !important; }
.res-sub { margin: 0; font-size: .9rem; opacity: .75; max-width: 320px; line-height: 1.5; }
.res-conf { text-align: right; line-height: 1; }
.res-conf span { font-size: 4rem; font-weight: 800; letter-spacing: -.03em; }
.res-conf i { font-style: normal; font-size: 1.4rem; font-weight: 700; }
.res-conf small { display: block; margin-top: 8px; font-size: .66rem; letter-spacing: .08em; text-transform: uppercase; opacity: .6; }
.res-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(255,255,255,.14); }
.res-grid > div { background: var(--primary); padding: 18px 30px; }
.res-grid small { display: block; font-size: .66rem; letter-spacing: .08em; text-transform: uppercase; opacity: .6; margin-bottom: 4px; }
.res-grid b { font-size: 1.05rem; font-weight: 800; }
.res-card .res-crop, .res-card .res-crop * { color: var(--accent) !important; }
.card-head p.card-sub { font-size: .8rem !important; line-height: 1.5 !important; }
.empty-panel, .res-card { min-height: 560px; }
.rot-card {
    border-radius: 18px; padding: 18px 22px; margin: 0 0 22px;
    border: 1px solid #E6D3A0; background: #FBF1D6;
}
.rot-card.rot-alert { border-color: #E6BDB6; background: #F8E6E3; }
.rot-head { display: flex; align-items: center; gap: 10px; font-size: .9rem; }
.rot-ico {
    width: 18px; height: 18px; background: #8A6414;
    -webkit-mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='2'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='m17%202%204%204-4%204'/%3E%3Cpath%20d='M3%2011v-1a4%204%200%200%201%204-4h14'/%3E%3Cpath%20d='m7%2022-4-4%204-4'/%3E%3Cpath%20d='M21%2013v1a4%204%200%200%201-4%204H3'/%3E%3C/svg%3E") center/contain no-repeat; mask: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='black'%20stroke-width='2'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='m17%202%204%204-4%204'/%3E%3Cpath%20d='M3%2011v-1a4%204%200%200%201%204-4h14'/%3E%3Cpath%20d='m7%2022-4-4%204-4'/%3E%3Cpath%20d='M21%2013v1a4%204%200%200%201-4%204H3'/%3E%3C/svg%3E") center/contain no-repeat;
}
.rot-alert .rot-ico { background: #B9483D; }
.rot-card .rot-line { margin: 8px 0 2px; font-weight: 800; font-size: 1rem; color: var(--dark) !important; }
.rot-card .rot-why { margin: 0 0 12px; font-size: .85rem; line-height: 1.5; color: var(--mid) !important; }
.rot-sug { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.rot-sug small { font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; color: var(--soft) !important; margin-right: 4px; }
.rot-sug span { background: var(--primary); border-radius: 999px; padding: 4px 14px; font-size: .75rem; font-weight: 800; color: #F8F6EF !important; }
</style>
""", unsafe_allow_html=True)

# ── Plotly defaults ──────────────────────────
EARTHY = ["#244F3B","#E9B84B","#D98A4F","#4A8FA3","#8DA555","#B9483D","#B7B29E"]
DARK_FONT = dict(family="Manrope", color="#213329", size=11)
TICK_FONT = dict(color="#213329", size=11)
TITLE_FONT = dict(color="#213329", size=12)

PL = dict(
    font=dict(family="Manrope", color="#213329"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=16, r=16, t=36, b=16),
    colorway=EARTHY,
)

# ── Module imports (graceful) ────────────────
sys.path.insert(0, os.path.dirname(__file__))

@st.cache_resource(show_spinner=False)
def load_modules():
    m = {}
    for name, path, fn in [
        ("compute_nutrient_gap", "modules.soil_adjustment",          "compute_nutrient_gap"),
        ("recommend_fertilizer", "modules.fertilizer_recommendation", "recommend_fertilizer"),
        ("predict_yield",        "modules.yield_model",               "predict_yield"),
    ]:
        try:
            mod = __import__(path, fromlist=[fn])
            m[name] = getattr(mod, fn)
        except Exception:
            m[name] = None
    try:
        import pickle
        with open(os.path.join("models", "crop_model.pkl"), "rb") as f:
            m["crop_model"] = pickle.load(f)
    except Exception:
        m["crop_model"] = None
    return m

mods = load_modules()

# ── Demo/fallback helpers ────────────────────
ALL_CROPS = ["Jowar", "Groundnut", "Cotton", "Sugarcane", "Wheat"]

YIELD_BASELINE = {
    "Jowar":     2800,
    "Groundnut": 2200,
    "Cotton":    2400,
    "Sugarcane": 70000,
    "Wheat":     3100,
}

def demo_crops(N, P, K, T, R, pH):
    seed = int(N * 7 + P * 13 + K * 17 + T * 3 + R * 0.1 + pH * 100) % (2**31)
    rng  = np.random.default_rng(seed)
    raw  = rng.dirichlet(np.ones(len(ALL_CROPS)) * 2)
    top5 = sorted(zip(ALL_CROPS, raw), key=lambda x: -x[1])[:5]
    tot  = sum(v for _, v in top5)
    return [(c, round(v / tot * 100, 1)) for c, v in top5]

def demo_soil(N, P, K, pH):
    OPT  = {"Nitrogen":(40,100), "Phosphorus":(25,80), "Potassium":(20,70), "pH":(5.5,7.5)}
    vals = {"Nitrogen":N, "Phosphorus":P, "Potassium":K, "pH":pH}
    rows = []
    for nut, (lo, hi) in OPT.items():
        v = vals[nut]
        if v < lo:   status, gap = "Low",     round(lo - v, 2)
        elif v > hi: status, gap = "High",    round(v - hi, 2)
        else:        status, gap = "Optimal", 0.0
        rows.append({"Nutrient":nut, "Value":round(v,2),
                     "Range":f"{lo}–{hi}", "Gap":gap, "Status":status})
    return pd.DataFrame(rows)

def demo_fert(crop, N, P, K):
    recs = []
    if N < 40:
        d = max(25, round((40-N)/0.46/25)*25)
        recs.append({"Fertilizer":"Urea (46-0-0)",  "NPK":"46-0-0",  "Dosage (kg/ha)":d, "Dose Range":f"{max(0,d-12)}–{d+12} kg/ha", "Reason":"Low nitrogen", "Nutrient":"Nitrogen", "Condition":"Low"})
    if P < 25:
        d = max(25, round((25-P)/0.46/25)*25)
        recs.append({"Fertilizer":"DAP (18-46-0)",  "NPK":"18-46-0", "Dosage (kg/ha)":d, "Dose Range":f"{max(0,d-12)}–{d+12} kg/ha", "Reason":"Low phosphorus", "Nutrient":"Phosphorus", "Condition":"Low"})
    if K < 20:
        d = max(25, round((20-K)/0.60/25)*25)
        recs.append({"Fertilizer":"MOP (0-0-60)",   "NPK":"0-0-60",  "Dosage (kg/ha)":d, "Dose Range":f"{max(0,d-12)}–{d+12} kg/ha", "Reason":"Low potassium", "Nutrient":"Potassium", "Condition":"Low"})
    if not recs:
        recs.append({"Fertilizer":"NPK 17-17-17", "NPK":"17-17-17", "Dosage (kg/ha)":50, "Dose Range":"38–62 kg/ha", "Reason":"Balanced maintenance", "Nutrient":"—", "Condition":"Balanced"})
    return pd.DataFrame(recs)

def demo_yield(crop, N, P, K, T, R, pH):
    seed = int(abs(hash(crop)) % 1000 + N * 7 + P * 13 + K * 17 + T * 3 + R * 0.1 + pH * 100) % (2**31)
    rng  = np.random.default_rng(seed)
    base = YIELD_BASELINE.get(crop, 3000)
    return round(base * rng.uniform(0.85, 1.15), 1)

# ═══════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
#  PAGE 1: LOGIN GATE  →  PAGE 2: MAIN APP (Predict / History / Compare)
# ═══════════════════════════════════════════════
# Only gate on login when the backend is actually reachable — otherwise
# there's no account system to log into, and the dashboard below works
# fine as a local, session-only calculator (as it always has).
_needs_login = _backend_online() and not _is_logged_in() and not st.session_state.get("guest_mode")
if _needs_login:
    render_login_page()
    st.stop()

render_page_topbar()
render_top_bar()

if "page" not in st.session_state:
    st.session_state.page = "predict"

_NAV_PAGES = {"predict": "Dashboard", "history": "History", "compare": "Compare"}
with st.sidebar:
    st.markdown("""
    <div class="brand-row">
        <span class="brand-mark"></span>
        <span><span class="brand-name">AgriSmart</span><span class="brand-sub">field companion</span></span>
    </div>
    <p class="side-label">Workspace</p>
    """, unsafe_allow_html=True)
    st.radio(
        "Section",
        options=list(_NAV_PAGES.keys()),
        format_func=lambda key: _NAV_PAGES[key],
        horizontal=False,
        key="page",
        label_visibility="collapsed",
    )
    st.markdown("""
    <div class="side-note">
        <div class="side-note-head"><span class="side-note-ico"></span><b>Decision record</b></div>
        Save your runs to History to compare seasons side by side — the same
        record the mobile app shows.
    </div>
    """, unsafe_allow_html=True)

if st.session_state.page == "history":
    render_history_page()
    chat_launcher(st.session_state.get("current_report") or {})
    st.stop()

if st.session_state.page == "compare":
    render_compare_page()
    chat_launcher(st.session_state.get("current_report") or {})
    st.stop()

# ── Otherwise: the Dashboard page ──────────────────────
_dash_user = (st.session_state.get("auth_user") or {}) if _is_logged_in() else {}
_dash_name = html.escape(
    _display_name(_dash_user.get("full_name") or _dash_user.get("username")) or "Guest"
)
st.markdown(
    f'<p class="page-eyebrow" style="margin-bottom:4px">Field intelligence, made practical</p>'
    f'<h2 style="margin:0 0 18px; font-size:1.85rem; color:var(--primary) !important">'
    f"Welcome, {_dash_name}</h2>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════
#  INPUT FORM
# ═══════════════════════════════════════════════
left_col, right_col = st.columns([1.08, 0.92], gap="large")
with left_col:
    with st.container(border=True):
        st.markdown("""
        <div class="card-head">
            <div><p class="card-title">Crop decision desk</p>
            <p class="card-sub">Authority starts with the field sample — enter your readings below for a crop
            recommendation, soil check, fertilizer plan and yield estimate.</p></div>
            <span class="mono-label card-tag">Live workflow</span>
        </div>
        """, unsafe_allow_html=True)
        r1a, r1b = st.columns(2)
        with r1a: N  = st.slider("Nitrogen (N) kg/ha",   0,    150,   58)
        with r1b: P  = st.slider("Phosphorus (P) kg/ha", 0,    150,   43)
        r2a, r2b = st.columns(2)
        with r2a: K  = st.slider("Potassium (K) kg/ha",  0,    150,   37)
        with r2b: pH = st.slider("Soil pH",              4.0,  9.0,   6.4, 0.1)
        r3a, r3b = st.columns(2)
        with r3a: T  = st.slider("Temperature °C",       5.0,  50.0,  26.5, 0.5)
        with r3b: R  = st.slider("Rainfall mm",          0.0,  2000.0, 820.0, 10.0)
        crop_choice = st.selectbox("Target Crop (fertilizer & yield)", ALL_CROPS, index=0)
        run_clicked = st.button("Run analysis  →", use_container_width=True, key="run_btn")

# The right-hand panel is a placeholder until an analysis has run; once results
# exist it is overwritten below with the decision card.
result_slot = right_col.empty()

# Persist "an analysis has been run" across reruns triggered by other widgets
# (e.g. opening the chat) — a plain st.button() only returns True for the one
# rerun it was clicked in, so without this the results would vanish back to
# the placeholder any time something else on the page is clicked.
if "analysis_run" not in st.session_state:
    st.session_state.analysis_run = False
if run_clicked:
    st.session_state.analysis_run = True
    # Freeze the readings at the moment of the click: results below are computed
    # from this snapshot, so moving a slider afterwards changes nothing until
    # Run analysis is pressed again.
    st.session_state.analysis_inputs = dict(
        N=N, P=P, K=K, pH=pH, T=T, R=R, crop_choice=crop_choice,
    )
    # New analysis → new "save to field record" form (keys below are per analysis)
    st.session_state.analysis_id = st.session_state.get("analysis_id", 0) + 1

# ═══════════════════════════════════════════════
#  PLACEHOLDER UNTIL RUN
# ═══════════════════════════════════════════════
if not st.session_state.analysis_run:
    result_slot.markdown("""
    <div class="empty-panel">
        <div>
            <span class="empty-ico"></span>
            <h2>The best decision is rooted in your soil.</h2>
            <p>Adjust the readings and click <b>Run analysis</b> — your recommendation will appear here,
            with the reasoning signals kept visible.</p>
        </div>
        <div class="empty-foot"><span class="topbar-dot gold"></span>No decision on file yet</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

_live_inputs = dict(N=N, P=P, K=K, pH=pH, T=T, R=R, crop_choice=crop_choice)
if "analysis_inputs" not in st.session_state:
    st.session_state.analysis_inputs = dict(_live_inputs)
if "analysis_id" not in st.session_state:
    st.session_state.analysis_id = 1
_a = st.session_state.analysis_inputs
N, P, K, pH, T, R = _a["N"], _a["P"], _a["K"], _a["pH"], _a["T"], _a["R"]
crop_choice = _a["crop_choice"]
if _live_inputs != _a:
    st.caption("✏️ Readings changed — press **Run analysis** to update the results below.")

if run_clicked:
    with st.spinner("🌱 Analysing soil conditions and running predictions..."):
        import time; time.sleep(0.8)

# ═══════════════════════════════════════════════
#  COMPUTE ALL RESULTS
# ═══════════════════════════════════════════════
# Crop probabilities
if mods["crop_model"] is not None:
    try:
        inp   = np.array([[N, P, K, T, 0, pH, R]])
        probs = mods["crop_model"].predict_proba(inp)[0]
        top5_idx = np.argsort(probs)[::-1][:5]
        top5  = [(mods["crop_model"].classes_[i], round(probs[i]*100,1)) for i in top5_idx]
    except Exception:
        top5 = demo_crops(N, P, K, T, R, pH)
else:
    top5 = demo_crops(N, P, K, T, R, pH)

# Soil
soil_dict = {"Nitrogen": N, "Phosphorus": P, "Potassium": K, "pH": pH}
if mods["compute_nutrient_gap"]:
    try:
        gap_result = mods["compute_nutrient_gap"](crop_choice, soil_dict)
        rows = []
        for nutrient, info in gap_result.items():
            rows.append({
                "Nutrient": nutrient,
                "Value":    round(info["current"], 2),
                "Range":    f"~{info['ideal']}",
                "Gap":      abs(info["gap"]),
                "Status":   info["status"],
            })
        df_soil = pd.DataFrame(rows)
    except Exception:
        df_soil = demo_soil(N, P, K, pH)
else:
    df_soil = demo_soil(N, P, K, pH)

# Fertilizer
fert_result = None
if mods["recommend_fertilizer"]:
    try:
        fert_result = mods["recommend_fertilizer"](crop_choice, soil_dict)
        fert_rows = []
        for rec in fert_result.get("generic_recs", []):
            nutrient  = rec["nutrient"]
            condition = rec["condition"]
            gap_info  = fert_result["gap_analysis"].get(nutrient, {})
            gap_amt   = abs(gap_info.get("gap", 0))

            if condition == "Low":
                nutrient_pct = {"Nitrogen": 0.46, "Phosphorus": 0.46, "Potassium": 0.60}.get(nutrient, 0.46)
                raw_dose = gap_amt / nutrient_pct if gap_amt > 0 else 50
                rounded  = max(25, round(raw_dose / 25) * 25)
                dosage   = rounded
                dose_range = f"{max(0, rounded - 12)}–{rounded + 12} kg/ha"
            else:
                dosage     = 0
                dose_range = "—"

            fert_rows.append({
                "Fertilizer":     rec["fertilizer"],
                "NPK":            rec["npk_ratio"],
                "Dosage (kg/ha)": dosage,
                "Dose Range":     dose_range,
                "Reason":         rec["reason"],
                "Nutrient":       nutrient,
                "Condition":      condition,
            })
        if not fert_rows:
            cp = fert_result.get("crop_primary")
            if cp:
                fert_rows.append({
                    "Fertilizer":    cp["fertilizer"],
                    "NPK":           "—",
                    "Dosage (kg/ha)": 50,
                    "Dose Range":    "38–62 kg/ha",
                    "Reason":        cp["note"],
                    "Nutrient":      "—",
                    "Condition":     "Balanced",
                })
            else:
                fert_rows.append({
                    "Fertilizer":    "NPK 17-17-17",
                    "NPK":           "17-17-17",
                    "Dosage (kg/ha)": 50,
                    "Dose Range":    "38–62 kg/ha",
                    "Reason":        "Soil balanced — maintenance dose",
                    "Nutrient":      "—",
                    "Condition":     "Balanced",
                })
        df_fert = pd.DataFrame(fert_rows)
    except Exception:
        fert_result = None
        df_fert = demo_fert(crop_choice, N, P, K)
else:
    df_fert = demo_fert(crop_choice, N, P, K)

# Yield
if mods["predict_yield"]:
    try:    predicted = mods["predict_yield"](crop_choice, N, P, K, T, R, pH)
    except: predicted = demo_yield(crop_choice, N, P, K, T, R, pH)
else:
    predicted = demo_yield(crop_choice, N, P, K, T, R, pH)

top_crop, top_prob = top5[0]
top_conf_label = "High Match" if top_prob >= 35 else "Moderate Match" if top_prob >= 22 else "Low Match"
avg_yield  = YIELD_BASELINE.get(crop_choice, 3000)
diff_pct   = round((predicted - avg_yield) / avg_yield * 100, 1)
opt_count  = int((df_soil["Status"] == "Optimal").sum())
need_count = len(df_soil) - opt_count

yield_lo_tha = round(predicted * 0.88 / 1000, 2)
yield_hi_tha = round(predicted * 1.12 / 1000, 2)

if need_count == 0:
    soil_kpi = "All Optimal"
elif need_count == 1:
    soil_kpi = "1 imbalance detected"
else:
    soil_kpi = f"{need_count} imbalances detected"

crop_mismatch = (top_crop != crop_choice)

result_slot.markdown(f"""
<div class="res-card">
    <div class="res-top">
        <div class="res-row">
            <span class="mono-label res-eyebrow">Decision returned · {crop_choice}</span>
            <span class="res-pill">Predicted</span>
        </div>
        <div class="res-main">
            <div>
                <p class="res-label">Best fit for this soil</p>
                <h2 class="res-crop">{top_crop}</h2>
                <p class="res-sub">{top_conf_label} · estimated {yield_lo_tha}–{yield_hi_tha} t/ha for {crop_choice}</p>
            </div>
            <div class="res-conf"><span>{top_prob:.0f}</span><i>%</i><small>match score</small></div>
        </div>
    </div>
    <div class="res-grid">
        <div><small>Soil pH</small><b>{pH:.1f}</b></div>
        <div><small>Rainfall</small><b>{R:g} mm</b></div>
        <div><small>Temperature</small><b>{T:.1f}°C</b></div>
        <div><small>Soil health</small><b>{soil_kpi}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  SAVE TO FIELD RECORD  (label optional · crop grown REQUIRED)
# ═══════════════════════════════════════════════
_aid = st.session_state.analysis_id
_saved_info = st.session_state.get("saved_runs", {}).get(_aid)
with st.container(border=True):
    st.markdown("""
    <div class="card-head">
        <div><p class="card-title">Save to field record</p>
        <p class="card-sub">Tell us which crop you finally grew. Rotation alerts are based on what was
        actually grown, so this is required.</p></div>
        <span class="mono-label card-tag">Field record</span>
    </div>
    """, unsafe_allow_html=True)
    if _saved_info:
        st.success(f"Saved — {_saved_info['grown']} recorded"
                   f"{' for “' + _saved_info['label'] + '”' if _saved_info['label'] else ''}. "
                   "See the History section for past runs.")
    else:
        sv_a, sv_b = st.columns(2)
        with sv_a:
            save_label = st.text_input(
                "Label (optional)", key=f"save_label_{_aid}", placeholder="e.g. North field",
                help="Runs with the same label are treated as one field when checking crop rotation.",
            ).strip()
        with sv_b:
            grown_crop = st.selectbox(
                "Crop you finally grew *", ALL_CROPS, index=None, key=f"grown_crop_{_aid}",
                placeholder="Select the crop you grew",
            )
        if grown_crop is None:
            st.caption("Choose the crop you grew to enable saving.")
        if st.button("💾 Save to history", key=f"save_btn_{_aid}", disabled=grown_crop is None,
                     use_container_width=True):
            if not grown_crop:  # belt and braces — the button is disabled without it
                st.error("Please select the crop you grew.")
            else:
                where = _save_run(
                    save_label, crop_choice, grown_crop, top_crop, predicted,
                    dict(nitrogen=N, phosphorus=P, potassium=K, ph=pH, temperature=T, rainfall=R),
                )
                st.session_state.setdefault("saved_runs", {})[_aid] = {
                    "label": save_label, "grown": grown_crop, "where": where,
                }
                st.rerun()

if _saved_info:
    _rotation = _current_rotation_advice(_saved_info["label"])
    if _rotation:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        _render_rotation_banner(_rotation)
st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  KPI STRIP
# ═══════════════════════════════════════════════
k1, k2, k3, k4 = st.columns(4)
k1.metric("🌱 Top Crop",        top_crop,                   top_conf_label)
k2.metric("🪱 Soil Health",     soil_kpi)
k3.metric("🧪 Fertilizers",     f"{len(df_fert[df_fert['Dosage (kg/ha)']>0])} to apply")
k4.metric("📈 Est. Yield",      f"{yield_lo_tha}–{yield_hi_tha} t/ha", f"{diff_pct:+.1f}% vs avg")

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  ROW 1 — Crop Recommendation  |  Soil Analysis
# ═══════════════════════════════════════════════
col_crop, col_soil = st.columns(2, gap="large")

# ── Crop Recommendation ──────────────────────
with col_crop:
    st.markdown('<div class="section-header">🌱 Crop Recommendation</div>', unsafe_allow_html=True)

    def conf_label(p):
        if p >= 35:   return ("High Match",     "#244F3B")
        elif p >= 22: return ("Moderate Match", "#8A6414")
        else:         return ("Low Match",       "#B9483D")

    top_label, top_label_color = conf_label(top_prob)

    st.markdown(f"""
    <div style='background:#EEE8D9; border:1px solid #D3CDB8; border-radius:12px;
                padding:18px 22px; margin-bottom:16px; display:flex; align-items:center; gap:16px'>
        <div style='font-size:2.4rem'>🌿</div>
        <div>
            <div style='font-size:0.72rem; color:#4D5D54; text-transform:uppercase;
                        letter-spacing:1.5px; font-weight:600'>Best Match</div>
            <div style='font-family:"Playfair Display",serif; font-size:1.6rem;
                        font-weight:600; color:#213329'>{top_crop}</div>
            <div style='font-size:0.82rem; color:{top_label_color}; font-weight:600'>{top_label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    crops_  = [c for c, _ in top5]
    probs_  = [p for _, p in top5]
    # FIX: shorter labels to prevent overflow
    labels_ = [f"{p}%" for p in probs_]
    colors_ = ["#244F3B" if i == 0 else "#D3CDB8" for i in range(len(top5))]

    fig_cr = go.Figure(go.Bar(
        y=crops_,
        x=probs_,
        orientation="h",
        marker_color=colors_,
        # FIX: text inside bars, white text for contrast
        text=labels_,
        textposition="inside",
        textfont=dict(color="#FFFFFF", size=12, family="Manrope"),
        insidetextanchor="middle",
    ))
    fig_cr.update_layout(
        **PL,
        height=220,
        # FIX: fixed axis range so bars never clip text
        xaxis=dict(
            title="Match score (%)",
            range=[0, 100],
            tickfont=TICK_FONT,
            title_font=TITLE_FONT,
            gridcolor="#DCD8CC",
        ),
        yaxis=dict(
            autorange="reversed",
            # FIX: force dark color for crop name labels
            tickfont=dict(color="#213329", size=12, family="Manrope"),
            title_font=TITLE_FONT,
        ),
    )
    st.plotly_chart(fig_cr, use_container_width=True)

    rc1, rc2, rc3 = st.columns(3)
    for col, (icon, label, val) in zip(
        [rc1, rc2, rc3],
        [("💧","Rainfall",f"{R:.0f} mm"), ("⚗️","pH",f"{pH:.1f}"), ("🌡️","Temp.",f"{T:.1f} °C")]
    ):
        col.markdown(f"""
        <div style='background:#fff; border:1px solid #DCD8CC; border-radius:10px;
                    padding:12px; text-align:center'>
            <div style='font-size:1.2rem'>{icon}</div>
            <div style='font-size:0.72rem; color:#4D5D54; font-weight:600'>{label}</div>
            <div style='font-weight:600; font-size:1rem; color:#213329'>{val}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Soil Analysis ────────────────────────────
with col_soil:
    st.markdown('<div class="section-header">🪱 Soil Analysis</div>', unsafe_allow_html=True)

    IDEAL_RANGES = {
        "Jowar":     {"Nitrogen":(44,65),   "Phosphorus":(32,42), "Potassium":(31,42), "pH":(6.5,7.1)},
        "Groundnut": {"Nitrogen":(19,40),   "Phosphorus":(36,47), "Potassium":(22,33), "pH":(6.2,6.8)},
        "Cotton":    {"Nitrogen":(107,128), "Phosphorus":(51,62), "Potassium":(55,66), "pH":(6.7,7.3)},
        "Sugarcane": {"Nitrogen":(121,142), "Phosphorus":(65,76), "Potassium":(109,119),"pH":(6.6,7.2)},
        "Wheat":     {"Nitrogen":(81,102),  "Phosphorus":(48,58), "Potassium":(44,55), "pH":(6.4,7.0)},
    }
    ideals = IDEAL_RANGES.get(crop_choice, {
        "Nitrogen":(40,100), "Phosphorus":(25,80), "Potassium":(20,70), "pH":(5.5,7.5)
    })

    fig_g = make_subplots(rows=2, cols=2, specs=[[{"type":"indicator"}]*2]*2)
    gauge_params = [
        ("Nitrogen",   N,  0,   150),
        ("Phosphorus", P,  0,   150),
        ("Potassium",  K,  0,   150),
        ("pH",         pH, 4.0, 9.0),
    ]
    for (name, val, lo, hi), (r, c) in zip(gauge_params, [(1,1),(1,2),(2,1),(2,2)]):
        ideal_lo, ideal_hi = ideals[name]
        fig_g.add_trace(go.Indicator(
            mode="gauge+number",
            value=val,
            title={"text": name, "font": {"size": 11, "color": "#213329", "family": "Manrope"}},
            number={"font": {"color": "#213329", "size": 16, "family": "Manrope"}},
            gauge={
                "axis": {
                    "range": [lo, hi],
                    "tickfont": {"size": 8, "color": "#213329"},
                },
                "bar":  {"color": "#244F3B", "thickness": 0.25},
                "bgcolor": "#FCFAF5",
                "borderwidth": 0,
                "steps": [
                    {"range": [lo,       ideal_lo],  "color": "#F8E6E3"},
                    {"range": [ideal_lo, ideal_hi],  "color": "#DCE9DF"},
                    {"range": [ideal_hi, hi],         "color": "#FBF1D6"},
                ],
                "threshold": {
                    "line": {"color": "#244F3B", "width": 2},
                    "thickness": 0.8,
                    "value": (ideal_lo + ideal_hi) / 2,
                },
            },
        ), row=r, col=c)
    fig_g.update_layout(**PL, height=280)
    st.plotly_chart(fig_g, use_container_width=True)

    st.markdown("""
    <div style='display:flex; gap:16px; font-size:0.75rem; color:#4D5D54;
                font-weight:500; margin-top:-8px; margin-bottom:4px'>
        <span><span style='display:inline-block;width:10px;height:10px;border-radius:2px;
              background:#F8E6E3;border:1px solid #B9483D;margin-right:4px'></span>Below optimal</span>
        <span><span style='display:inline-block;width:10px;height:10px;border-radius:2px;
              background:#DCE9DF;border:1px solid #244F3B;margin-right:4px'></span>Optimal range</span>
        <span><span style='display:inline-block;width:10px;height:10px;border-radius:2px;
              background:#FBF1D6;border:1px solid #8A6414;margin-right:4px'></span>Above optimal</span>
    </div>
    """, unsafe_allow_html=True)

    badge_map = {"Optimal":"ok", "Low":"low", "High":"high"}
    msg_map   = lambda row: {
        "Low":     f"⬆ +{row['Gap']} needed",
        "High":    f"⬇ {row['Gap']} above optimal",
        "Optimal": "Within optimal range",
    }[row["Status"]]

    for _, row in df_soil.iterrows():
        st.markdown(f"""
        <div style='display:flex; justify-content:space-between; align-items:center;
                    background:#fff; border:1px solid #DCD8CC; border-radius:8px;
                    padding:10px 14px; margin-bottom:6px'>
            <div>
                <span style='font-weight:600; color:#213329'>{row["Nutrient"]}</span>
                <span style='font-size:0.75rem; color:#4D5D54; margin-left:8px;
                             font-weight:500'>{msg_map(row)}</span>
            </div>
            <div style='display:flex; align-items:center; gap:10px'>
                <span style='font-weight:600; color:#213329'>{row["Value"]}</span>
                <span class='{badge_map[row["Status"]]}'>{row["Status"]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<hr style='margin:28px 0'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  ROW 2 — Fertilizer  |  Yield Prediction
# ═══════════════════════════════════════════════
col_fert, col_yield = st.columns(2, gap="large")

# ── Fertilizer ───────────────────────────────
with col_fert:
    st.markdown(f'<div class="section-header">🧪 Fertilizer — {crop_choice}</div>', unsafe_allow_html=True)

    PRIMARY = {
        "Cotton":    ("DAP", "Preferred basal for Cotton in Black Soil"),
        "Groundnut": ("Chelated Micronutrient", "Micronutrient support alongside NPK"),
        "Jowar":     ("10:26:26 NPK", "High P+K supports grain and stem development"),
        "Sugarcane": ("MOP", "Sugarcane is K-hungry — standard choice"),
        "Wheat":     ("19:19:19 NPK", "Balanced NPK suits Wheat's equal N/P/K demand"),
    }
    if crop_choice in PRIMARY:
        pf, pnote = PRIMARY[crop_choice]
        st.markdown(f"""
        <div style='background:#E6EFE9; border-left:3px solid #244F3B; border-radius:6px;
                    padding:8px 12px; margin-bottom:10px; font-size:0.82rem; color:#213329'>
            <b>Primary fertilizer:</b> {pf} &nbsp;·&nbsp;
            <span style='color:#4D5D54; font-weight:500'>{pnote}</span>
        </div>
        """, unsafe_allow_html=True)

    for _, row in df_fert.iterrows():
        is_skip      = row["Dosage (kg/ha)"] == 0
        dose_display = "—" if is_skip else row.get("Dose Range", f"{row['Dosage (kg/ha)']} kg/ha")
        dosage_color = "#B9483D" if is_skip else "#213329"
        st.markdown(f"""
        <div style='background:#fff; border:1px solid #DCD8CC; border-radius:8px;
                    padding:10px 14px; margin-bottom:7px'>
            <div style='display:flex; justify-content:space-between; align-items:center'>
                <div>
                    <div style='font-weight:600; color:#213329; font-size:0.9rem'>{row["Fertilizer"]}</div>
                    <div style='font-size:0.73rem; color:#4D5D54; margin-top:2px;
                                font-weight:500'>{row["Reason"]}</div>
                </div>
                <div style='text-align:right'>
                    <div style='font-family:"Playfair Display",serif; font-size:1.05rem;
                                font-weight:600; color:{dosage_color}'>{dose_display}</div>
                    <div style='font-size:0.72rem; color:#4D5D54; font-weight:500'>NPK {row["NPK"]}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    df_fert_chart = df_fert[df_fert["Dosage (kg/ha)"] > 0]
    all_skip = not df_fert.empty and df_fert_chart.empty

    if df_fert.empty:
        st.markdown("""
        <div style='background:#E6EFE9; border:1px solid #8DB39B; border-radius:10px;
                    padding:20px; text-align:center; color:#244F3B; font-size:0.85rem;
                    font-weight:500'>
            ✅ Soil is perfectly balanced — no fertilizer application needed this season.
        </div>
        """, unsafe_allow_html=True)
    elif all_skip:
        st.markdown("""
        <div style='background:#FBF1D6; border:1px solid #8A6414; border-radius:10px;
                    padding:20px; text-align:center; color:#6E4F0B; font-size:0.85rem;
                    font-weight:500'>
            ⚠️ Some nutrients exceed optimal levels — skip those fertilizers this season.
            No additional application required.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Shorten names: "Urea (46-0-0)" → "Urea", keep "Hydrated Lime — Ca(OH)₂" short too
        df_fert_chart = df_fert_chart.copy()
        df_fert_chart["Fert_Short"] = (
            df_fert_chart["Fertilizer"]
            .str.split("(").str[0]          # drop parenthetical NPK codes
            .str.split("—").str[0]          # shorten "Hydrated Lime — Ca(OH)₂"
            .str.strip()
        )

        # Build one trace per fertilizer so each gets its own legend entry + color
        npk_vals    = df_fert_chart["NPK"].tolist()
        fert_shorts = df_fert_chart["Fert_Short"].tolist()
        dosages     = df_fert_chart["Dosage (kg/ha)"].tolist()

        fig_f = go.Figure()
        for i, (fname, npk, dose) in enumerate(zip(fert_shorts, npk_vals, dosages)):
            fig_f.add_trace(go.Bar(
                x=[fname],
                y=[dose],
                name=f"NPK {npk}",
                marker_color=EARTHY[i % len(EARTHY)],
                text=[str(dose)],
                textposition="outside",
                textfont=dict(color="#213329", size=11, family="Manrope"),
            ))

        PL_fert = {k: v for k, v in PL.items() if k != "margin"}
        fig_f.update_layout(
            **PL_fert,
            height=270,
            barmode="group",
            showlegend=True,
            margin=dict(l=16, r=16, t=36, b=90),
            legend=dict(
                orientation="h",
                y=-0.42,                                    # below x-axis labels
                x=0,
                font=dict(size=10, color="#213329", family="Manrope"),
                # FIX: legend title color explicitly set
                title=dict(
                    text="NPK",
                    font=dict(size=10, color="#213329", family="Manrope"),
                ),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
            ),
        )
        fig_f.update_xaxes(
            tickfont=dict(color="#213329", size=11, family="Manrope"),
            title_text="",          # remove "Fertilizer" label — redundant with card headers above
            tickangle=0,            # keep upright; names are short now
        )
        fig_f.update_yaxes(
            title_text="Dosage (kg/ha)",
            tickfont=dict(color="#213329", size=11, family="Manrope"),
            title_font=dict(color="#213329", size=12, family="Manrope"),
            gridcolor="#DCD8CC",
            # give headroom above tallest bar so "outside" text isn't clipped
            range=[0, max(dosages) * 1.35],
        )
        st.plotly_chart(fig_f, use_container_width=True)

# ── Yield Prediction ─────────────────────────
with col_yield:
    st.markdown('<div class="section-header">📈 Yield Prediction</div>', unsafe_allow_html=True)

    pred_tha    = round(predicted / 1000, 2)
    avg_tha     = round(avg_yield  / 1000, 2)
    max_tha     = round(avg_tha * 1.5, 2)

    fig_y = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pred_tha,
        delta={
            "reference": avg_tha,
            "suffix": " t/ha",
            "increasing": {"color": "#244F3B"},
            "decreasing": {"color": "#B9483D"},
            "font": {"color": "#213329"},
        },
        number={"suffix": " t/ha", "font": {"size": 24, "color": "#213329", "family": "Manrope"}},
        title={"text": f"{crop_choice}  ({int(predicted):,} kg/ha)",
               "font": {"size": 12, "color": "#213329", "family": "Manrope"}},
        gauge={
            "axis": {
                "range": [0, max_tha],
                "tickfont": {"size": 9, "color": "#213329"},
            },
            "bar":  {"color": "#244F3B"},
            "bgcolor": "#FCFAF5",
            "borderwidth": 0,
            "steps": [
                {"range": [0,           avg_tha * 0.6], "color": "#F8E6E3"},
                {"range": [avg_tha*0.6, avg_tha],       "color": "#FBF1D6"},
                {"range": [avg_tha,     max_tha],        "color": "#DCE9DF"},
            ],
            "threshold": {
                "line": {"color": "#244F3B", "width": 2},
                "thickness": 0.8,
                "value": avg_tha,
            },
        },
    ))
    fig_y.update_layout(**PL, height=260)
    st.plotly_chart(fig_y, use_container_width=True)

    if diff_pct >= 5:
        bg,border,label,msg = "#DCE9DF","#244F3B","🟢 Above Average","Excellent conditions — strong harvest expected."
    elif diff_pct >= -5:
        bg,border,label,msg = "#DCD8CC","#8A6414","🟡 Near Average","Close to regional average; minor tweaks can help."
    else:
        bg,border,label,msg = "#E6CBC6","#B9483D","🔴 Below Average","Review soil health and fertilizer recommendations."

    st.markdown(f"""
    <div style='background:{bg}; border-left:3px solid {border}; border-radius:8px;
                padding:12px 16px; margin-bottom:16px'>
        <b style='color:#213329'>{label}</b> &nbsp;·&nbsp;
        <span style='font-size:0.84rem; color:#4D5D54; font-weight:500'>{msg}</span>
    </div>
    """, unsafe_allow_html=True)

    comp_crops  = [crop_choice] + [c for c in ALL_CROPS if c != crop_choice]
    seed_base   = int(N * 7 + P * 13 + K * 17 + T * 3 + R * 0.1 + pH * 100) % (2**31)
    comp_yields_kgha = [predicted]
    for i, c in enumerate(comp_crops[1:]):
        rng_c = np.random.default_rng(seed_base + i + abs(hash(c)) % 1000)
        comp_yields_kgha.append(YIELD_BASELINE.get(c, 3000) * rng_c.uniform(0.9, 1.1))

    comp_yields_tha = [round(y / 1000, 2) for y in comp_yields_kgha]
    bar_colors = ["#244F3B" if c == crop_choice else "#D3CDB8" for c in comp_crops]
    bar_texts  = [f"{y} t/ha" for y in comp_yields_tha]

    fig_c = go.Figure(go.Bar(
        x=comp_crops,
        y=comp_yields_tha,
        marker_color=bar_colors,
        text=bar_texts,
        textposition="outside",
        textfont=dict(color="#213329", size=11),
    ))
    fig_c.update_layout(
        **PL,
        height=240,
        yaxis=dict(
            title="Yield (t/ha)",
            range=[0, max(comp_yields_tha) * 1.25],
            tickfont=TICK_FONT,
            title_font=TITLE_FONT,
            gridcolor="#DCD8CC",
        ),
        xaxis=dict(
            tickfont=TICK_FONT,
            title_font=TITLE_FONT,
        ),
    )
    st.plotly_chart(fig_c, use_container_width=True)

# ═══════════════════════════════════════════════
#  CHAT ASSISTANT — hybrid intent classifier + Gemini fallback, floating icon
# ═══════════════════════════════════════════════

# Assemble the current analysis into the shape both intent_responder.py and
# gemini_chat.build_report_context expect (mirrors the report_*.json shape
# the original pipeline.py produced).
soil_adjustment_ctx = {
    row["Nutrient"]: {
        "current": row["Value"],
        "ideal": row["Range"],
        "status": row["Status"],
    }
    for _, row in df_soil.iterrows()
}

fert_generic_recs_ctx = [
    {
        "fertilizer": row["Fertilizer"],
        "npk_ratio": row["NPK"],
        "nutrient": row.get("Nutrient", "—"),
        "condition": row.get("Condition", "Low" if row["Dosage (kg/ha)"] > 0 else "Balanced"),
        "reason": row["Reason"],
        "dose_note": row["Dose Range"] if row["Dosage (kg/ha)"] > 0 else "no application needed",
    }
    for _, row in df_fert.iterrows()
]

crop_primary_ctx = None
if crop_choice in PRIMARY:
    _pf, _pnote = PRIMARY[crop_choice]
    crop_primary_ctx = {"fertilizer": _pf, "note": _pnote}

fert_action_needed = (
    fert_result.get("action_needed") if fert_result else bool((df_fert["Dosage (kg/ha)"] > 0).any())
)
fert_gap_analysis_ctx = fert_result.get("gap_analysis", {}) if fert_result else soil_adjustment_ctx

current_report = {
    "chosen_crop": crop_choice,
    "top_5_crops": [{"crop": c, "probability": p / 100} for c, p in top5],
    "soil_input": {**soil_dict, "Temperature": T, "Rainfall": R},
    "soil_adjustment": soil_adjustment_ctx,
    "fertilizer": {
        "gap_analysis": fert_gap_analysis_ctx,
        "generic_recs": fert_generic_recs_ctx,
        "crop_primary": crop_primary_ctx,
        "action_needed": fert_action_needed,
    },
    "yield_prediction": {
        "predicted_yield_kg_ha": predicted,
        "avg_yield_kg_ha": avg_yield,
        "diff_pct": diff_pct,
        "interpretation": f"{label} — {msg}",
    },
}

# Make this run available to the 📜 History and ⚖️ Compare pages (they run
# on separate reruns, after the nav switch above), and to mobile-parity
# "save this run" there.
st.session_state["current_report"] = current_report
st.session_state["last_soil_values"] = dict(
    nitrogen=N, phosphorus=P, potassium=K, ph=pH, temperature=T, rainfall=R
)
st.session_state["last_crop_choice"] = crop_choice

st.markdown("<hr style='margin:28px 0'>", unsafe_allow_html=True)
if _backend_online() and _is_logged_in():
    st.caption("💾 Use **Save to field record** above to keep this run in your account — History shows past runs and rotation alerts.")
else:
    st.caption("💾 Use **Save to field record** above to keep this run on this computer. Log in with the backend running to keep it in your account.")

chat_launcher(current_report)

# ── Footer ───────────────────────────────────
st.markdown("""
<hr style='margin:32px 0 12px'>
<div style='text-align:center; color:#4D5D54; font-size:0.74rem;
            padding-bottom:20px; font-weight:500'>
    AgriSmart DSS · Final Year Project · Built with Streamlit 🌾
</div>
""", unsafe_allow_html=True)