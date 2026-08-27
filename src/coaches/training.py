from .. import db
from .. import gemini


def run():
    e1rm_rows = db.fetch_all(
        "WITH daily_best AS ("
        "  SELECT e.pattern, w.session_date, MAX(ws.e1rm) AS best_e1rm"
        "  FROM workout_sets ws"
        "  JOIN workouts w ON w.id = ws.workout_id"
        "  JOIN exercises e ON e.id = ws.exercise_id"
        "  WHERE w.session_date >= (CURRENT_DATE - interval '28 days')"
        "  GROUP BY e.pattern, w.session_date"
        ") SELECT pattern, session_date, best_e1rm FROM daily_best "
        "ORDER BY pattern, session_date"
    )

    session_counts = db.fetch_all(
        "SELECT e.pattern, COUNT(DISTINCT w.session_date) AS sessions "
        "FROM workout_sets ws"
        " JOIN workouts w ON w.id = ws.workout_id"
        " JOIN exercises e ON e.id = ws.exercise_id"
        " WHERE w.session_date >= (CURRENT_DATE - interval '28 days')"
        " GROUP BY e.pattern"
    )

    weight_rows = db.fetch_all(
        "SELECT recorded_at::date AS day, weight_lbs FROM body_metrics "
        "WHERE recorded_at >= (CURRENT_DATE - interval '28 days') ORDER BY recorded_at"
    )

    latest = db.fetch_all(
        "WITH latest AS ("
        "  SELECT e.pattern, w.session_date, ws.weight_lbs, ws.reps, ws.rir, ws.e1rm,"
        "    ROW_NUMBER() OVER (PARTITION BY e.pattern ORDER BY w.session_date DESC, "
        "      ws.set_index DESC) AS rn"
        "  FROM workout_sets ws"
        "  JOIN workouts w ON w.id = ws.workout_id"
        "  JOIN exercises e ON e.id = ws.exercise_id"
        ") SELECT pattern, session_date, weight_lbs, reps, rir, e1rm "
        "FROM latest WHERE rn = 1"
    )

    chat_row = db.fetch_one(
        "SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1"
    )
    if not chat_row:
        return None
    chat_id = chat_row["chat_id"]

    has_history = any(r["sessions"] >= 3 for r in session_counts)
    if not has_history:
        return chat_id, "Not enough training history yet to prescribe. Keep logging sessions."

    prompt = f"""You are a training coach. Analyze this athlete's data and prescribe today's session.

Best e1rm per day (last 28 days):
{[dict(r) for r in e1rm_rows]}

Sessions per pattern:
{[dict(r) for r in session_counts]}

Bodyweight last 28 days:
{[dict(r) for r in weight_rows]}

Latest session per pattern:
{[dict(r) for r in latest]}

INSTRUCTIONS:
1. For each pattern, take the single highest e1rm per session_date, then fit a least-squares line over 28 days. Ignore patterns with fewer than 3 sessions.
2. Stalled = 28-day slope zero or negative. Rising = positive.
3. Before prescribing for a stall, check bodyweight slope. If falling > 0.3 lbs/week, say stall is a food problem and prescribe nothing for that pattern.
4. Otherwise:
   - stalled + bodyweight steady: hold load, add 1 rep to every set
   - rising + last set rir >= 2: +5 lbs compound, +2.5 lbs isolation
   - rising + rir 0/1/null: repeat last session exactly
   - falling > 2%/week: drop load 10%, repeat for 2 sessions
   Carry sets and reps from most recent session of that pattern.
5. If no workouts for longer than median gap, send a nudge.

FORMAT:
[pattern] - [movement], [sets] x [reps] at [load] lbs (e1RM [val], [up/down] [x] on last week, RIR [val]).

RULES:
- No motivation. Just the prescription.
- Order by most recent session first, then alphabetically.
- Keep under 1000 characters."""

    return chat_id, gemini.generate(prompt)
