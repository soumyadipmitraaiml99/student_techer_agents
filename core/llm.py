import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_llm(messages, model="llama-3.3-70b-versatile"):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    response = requests.post(BASE_URL, json=payload, headers=headers)
    data = response.json()
    print(data)  # Debug: print the full response
    
    return data["choices"][0]["message"]["content"]