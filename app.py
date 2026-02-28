import os
import time
from pathlib import Path
from datetime import datetime
import streamlit as st

# Backend imports (do not modify backend logic)
from core.llm import call_llm
from utils.topic_manager import create_topic, add_message, load_topics, save_topics, ensure_topic_store
from utils.memory_manager import append_message as update_memory, ensure_memory_store

# Paths
STUDENT_PROMPT_FILE = Path("agents/student.txt")
TEACHER_PROMPT_FILE = Path("agents/teacher.txt")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Page config
st.set_page_config(page_title="Student–Teacher AI", page_icon="🎓", layout="wide")

# Ensure data stores exist before any access (important for fresh deployments)
ensure_topic_store()
ensure_memory_store()

# Session defaults
for key, default in {
    "topic_id": None,
    "topic": "",
    "max_turns": 6,
    "turn_count": 0,
    "stop_requested": False,
    "auto_run": False,
    "status": "idle",
    "manual_mode": False,
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
    return


def save_uploaded_pdf(uploaded_file):
    return None


def list_uploaded_pdfs():
    return []


def reset_session_state():
    st.session_state.topic_id = None
    st.session_state.topic = ""
    st.session_state.max_turns = 6
    st.session_state.turn_count = 0
    st.session_state.stop_requested = False
    st.session_state.auto_run = False
    st.session_state.status = "idle"
    st.session_state.manual_mode = False


def start_topic(topic: str, max_turns: int, manual_mode: bool = False):
    ensure_topic_store()
    ensure_memory_store()
    st.session_state.topic_id = create_topic(topic, max_turns)
    st.session_state.topic = topic
    st.session_state.max_turns = max_turns
    st.session_state.turn_count = 0
    st.session_state.stop_requested = False
    st.session_state.auto_run = not manual_mode
    st.session_state.status = "running"
    st.session_state.manual_mode = manual_mode

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
    return


def handle_voice_input():
    return None


def handle_tts(text: str):
    return


# Layout
st.title("🎓 Student–Teacher AI (Streamlit)")
st.caption("Chat between a curious student and a helpful teacher. Backend untouched.")

# UI copy blocks
st.markdown(
    """
    Start a topic, set a turn limit, and watch the student/teacher exchange. JSON logs stay hidden and are only touched after you launch a topic.
    """
)


def status_badge(label: str, color: str):
    st.markdown(
        f"<div style='display:inline-block;padding:6px 10px;border-radius:12px;background:{color};color:white;font-weight:600;'>"
        f"{label}</div>",
        unsafe_allow_html=True,
    )

apply_theme(False)

# Main inputs
with st.container():
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1.2])
    with col1:
        topic_text = st.text_input("Topic", value=st.session_state.topic)
    with col2:
        max_turns = st.number_input("Max turns", min_value=2, max_value=20, value=int(st.session_state.max_turns))
    with col3:
        st.write(" ")
        start_clicked = st.button("Start Topic", use_container_width=True)
        stop_clicked = st.button("Stop Topic", use_container_width=True)
    with col4:
        manual_mode = st.toggle("Manual steps", value=st.session_state.manual_mode, help="If on, turns advance only when you click Step once.")
        st.session_state.manual_mode = manual_mode
        step_clicked = st.button("Step once", use_container_width=True, disabled=not st.session_state.topic_id)
        resume_clicked = st.button("Resume auto", use_container_width=True, disabled=not st.session_state.topic_id)
        reset_clicked = st.button("Reset session", use_container_width=True)

    if start_clicked:
        if not topic_text.strip():
            st.warning("Enter a topic first.")
        else:
            start_topic(topic_text.strip(), int(max_turns), manual_mode=st.session_state.manual_mode)
            st.rerun()

    if stop_clicked:
        st.session_state.stop_requested = True
        st.session_state.auto_run = False
        st.session_state.status = "stopped"

    if reset_clicked:
        reset_session_state()
        st.rerun()

    if step_clicked and st.session_state.topic_id:
        st.session_state.auto_run = False
        st.session_state.stop_requested = False
        process_next_turn()
        st.rerun()

    if resume_clicked and st.session_state.topic_id:
        st.session_state.stop_requested = False
        st.session_state.auto_run = True
        st.session_state.status = "running"
        st.rerun()

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
        mode = "Manual" if st.session_state.manual_mode else "Auto"
        st.markdown(f"**Active topic:** {topic_label} &nbsp;|&nbsp; **Mode:** {mode}")

st.info("Tip: keep max turns modest (6-10) for quicker iterations. You can stop or step manually anytime.")

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

st.info("Run with: streamlit run app.py")
