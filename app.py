import os
import json
import time
import base64
from pathlib import Path
from datetime import datetime
import streamlit as st

# Backend imports (do not modify backend logic)
from core.llm import call_llm
from utils.topic_manager import create_topic, add_message, load_topics, save_topics
from utils.memory_manager import append_message as update_memory, load_memory

# Paths
STUDENT_PROMPT_FILE = Path("agents/student.txt")
TEACHER_PROMPT_FILE = Path("agents/teacher.txt")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Page config
st.set_page_config(page_title="Student–Teacher AI", page_icon="🎓", layout="wide")

# Session defaults
for key, default in {
    "topic_id": None,
    "topic": "",
    "max_turns": 6,
    "turn_count": 0,
    "stop_requested": False,
    "auto_run": False,
    "status": "idle",
    "selected_topic_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# Helpers
@st.cache_data(show_spinner=False)
def read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def get_last_student(topic_id: str):
    data = load_topics()
    for topic in data.get("topics", []):
        if topic.get("topic_id") == topic_id:
            for msg in reversed(topic.get("messages", [])):
                if msg.get("role") == "student":
                    return msg.get("message")
    return ""


def get_last_teacher(topic_id: str):
    data = load_topics()
    for topic in data.get("topics", []):
        if topic.get("topic_id") == topic_id:
            for msg in reversed(topic.get("messages", [])):
                if msg.get("role") == "teacher":
                    return msg.get("message")
    return ""


def delete_topic(topic_id: str):
    data = load_topics()
    data["topics"] = [t for t in data.get("topics", []) if t.get("topic_id") != topic_id]
    save_topics(data)


def load_topic_messages(topic_id: str):
    data = load_topics()
    for topic in data.get("topics", []):
        if topic.get("topic_id") == topic_id:
            return topic.get("messages", [])
    return []


def typing_animation(container, text: str, delay: float = 0.01):
    displayed = ""
    for ch in text:
        displayed += ch
        container.markdown(displayed)
        time.sleep(delay)


def render_chat(messages):
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("message", "")
        icon = "👦" if role == "student" else ("👨‍🏫" if role == "teacher" else "ℹ️")
        with st.container(border=True):
            st.markdown(f"**{icon} {role.title()}**  ")
            st.markdown(content)


def apply_theme(dark_mode: bool):
    if dark_mode:
        st.markdown(
            """
            <style>
            :root {
                --bg: #0f172a;
                --card: #111827;
                --text: #e5e7eb;
                --muted: #94a3b8;
                --accent: #22d3ee;
                --border: #1f2937;
            }
            .stApp { background-color: var(--bg); color: var(--text); }
            [data-testid="stSidebar"] { background-color: var(--card); color: var(--text); }
            div.block-container { color: var(--text); }
            .stContainer { background: var(--card); }
            .stButton>button, .stDownloadButton>button { background: var(--accent); color: #0b1220; border: none; }
            .stButton>button:hover, .stDownloadButton>button:hover { filter: brightness(0.92); }
            div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
                background: var(--card);
                color: var(--text);
                border-color: var(--border);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            :root {
                --bg: #f8fafc;
                --card: #ffffff;
                --text: #0f172a;
                --muted: #475569;
                --accent: #2563eb;
                --border: #e2e8f0;
            }
            .stApp { background-color: var(--bg); color: var(--text); }
            [data-testid="stSidebar"] { background-color: var(--card); color: var(--text); }
            div.block-container { color: var(--text); }
            .stContainer { background: var(--card); }
            .stButton>button, .stDownloadButton>button { background: var(--accent); color: #ffffff; border: none; }
            .stButton>button:hover, .stDownloadButton>button:hover { filter: brightness(0.96); }
            div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
                background: var(--card);
                color: var(--text);
                border-color: var(--border);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


def export_conversation_pdf(topic_id: str):
    try:
        from fpdf import FPDF
    except Exception:
        st.warning("Install fpdf to enable PDF export: pip install fpdf")
        return

    messages = load_topic_messages(topic_id)
    if not messages:
        st.info("No messages to export.")
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Conversation: {topic_id}", ln=True)
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("message", "")
        pdf.multi_cell(0, 10, txt=f"{role}: {content}")
        pdf.ln(2)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    b64 = base64.b64encode(pdf_bytes).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="conversation.pdf">Download PDF</a>'
    st.markdown(href, unsafe_allow_html=True)


def save_uploaded_pdf(uploaded_file):
    if uploaded_file is None:
        return None
    file_path = UPLOAD_DIR / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path


def list_uploaded_pdfs():
    return sorted([p.name for p in UPLOAD_DIR.glob("*.pdf")])


def start_topic(topic: str, max_turns: int):
    st.session_state.topic_id = create_topic(topic, max_turns)
    st.session_state.topic = topic
    st.session_state.max_turns = max_turns
    st.session_state.turn_count = 0
    st.session_state.stop_requested = False
    st.session_state.auto_run = True
    st.session_state.status = "running"

    student_prompt = read_prompt(STUDENT_PROMPT_FILE)
    student_msg = call_llm([
        {"role": "system", "content": student_prompt},
        {"role": "user", "content": f"Ask a question about this topic: {topic}"},
    ])
    add_message(st.session_state.topic_id, "student", student_msg)
    update_memory("student", student_msg)
    st.session_state.turn_count += 1


def process_next_turn():
    if st.session_state.stop_requested:
        st.session_state.auto_run = False
        st.session_state.status = "stopped"
        return

    if st.session_state.turn_count >= st.session_state.max_turns:
        st.session_state.auto_run = False
        st.session_state.status = "complete"
        return

    teacher_prompt = read_prompt(TEACHER_PROMPT_FILE)
    student_prompt = read_prompt(STUDENT_PROMPT_FILE)
    topic_id = st.session_state.topic_id

    # Teacher responds to last student
    teacher_msg = call_llm([
        {"role": "system", "content": teacher_prompt},
        {"role": "user", "content": get_last_student(topic_id)},
    ])
    add_message(topic_id, "teacher", teacher_msg)
    update_memory("teacher", teacher_msg)
    st.session_state.turn_count += 1

    if st.session_state.turn_count >= st.session_state.max_turns or st.session_state.stop_requested:
        st.session_state.auto_run = False
        st.session_state.status = "complete"
        return

    # Student follow-up
    student_msg = call_llm([
        {"role": "system", "content": student_prompt},
        {"role": "user", "content": teacher_msg},
    ])
    add_message(topic_id, "student", student_msg)
    update_memory("student", student_msg)
    st.session_state.turn_count += 1

    if st.session_state.turn_count >= st.session_state.max_turns:
        st.session_state.auto_run = False
        st.session_state.status = "complete"


def render_memory_viewer():
    mem = load_memory()
    with st.expander("Memory viewer", expanded=False):
        st.json(mem)


def handle_voice_input():
    st.markdown("### Optional voice input (Whisper)")
    audio_file = st.file_uploader("Upload audio (wav/mp3)", type=["wav", "mp3"], key="audio_upload")
    text_out = None
    if audio_file is not None:
        try:
            import whisper  # optional
            model = whisper.load_model("base")
            audio_path = Path("/tmp") / audio_file.name
            with open(audio_path, "wb") as f:
                f.write(audio_file.read())
            result = model.transcribe(str(audio_path))
            text_out = result.get("text", "")
            st.success("Transcription complete.")
        except Exception as exc:  # pragma: no cover - optional path
            st.warning(f"Whisper not available: {exc}")
    return text_out


def handle_tts(text: str):
    if not text:
        return
    try:
        import pyttsx3  # optional
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        st.success("Played TTS locally.")
    except Exception as exc:  # pragma: no cover - optional path
        st.warning(f"TTS not available: {exc}")


# Layout
st.title("🎓 Student–Teacher AI (Streamlit)")
st.caption("Chat between a curious student and a helpful teacher. Backend untouched.")

# UI copy blocks
st.markdown(
    """
    **What this does:** spins up a lightweight practice room where an AI student and teacher swap turns on your topic. Start a topic, let them iterate, and export the dialogue when done.

    **How to use:**
    - Pick a topic and max turns, then hit Start Topic.
    - Watch the live exchange; stop early if you need to.
    - View past topics or export the current one as PDF.
    """
)


def status_badge(label: str, color: str):
    st.markdown(
        f"<div style='display:inline-block;padding:6px 10px;border-radius:12px;background:{color};color:white;font-weight:600;'>"
        f"{label}</div>",
        unsafe_allow_html=True,
    )

# Sidebar
with st.sidebar:
    st.header("Controls")
    dark_mode = st.toggle("Dark mode", value=False)
    apply_theme(dark_mode)

    st.subheader("Topic history")
    st.caption("Re-open, review, or delete any previous topic thread. Select one to inspect or export.")
    topics_data = load_topics()
    topic_options = {t["topic"] + " (" + t["topic_id"][:8] + ")": t["topic_id"] for t in topics_data.get("topics", [])}
    selected_label = st.selectbox("Select topic", options=["<none>"] + list(topic_options.keys()))
    if selected_label != "<none>":
        st.session_state.selected_topic_id = topic_options[selected_label]
        if st.button("Delete selected topic"):
            delete_topic(st.session_state.selected_topic_id)
            st.session_state.selected_topic_id = None
            st.rerun()

    st.subheader("Upload PDFs (future RAG)")
    st.caption("Uploads are stored locally; future versions may use them for retrieval-augmented replies.")
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_upload")
    if uploaded_pdf:
        saved = save_uploaded_pdf(uploaded_pdf)
        if saved:
            st.success(f"Saved to {saved}")
            st.rerun()
    st.caption("Uploaded files:")
    for name in list_uploaded_pdfs():
        st.text(f"• {name}")

    st.divider()
    st.subheader("Export conversation")
    export_topic_id = st.session_state.selected_topic_id or st.session_state.topic_id
    if st.button("Export as PDF"):
        if export_topic_id:
            export_conversation_pdf(export_topic_id)
        else:
            st.info("Select or start a topic first.")

# Main inputs
with st.container():
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        topic_text = st.text_input("Topic", value=st.session_state.topic)
    with col2:
        max_turns = st.number_input("Max turns", min_value=2, max_value=20, value=int(st.session_state.max_turns))
    with col3:
        st.write(" ")
        start_clicked = st.button("Start Topic", use_container_width=True)
        stop_clicked = st.button("Stop Topic", use_container_width=True)

    if start_clicked:
        if not topic_text.strip():
            st.warning("Enter a topic first.")
        else:
            start_topic(topic_text.strip(), int(max_turns))
            st.rerun()

    if stop_clicked:
        st.session_state.stop_requested = True
        st.session_state.auto_run = False
        st.session_state.status = "stopped"

# Status and context strip
status_colors = {
    "idle": "#6c757d",
    "running": "#198754",
    "stopped": "#dc3545",
    "complete": "#0d6efd",
}

with st.container(border=True):
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        status_badge(f"Status: {st.session_state.status.title()}", status_colors.get(st.session_state.status, "#6c757d"))
    with c2:
        st.markdown(f"**Turn:** {st.session_state.turn_count}/{st.session_state.max_turns}")
    with c3:
        topic_label = st.session_state.topic or "—"
        st.markdown(f"**Active topic:** {topic_label}")

st.info("Tip: keep max turns modest (6-10) for quicker iterations. You can stop anytime; export stays available even after stopping.")

# Auto-run loop (one iteration per rerun)
if st.session_state.auto_run and st.session_state.topic_id:
    process_next_turn()
    if st.session_state.auto_run:
        st.rerun()

# Display current conversation
if st.session_state.topic_id:
    st.subheader(f"Live conversation (turn {st.session_state.turn_count}/{st.session_state.max_turns})")
    st.caption("Real-time exchange between student and teacher for the active topic.")
    msgs = load_topic_messages(st.session_state.topic_id)
    render_chat(msgs)

# Typing animation for the latest message
    if msgs:
        anim_spot = st.empty()
        typing_animation(anim_spot, msgs[-1]["message"][:400], delay=0.005)

# Past conversations view
if st.session_state.selected_topic_id and st.session_state.selected_topic_id != st.session_state.topic_id:
    st.subheader("Past conversation")
    st.caption("Selected topic from history; read-only view.")
    render_chat(load_topic_messages(st.session_state.selected_topic_id))

render_memory_viewer()

# Optional voice input/output
with st.expander("Voice options", expanded=False):
    st.caption("Optional transcription (Whisper) and text-to-speech. Both are local and optional.")
    voice_text = handle_voice_input()
    if voice_text:
        st.text_area("Transcribed text", value=voice_text, height=80)
    tts_text = st.text_input("Text to speak (TTS)")
    if st.button("Play TTS"):
        handle_tts(tts_text)

with st.expander("Quick tips", expanded=False):
    st.markdown(
        """
        - Start narrow: pick a focused topic so the exchange stays concise.
        - Raise turns if you want deeper follow-ups; lower turns for rapid checks.
        - Use topic history to compare how prompts evolve over time.
        - Export after a good run to keep a snapshot of the dialogue.
        """
    )

st.info("Run with: streamlit run app.py")
