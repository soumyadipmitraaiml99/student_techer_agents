import json
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path("data/shared_memory.json")
DEFAULT_PAYLOAD = {"conversation": []}


def _ensure_memory_file():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(json.dumps(DEFAULT_PAYLOAD, indent=4), encoding="utf-8")


def _safe_load():
    _ensure_memory_file()
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        MEMORY_FILE.write_text(json.dumps(DEFAULT_PAYLOAD, indent=4), encoding="utf-8")
        return DEFAULT_PAYLOAD.copy()


def load_memory():
    return _safe_load()


def save_memory(data):
    _ensure_memory_file()
    MEMORY_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def append_message(role, message):
    mem = _safe_load()
    turn_number = len(mem["conversation"]) + 1

    mem["conversation"].append({
        "role": role,
        "message": message,
        "turn": turn_number,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    save_memory(mem)


def get_turn_count():
    return len(_safe_load()["conversation"])