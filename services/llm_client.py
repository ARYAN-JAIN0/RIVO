import os
import time
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


def call_llm(prompt: str, json_mode: bool = False) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    if json_mode:
        payload["format"] = "json"

    last_error = None
    for attempt in range(1, LLM_MAX_RETRIES + 2):
        try:
            response = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=(10, LLM_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            body = response.json()
            return body.get("response", "")
        except (requests.exceptions.RequestException, ValueError) as e:
            last_error = e
            print(f"❌ LLM Call Failed (attempt {attempt}/{LLM_MAX_RETRIES + 1}): {e}")
            if attempt <= LLM_MAX_RETRIES:
                time.sleep(min(2 * attempt, 5))

    print(
        "⚠️ LLM unavailable after retries. "
        "Check that Ollama is running and model is pulled: "
        f"`ollama serve` and `ollama pull {MODEL_NAME}`."
    )
    if last_error:
        print(f"⚠️ Last LLM error: {last_error}")
    return ""
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        return body.get("response", "")
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"❌ LLM Call Failed: {e}")
        return ""
