import os
import json
import requests

# Primary: Groq (free tier, generous limits)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


def _api_key():
    return os.environ["GROQ_API_KEY"]

PARSE_PROMPT = """You are a fitness data parser. Given a transcript of what someone said to their coach, extract structured data.

Transcript: {transcript}

Return ONLY valid JSON with this exact schema:
{{
  "foods": [{{"name": "string", "brand": "string", "quantity": number, "unit": "string"}}],
  "sets": [{{"exercise": "string", "weight_lbs": number, "reps": number, "rir": number|null}}],
  "supplements": [{{"name": "string", "quantity": number}}],
  "body": [{{"weight_lbs": number, "bodyfat_pct": number|null, "waist_in": number|null, "resting_hr": number|null}}],
  "mentioned_food": boolean,
  "mentioned_lifting": boolean
}}

Rules:
- Empty array where nothing was mentioned
- Never invent a number the user did not say
- Leave rir null if not mentioned
- quantity for foods is always in GRAMS, converted by you (e.g. "2 eggs" -> {{\"quantity\": 100, \"unit\": \"g\"}}, "30g whey" -> {{\"quantity\": 30, \"unit\": \"g\"}}, "a bowl of soup" -> {{\"quantity\": 250, \"unit\": \"g\"}})
- weight_lbs for body is bodyweight
- Return ONLY the JSON, no markdown, no explanation"""


def _chat(prompt, max_tokens=1024):
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    r = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_transcript(transcript):
    text = _chat(PARSE_PROMPT.format(transcript=transcript))
    cleaned = text.replace("```json\n", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "foods": [],
            "sets": [],
            "supplements": [],
            "body": [],
            "mentioned_food": False,
            "mentioned_lifting": False,
        }


def generate(prompt):
    return _chat(prompt, max_tokens=2048)
