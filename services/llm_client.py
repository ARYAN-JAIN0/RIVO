import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"

def call_llm(prompt: str, json_mode: bool = False) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        return body.get("response", "")
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"❌ LLM Call Failed: {e}")
        return ""
