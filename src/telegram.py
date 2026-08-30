import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_updates(offset=None, timeout=0):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("result", [])


def send_message(chat_id, text, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    r = requests.post(f"{BASE}/sendMessage", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def set_my_commands(commands):
    r = requests.post(
        f"{BASE}/setMyCommands",
        json={"commands": commands},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def download_file(file_id):
    info = requests.get(f"{BASE}/getFile", params={"file_id": file_id}, timeout=15)
    info.raise_for_status()
    path = info.json()["result"]["file_path"]
    data = requests.get(
        f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}", timeout=30
    )
    data.raise_for_status()
    return data.content
