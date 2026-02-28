import customtkinter as ctk
from core.llm import call_llm
from utils.topic_manager import create_topic, add_message
from utils.memory_manager import save_memory

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Student–Teacher AI")
        self.geometry("700x600")

        # Topic input
        self.topic_entry = ctk.CTkEntry(self, placeholder_text="Enter topic...")
        self.topic_entry.pack(pady=10, fill="x", padx=20)

        # Max turns
        self.turn_entry = ctk.CTkEntry(self, placeholder_text="Max Turns (e.g., 6)")
        self.turn_entry.pack(pady=10, fill="x", padx=20)

        # Start button
        self.start_btn = ctk.CTkButton(self, text="Start Topic", command=self.start_conversation)
        self.start_btn.pack(pady=10)

        # Stop button

        self.stop_btn = ctk.CTkButton(self, text="🛑Stop Conversation", command=self.stop_conversation)
        self.stop_btn.pack(pady=5)

        # Chat display box
        self.chat_box = ctk.CTkTextbox(self, width=650, height=400)
        self.chat_box.pack(pady=10, padx=20)

        self.topic_id = None
        self.turn_count = 0
        self.max_turns = 0
        self.stop_requested = False

    def safe_call(self, fn):
        try:
            fn()
        except Exception as exc:
            self.add_chat("System", f"Error: {exc}")

    def safe_after(self, delay_ms, fn):
        try:
            self.after(delay_ms, lambda: self.safe_call(fn))
        except Exception as exc:
            self.add_chat("System", f"Schedule error: {exc}")

    def end_conversation(self, message, auto_close=True):
        self.stop_requested = True
        self.add_chat("System", message)
        if auto_close:
            self.safe_after(300, self.destroy)

    def reset_state(self):
        self.topic_id = None
        self.turn_count = 0
        self.max_turns = 0
        self.stop_requested = False
        self.chat_box.delete("1.0", "end")
        save_memory({"conversation": []})

    def add_chat(self, role, msg):
        self.chat_box.insert("end", f"{role}: {msg}\n\n")
        self.chat_box.see("end")

    def start_conversation(self):
        topic = self.topic_entry.get().strip()
        if not topic:
            self.add_chat("System", "Please enter a topic.")
            return

        turn_value = self.turn_entry.get().strip()
        try:
            parsed_turns = int(turn_value)
            if parsed_turns <= 0:
                raise ValueError
        except Exception:
            self.add_chat("System", "Please enter a positive integer for Max Turns.")
            return

        self.reset_state()
        self.max_turns = parsed_turns

        self.topic_id = create_topic(topic, self.max_turns)

        # First student question
        student_msg = call_llm([
            {"role": "system", "content": open("agents/student.txt").read()},
            {"role": "user", "content": f"Ask your first question about: {topic}"}
        ])

        add_message(self.topic_id, "student", student_msg)
        self.add_chat("👦 Student", student_msg)

        self.turn_count += 1
        self.safe_after(500, self.teacher_turn)

    def teacher_turn(self):
        if self.stop_requested:
            return


        if self.turn_count >= self.max_turns:
            self.end_conversation("Topic completed.")
            return

        teacher_msg = call_llm([
            {"role": "system", "content": open("agents/teacher.txt", "r", encoding="utf-8").read()},
            {"role": "user", "content": f"Student asked: {self.get_last_student()}"}
        ])

        add_message(self.topic_id, "teacher", teacher_msg)
        self.add_chat("👨‍🏫 Teacher", teacher_msg)

        self.turn_count += 1
        self.safe_after(500, self.student_turn)

    def student_turn(self):

        if self.stop_requested:
            return
        
        if self.turn_count >= self.max_turns:
            self.end_conversation("Topic completed.")
            return

        student_msg = call_llm([
            {"role": "system", "content": open("agents/student.txt", "r", encoding="utf-8").read()},
            {"role": "user", "content": f"Teacher replied: {self.get_last_teacher()}"}
        ])

        add_message(self.topic_id, "student", student_msg)
        self.add_chat("👦 Student", student_msg)

        self.turn_count += 1
        self.safe_after(500, self.teacher_turn)

    def get_last_student(self):
        data = open("data/topics_memory.json", "r", encoding="utf-8").read()
        # quick parse
        import json
        topics = json.loads(data)
        for t in topics["topics"]:
            if t["topic_id"] == self.topic_id:
                for m in reversed(t["messages"]):
                    if m["role"] == "student":
                        return m["message"]

    def get_last_teacher(self):
        import json
        with open("data/topics_memory.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for t in data["topics"]:
            if t["topic_id"] == self.topic_id:
                for m in reversed(t["messages"]):
                    if m["role"] == "teacher":
                        return m["message"]
                    
    def stop_conversation(self):
        if self.topic_id is not None:
            self.end_conversation("Conversation stopped by user.")


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()