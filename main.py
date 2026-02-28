from core.llm import call_llm
from utils.memory_manager import load_memory, append_message, get_turn_count
from gui.app import ChatApp

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()

MAX_TURNS = 10  # total turns (student + teacher)
STUDENT_PROMPT_FILE = "agents/student.txt"
TEACHER_PROMPT_FILE = "agents/teacher.txt"

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_conversation(topic):
    student_role = read_file(STUDENT_PROMPT_FILE)
    teacher_role = read_file(TEACHER_PROMPT_FILE)

    # --- Student first question ---
    student_messages = [
        {"role": "system", "content": student_role},
        {"role": "user", "content": f"Ask a question about this topic: {topic}"}
    ]

    student_q = call_llm(student_messages)
    print("\n👦 Student:", student_q)
    append_message("student", student_q)

    # --- Main loop ---
    while get_turn_count() < MAX_TURNS:
        memory = load_memory()

        # Teacher responds
        teacher_messages = [
            {"role": "system", "content": teacher_role},
            {"role": "user", "content": memory["conversation"][-1]["message"]}
        ]

        teacher_answer = call_llm(teacher_messages)
        print("\n👨‍🏫 Teacher:", teacher_answer)
        append_message("teacher", teacher_answer)

        if get_turn_count() >= MAX_TURNS:
            break

        # Student follow-up
        student_follow_messages = [
            {"role": "system", "content": student_role},
            {"role": "user", "content": teacher_answer}
        ]

        student_follow = call_llm(student_follow_messages)
        print("\n👦 Student:", student_follow)
        append_message("student", student_follow)

# ---- RUN SYSTEM ----
topic = input("Enter a topic: ")
run_conversation(topic)