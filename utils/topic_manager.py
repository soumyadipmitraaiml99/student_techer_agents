import json
import uuid
from datetime import datetime
from pathlib import Path

TOPIC_FILE = Path("data/topics_memory.json")
DEFAULT_DATA = {"topics": []}


def _ensure_topic_file():
    TOPIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TOPIC_FILE.exists():
        TOPIC_FILE.write_text(json.dumps(DEFAULT_DATA, indent=4), encoding="utf-8")


def load_topics():
    _ensure_topic_file()
    try:
        return json.loads(TOPIC_FILE.read_text(encoding="utf-8"))
    except Exception:
        TOPIC_FILE.write_text(json.dumps(DEFAULT_DATA, indent=4), encoding="utf-8")
        return DEFAULT_DATA.copy()


def save_topics(data):
    _ensure_topic_file()
    TOPIC_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def create_topic(topic_text, max_turns):
    topic_id = str(uuid.uuid4())
    data = load_topics()
    data["topics"].append({
        "topic_id": topic_id,
        "topic": topic_text,
        "max_turns": max_turns,
        "messages": [],
    })
    save_topics(data)
    return topic_id


def add_message(topic_id, role, message):
    data = load_topics()
    for topic in data["topics"]:
        if topic["topic_id"] == topic_id:
            topic["messages"].append({
                "role": role,
                "message": message,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
    save_topics(data)