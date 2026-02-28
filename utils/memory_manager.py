import json
from datetime import datetime

MEMORY_FILE = "data/shared_memory.json"

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def append_message(role, message):
    mem = load_memory()
    turn_number = len(mem["conversation"]) + 1
    
    mem["conversation"].append({
        "role": role,
        "message": message,
        "turn": turn_number,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    
    save_memory(mem)

def get_turn_count():
    return len(load_memory()["conversation"])