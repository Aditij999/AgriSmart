"""Browser-based voice input/output for the Streamlit website.

Mirrors the mobile app's on-device speech recognition (`speech_to_text`) and
text-to-speech (`flutter_tts`, see `mobile/lib/voice/`): everything here runs
in the visitor's own browser via the standard Web Speech API. No audio is
ever sent to the server — only text that was already going to cross the
browser/Python boundary anyway (the typed-or-dictated question, and the
assistant's already-computed reply) does.

`voice_input_component()` is a real bidirectional Streamlit component (see
`web_voice_component/index.html`): the in-browser recognizer hands its
transcript straight back to Python via the normal widget-value mechanism, on
the current page, in place — no page navigation, so it works the same way
regardless of whether it's sitting inside an `st.dialog` or anywhere else.
This replaces an earlier version that wrote the transcript into the page URL
and did a full reload to get it back into Python; that reload closed any
open `st.dialog` before the transcript could be read, which is why voice
input silently went nowhere. The caller drops the returned text into the
same editable field the person types into — dictation fills the box, it
doesn't auto-send — exactly like `mobile/lib/screens/chat_screen.dart`'s
`_onSpeechResult`, so the two clients behave the same way.

`to_plain_text()` mirrors `backend/routers/chat.py`'s `_plain_text` so the
website reads answers aloud the same way the mobile app's `answer_plain`
field does.
"""

import json
import os
import re

import streamlit as st
import streamlit.components.v1 as components

from chatbot.language import detect_language  # noqa: E402  (same en/hi/mr detection the chatbot uses)

_DECORATION = re.compile(r"[•\-\*]{1,2}\s|[\U0001F300-\U0001FAFF\u2600-\u27BF]")

_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "web_voice_component")
_voice_component = components.declare_component("voice_input", path=_COMPONENT_DIR)


def to_plain_text(answer: str) -> str:
    """Strips markdown bullets/emoji so text-to-speech reads cleanly.

    Kept in sync with backend/routers/chat.py's `_plain_text`, which builds
    the mobile app's `answer_plain` field.
    """
    stripped = _DECORATION.sub("", answer)
    return re.sub(r"\s+", " ", stripped).strip()


def voice_input_component(key: str):
    """Renders a mic button; returns freshly dictated text once it arrives,
    else None. Speech recognition runs entirely in the browser; the
    transcript comes straight back through the component's normal return
    value (see `web_voice_component/index.html`) — no audio, and nothing
    routed through the URL or a page reload.

    A component keeps re-returning its last value on every later rerun (a
    button click elsewhere, typing in another field, ...), not just once —
    so a nonce sent alongside the text is what tells a genuinely fresh
    dictation apart from the same result being reported again.
    """
    raw = _voice_component(key=key, default=None)
    if not raw:
        return None
    seen_key = f"_voice_seen_{key}"
    if st.session_state.get(seen_key) == raw.get("nonce"):
        return None
    st.session_state[seen_key] = raw.get("nonce")
    return raw.get("text")


# BCP-47 tag handed to the browser's speech engine for each reply language.
_SPEECH_LANG_TAG = {"en": "en-US", "hi": "hi-IN", "mr": "mr-IN"}


def speak_button(text: str, key: str):
    """Renders a Listen/Stop toggle that reads `text` aloud via the browser's
    built-in speech synthesis — the web equivalent of the app's speaker icon
    under each assistant reply. Nothing is sent to any server for this.

    The reply language (en/hi/mr) is detected from the text itself with the
    chatbot's own `detect_language`, and passed to the browser so it uses a
    matching voice. Without a language the browser falls back to its default
    English voice, which stays silent on Devanagari text — that is why Marathi
    answers used to produce no sound. Marathi falls back to a Hindi voice when
    the browser has no Marathi one (both are written in Devanagari), and the
    button says so plainly if neither is installed instead of failing silently.
    """
    text = (text or "").strip()
    if not text:
        return
    lang = detect_language(text, fallback="en")
    lang_tag = _SPEECH_LANG_TAG.get(lang, "en-US")
    # json.dumps gives a valid JS string literal for any text (quotes, newlines,
    # backticks, "${"); "</" is split so the text can never close the <script> tag.
    js_text = json.dumps(text).replace("</", "<\\/")
    components.html(
        f"""
        <button id="speak-btn-{key}" type="button"
          style="border:none;background:none;color:#8C6D3F;font-size:12px;
                 cursor:pointer;padding:2px 0;">🔊 Listen</button>
        <script>
        (function() {{
          const btn = document.getElementById("speak-btn-{key}");
          const text = {js_text};
          const langTag = {json.dumps(lang_tag)};
          const synth = (window.parent && window.parent.speechSynthesis) || window.speechSynthesis;
          if (!synth) {{
            btn.disabled = true;
            btn.textContent = "Text-to-speech unavailable";
            return;
          }}
          const LISTEN = "🔊 Listen", STOP = "⏹ Stop";
          let runId = 0;

          // Best installed voice for the language: exact tag, then same base
          // language, then (Marathi only) Hindi — also Devanagari script.
          function pickVoice() {{
            const voices = synth.getVoices() || [];
            const base = langTag.split("-")[0].toLowerCase();
            const wanted = [langTag.toLowerCase(), base];
            if (base === "mr") wanted.push("hi-in", "hi");
            for (const w of wanted) {{
              const hit = voices.find(function(v) {{
                const l = (v.lang || "").toLowerCase().replace("_", "-");
                return l === w || l.split("-")[0] === w;
              }});
              if (hit) return hit;
            }}
            return null;
          }}

          // Long utterances get cut off by some browsers, so speak sentence by
          // sentence (English "." "!" "?", Devanagari danda "।").
          function chunks(t) {{
            const parts = t.match(/[^.!?।॥\\n]+[.!?।॥]*/g) || [t];
            const out = [];
            let cur = "";
            parts.forEach(function(p) {{
              p = p.trim();
              if (!p) return;
              if ((cur + " " + p).length > 180 && cur) {{ out.push(cur); cur = p; }}
              else {{ cur = cur ? cur + " " + p : p; }}
            }});
            if (cur) out.push(cur);
            return out;
          }}

          function reset() {{
            btn.textContent = LISTEN;
            btn.dataset.speaking = "0";
          }}

          btn.addEventListener("click", function() {{
            if (btn.dataset.speaking === "1") {{
              runId++;
              synth.cancel();
              reset();
              return;
            }}
            runId++;
            const myRun = runId;
            synth.cancel();

            // English keeps the browser's default voice and a single utterance,
            // exactly as before; the language-aware path is for Hindi/Marathi.
            const isEnglish = langTag === "en-US";
            const voice = isEnglish ? null : pickVoice();
            if (!voice && !isEnglish && (synth.getVoices() || []).length > 0) {{
              btn.textContent = "No " + (langTag.startsWith("mr") ? "Marathi/Hindi" : "Hindi") +
                " voice installed in this browser";
              btn.dataset.speaking = "0";
              return;
            }}

            const list = isEnglish ? [text] : chunks(text);
            list.forEach(function(piece, i) {{
              const utter = new SpeechSynthesisUtterance(piece);
              if (!isEnglish) {{
                utter.lang = voice ? voice.lang : langTag;
                if (voice) utter.voice = voice;
              }}
              utter.rate = 0.95;
              const done = function() {{
                if (myRun !== runId) return;       // cancelled / superseded
                if (i === list.length - 1) reset();
              }};
              utter.onend = done;
              utter.onerror = function() {{ if (myRun === runId) reset(); }};
              synth.speak(utter);
            }});
            btn.textContent = STOP;
            btn.dataset.speaking = "1";
          }});

          // Browsers load their voice list asynchronously; nothing to do on
          // change because the voice is looked up fresh on every click.
        }})();
        </script>
        """,
        height=28,
    )
