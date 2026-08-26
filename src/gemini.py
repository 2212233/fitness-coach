import os
import json
import requests

API_KEY = os.environ["GEMINI_API_KEY"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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
- quantity for foods is in the unit the user said (e.g. 2 eggs, 30g whey)
- weight_lbs for body is bodyweight
- Return ONLY the JSON, no markdown, no explanation"""


def parse_transcript(transcript):
    payload = {
        "contents": [{"parts": [{"text": PARSE_PROMPT.format(transcript=transcript)}]}]
    }
    r = requests.post(
        URL,
        headers={"Content-Type": "application/json", "X-goog-api-key": API_KEY},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
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
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(
        URL,
        headers={"Content-Type": "application/json", "X-goog-api-key": API_KEY},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
