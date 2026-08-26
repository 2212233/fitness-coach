import os
import requests

API_KEY = os.environ["GROQ_API_KEY"]
URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe(audio_bytes, filename="voice.ogg"):
    r = requests.post(
        URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"file": (filename, audio_bytes, "audio/ogg")},
        data={"model": "whisper-large-v3-turbo", "response_format": "json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("text", "")
