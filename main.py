#!/usr/bin/env python3
"""
$8,250 Fitness Coach — CLI Entry Point

Usage:
  python main.py ingest          Poll Telegram, transcribe, save to messages
  python main.py parse           Parse pending messages, write DB rows
  python main.py nutrition       Run nightly nutrition coach
  python main.py training        Run nightly training coach
  python main.py head            Run weekly head coach
  python main.py coaches         Run all three coaches
  python main.py poll            Ingest + parse in a loop (for local use)
  python main.py register        Register the bot's /command menu
"""
import sys
import time

from src import db, telegram, groq, gemini, parser, commands
from src.coaches import nutrition, training, head


def ingest():
    updates = telegram.get_updates()
    if not updates:
        return 0

    count = 0
    for update in updates:
        update_id = update.get("update_id")
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        if not chat_id:
            continue

        text = msg.get("text")
        voice = msg.get("voice") or msg.get("document")
        kind = "text"
        transcript = text or ""
        raw_text = text

        if text and text.startswith("/"):
            reply = commands.handle(chat_id, text)
            if reply:
                telegram.send_message(chat_id, reply)
            else:
                telegram.send_message(chat_id, "Unknown command. Use /help.")
            continue

        if voice and voice.get("mime_type", "").startswith("audio/"):
            kind = "voice"
            try:
                audio = telegram.download_file(voice["file_id"])
                transcript = groq.transcribe(audio)
            except Exception as e:
                transcript = f"[transcription failed: {e}]"
                raw_text = None

        if not transcript and not raw_text:
            continue

        existing = db.fetch_one(
            "SELECT id FROM messages WHERE chat_id = %s AND transcript = %s AND kind = %s",
            (chat_id, transcript, kind),
        )
        if existing:
            continue

        db.execute(
            "INSERT INTO messages (source, chat_id, kind, raw_text, transcript, status) "
            "VALUES ('telegram', %s, %s, %s, %s, 'pending')",
            (chat_id, kind, raw_text, transcript),
        )
        telegram.send_message(chat_id, "Got it - logging now.")
        count += 1

    if updates:
        telegram.get_updates(offset=updates[-1]["update_id"] + 1)

    return count


def parse():
    rows = db.fetch_all(
        "SELECT * FROM messages WHERE status = 'pending' "
        "ORDER BY received_at LIMIT 10 FOR UPDATE SKIP LOCKED"
    )
    if not rows:
        return 0

    ids = [r["id"] for r in rows]
    db.execute(
        "UPDATE messages SET status = 'parsing' WHERE id = ANY(%s)", (ids,)
    )

    count = 0
    for msg in rows:
        transcript = msg["transcript"] or ""
        if not transcript.strip():
            db.execute(
                "UPDATE messages SET status = 'needs_review' WHERE id = %s",
                (msg["id"],),
            )
            continue

        try:
            parsed = gemini.parse_transcript(transcript)
            results, chat_id = parser.process_message(msg["id"], parsed)

            parts = []
            if results["foods"]:
                parts.append(f"{results['foods']} foods")
            if results["sets"]:
                parts.append(f"{results['sets']} sets")
            if results["supplements"]:
                parts.append(f"{results['supplements']} supplements")
            if results["body"]:
                parts.append(f"{results['body']} body metrics")

            if parts:
                telegram.send_message(chat_id, f"Logged {', '.join(parts)}.")
            else:
                telegram.send_message(
                    chat_id,
                    "Got your message but could not parse it. Please rephrase.",
                )
        except Exception as e:
            db.execute(
                "UPDATE messages SET status = 'needs_review' WHERE id = %s",
                (msg["id"],),
            )
            print(f"Parse error on message {msg['id']}: {e}", file=sys.stderr)

        count += 1

    return count


def run_coach(coach_module, name):
    try:
        result = coach_module.run()
        if result is None:
            print(f"{name}: no chat_id found, skipping")
            return False
        chat_id, text = result
        text = (text or "").strip()
        if not text:
            print(f"{name}: coach returned empty message, skipping send")
            return False
        if len(text) > 4000:
            text = text[:4000]
        telegram.send_message(chat_id, text)
        print(f"{name}: sent ({len(text)} chars)")
        return True
    except Exception as e:
        print(f"{name} error: {e}", file=sys.stderr)
        return False


def coaches():
    run_coach(nutrition, "nutrition")
    run_coach(training, "training")
    run_coach(head, "head")


def poll(interval=30):
    print(f"Polling every {interval}s. Press Ctrl+C to stop.")
    while True:
        try:
            n = ingest()
            if n:
                print(f"Ingested {n} messages")
            p = parse()
            if p:
                print(f"Parsed {p} messages")
        except Exception as e:
            print(f"Poll error: {e}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "ingest":
        n = ingest()
        print(f"Ingested {n} messages")
    elif cmd == "parse":
        n = parse()
        print(f"Parsed {n} messages")
    elif cmd == "nutrition":
        run_coach(nutrition, "nutrition")
    elif cmd == "training":
        run_coach(training, "training")
    elif cmd == "head":
        run_coach(head, "head")
    elif cmd == "coaches":
        coaches()
    elif cmd == "poll":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        poll(interval)
    elif cmd == "register":
        commands.register_menu()
        print("Bot command menu registered")
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
