import json
import uuid
from datetime import datetime

TOPIC_FILE = "data/topics_memory.json"

def load_topics():
    try:
        with open(TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"topics": []}

def save_topics(data):
    with open(TOPIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def create_topic(topic_text, max_turns):
    topic_id = str(uuid.uuid4())
    data = load_topics()
    data["topics"].append({
        "topic_id": topic_id,
        "topic": topic_text,
        "max_turns": max_turns,
        "messages": []
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
                "time": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    save_topics(data)