from . import db
from . import telegram

HELP_TEXT = (
    "How to use me — just chat or use commands.\n\n"
    "FOOD\n"
    "  Say what you ate:  *2 eggs, 30g whey*\n"
    "  Include amounts in grams or servings.\n\n"
    "TRAINING\n"
    "  Log sets:  *bench 225 by 8 at 2 RIR*\n"
    "  or just:  *i did 50 pushups*\n\n"
    "SUPPLEMENTS\n"
    "  Say it:  *took 5g creatine*\n\n"
    "BODY METRICS (commands)\n"
    "  /weight 185   — bodyweight lbs\n"
    "  /bodyfat 20   — body fat %\n"
    "  /waist 34     — waist inches\n"
    "  /hr 55        — resting heart rate\n\n"
    "GOALS (commands)\n"
    "  /goal calories 1800\n"
    "  /goal protein 160\n"
    "  /goal weight_rate -1    — lbs/week (negative = cutting)\n"
    "  /goals                  — show current goals\n\n"
    "OTHER\n"
    "  /help — this message"
)

COMMANDS = [
    ("help", "Show this message"),
    ("weight", "Log bodyweight in lbs, e.g. /weight 185"),
    ("bodyfat", "Log body fat per cent, e.g. /bodyfat 20"),
    ("waist", "Log waist inches, e.g. /waist 34"),
    ("hr", "Log resting heart rate, e.g. /hr 55"),
    ("goal", "Set a goal, e.g. /goal calories 1800"),
    ("goals", "Show current goals"),
]

_GOAL_UNITS = {
    "calories": "kcal",
    "protein": "g",
    "carbs": "g",
    "fat": "g",
    "water": "ml",
    "weight_rate": "lbs/week",
}

_GOAL_NEGATIVE_ONLY = {"weight_rate"}


def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


_BODY_LABELS = {
    "weight_lbs": "bodyweight",
    "bodyfat_pct": "body fat",
    "waist_in": "waist",
    "resting_hr": "resting heart rate",
}


def _write_body(records):
    for field, value in records:
        db.execute(
            f"INSERT INTO body_metrics ({field}, recorded_at) VALUES (%s, now())",
            (value,),
        )
    parts = []
    for field, value in records:
        label = _BODY_LABELS.get(field, field)
        if field == "bodyfat_pct":
            parts.append(f"{label} {value:g}%")
        elif field == "resting_hr":
            parts.append(f"{label} {value:g} bpm")
        else:
            parts.append(f"{label} {value:g}")
    return "Logged " + ", ".join(parts) + "."


def _set_goal(label, value):
    unit = _GOAL_UNITS.get(label)
    if unit is None:
        return "Unknown goal. Try one of: calories, protein, carbs, fat, water, weight_rate."
    if label in _GOAL_NEGATIVE_ONLY and value >= 0:
        return "weight_rate must be negative for cutting (e.g. -1), positive for bulking."
    if label not in _GOAL_NEGATIVE_ONLY and value <= 0:
        return f"{label} must be a positive number."
    db.execute(
        "UPDATE daily_plan SET target_value = %s, active = true "
        "WHERE item_type = 'goal' AND label = %s",
        (value, label),
    )
    db.execute(
        "INSERT INTO daily_plan (item_type, label, target_value, target_unit, active) "
        "SELECT 'goal', %s, %s, %s, true "
        "WHERE NOT EXISTS (SELECT 1 FROM daily_plan WHERE item_type='goal' AND label=%s)",
        (label, value, unit, label),
    )
    return f"Goal set: {label} = {value:g} {unit}."


def handle(chat_id, text):
    text = (text or "").strip()
    if not text.startswith("/"):
        return None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    replies = []
    for ln in lines:
        parts = ln.split()
        if not parts:
            continue
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            replies.append(HELP_TEXT)
        elif cmd == "/weight":
            v = _float(args[0]) if args else None
            if v is None or v <= 0:
                replies.append("Usage: /weight 185")
            else:
                _write_body([("weight_lbs", v)])
                replies.append(f"Logged bodyweight: {v:g} lbs.")
        elif cmd == "/bodyfat":
            v = _float(args[0]) if args else None
            if v is None or v <= 0:
                replies.append("Usage: /bodyfat 20")
            else:
                _write_body([("bodyfat_pct", v)])
                replies.append(f"Logged body fat: {v:g} %.")
        elif cmd == "/waist":
            v = _float(args[0]) if args else None
            if v is None or v <= 0:
                replies.append("Usage: /waist 34")
            else:
                _write_body([("waist_in", v)])
                replies.append(f"Logged waist: {v:g} in.")
        elif cmd == "/hr":
            v = _float(args[0]) if args else None
            if v is None or v <= 0:
                replies.append("Usage: /hr 55")
            else:
                _write_body([("resting_hr", v)])
                replies.append(f"Logged resting heart rate: {v:g}.")
        elif cmd == "/goal":
            if len(args) < 2:
                replies.append("Usage: /goal <calories|protein|carbs|fat|water|weight_rate> <value>")
            else:
                v = _float(args[1])
                if v is None:
                    replies.append("Use a number, e.g. /goal calories 1800")
                else:
                    replies.append(_set_goal(args[0].lower(), v))
        elif cmd == "/goals":
            rows = db.fetch_all(
                "SELECT label, target_value, target_unit FROM daily_plan "
                "WHERE item_type = 'goal' AND active = true ORDER BY label"
            )
            if not rows:
                replies.append("No goals set yet. Try /goal calories 1800")
            else:
                lines_out = ["Current goals:"]
                for r in rows:
                    unit = r["target_unit"] or _GOAL_UNITS.get(r["label"], "")
                    lines_out.append(f"  {r['label']}: {r['target_value']:g} {unit}")
                replies.append("\n".join(lines_out))
        else:
            replies.append(f"Unknown command: {cmd}. Use /help.")

    return "\n".join(replies)


def register_menu():
    return telegram.set_my_commands([
        {"command": c, "description": d} for c, d in COMMANDS
    ])