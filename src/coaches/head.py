from .. import db
from .. import gemini


def run():
    monthly = db.fetch_all(
        "SELECT date_trunc('month', day)::date AS month, "
        "SUM(calories) AS total_cal, SUM(protein_g) AS total_protein, "
        "AVG(protein_per_lb) AS avg_protein_per_lb, AVG(weight_lbs) AS avg_weight "
        "FROM ("
        "  SELECT fl.consumed_at::date AS day, fl.calories, fl.protein_g,"
        "    fl.protein_g / NULLIF(bm.weight_lbs, 0) AS protein_per_lb,"
        "    bm.weight_lbs"
        "  FROM food_log fl"
        "  LEFT JOIN body_metrics bm ON bm.recorded_at::date = fl.consumed_at::date"
        "  WHERE fl.consumed_at >= (CURRENT_DATE - interval '90 days')"
        ") sub GROUP BY month ORDER BY month"
    )

    detail_14d = db.fetch_all(
        "SELECT 'food' AS source, fl.consumed_at::date AS day,"
        "  fl.calories, fl.protein_g, NULL AS e1rm, NULL AS exercise"
        " FROM food_log fl WHERE fl.consumed_at >= (CURRENT_DATE - interval '14 days')"
        " UNION ALL"
        " SELECT 'training', w.session_date, NULL, NULL, ws.e1rm, e.name"
        " FROM workout_sets ws"
        " JOIN workouts w ON w.id = ws.workout_id"
        " JOIN exercises e ON e.id = ws.exercise_id"
        " WHERE w.session_date >= (CURRENT_DATE - interval '14 days')"
        " UNION ALL"
        " SELECT 'body', bm.recorded_at::date, NULL, NULL, NULL, NULL"
        " FROM body_metrics bm WHERE bm.recorded_at >= (CURRENT_DATE - interval '14 days')"
        " ORDER BY day"
    )

    e1rm_trends = db.fetch_all(
        "WITH daily_best AS ("
        "  SELECT e.name AS exercise, e.pattern, w.session_date, MAX(ws.e1rm) AS best_e1rm"
        "  FROM workout_sets ws"
        "  JOIN workouts w ON w.id = ws.workout_id"
        "  JOIN exercises e ON e.id = ws.exercise_id"
        "  WHERE w.session_date >= (CURRENT_DATE - interval '90 days')"
        "  GROUP BY e.name, e.pattern, w.session_date"
        ") SELECT exercise, pattern, session_date, best_e1rm "
        "FROM daily_best ORDER BY exercise, session_date"
    )

    protein_per_lb = db.fetch_all(
        "SELECT fl.consumed_at::date AS day, SUM(fl.protein_g) AS total_protein,"
        "  (SELECT weight_lbs FROM body_metrics WHERE recorded_at <= fl.consumed_at"
        "   ORDER BY recorded_at DESC LIMIT 1) AS weight_lbs"
        " FROM food_log fl"
        " WHERE fl.consumed_at >= (CURRENT_DATE - interval '14 days')"
        " GROUP BY fl.consumed_at::date ORDER BY day"
    )

    plan = db.fetch_all("SELECT * FROM daily_plan WHERE active = true")

    chat_row = db.fetch_one(
        "SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1"
    )
    if not chat_row:
        return None
    chat_id = chat_row["chat_id"]

    prompt = f"""You are the head coach. Find ONE cross-table link the nightly coaches missed.

90-day monthly rollups:
{[dict(r) for r in monthly]}

14-day detailed:
{[dict(r) for r in detail_14d]}

e1rm trends:
{[dict(r) for r in e1rm_trends]}

Protein per pound:
{[dict(r) for r in protein_per_lb]}

Current plan:
{[dict(r) for r in plan]}

INSTRUCTIONS:
1. Find ONE link between two tables neither coach could see alone. Example: e1rm stopped rising the same week protein dropped under 0.8 g/lb.
2. Both series need 10+ data points. Otherwise say data doesn't support one and stop.
3. State with two numbers and overlapping dates. Same stall definition: 28-day slope zero or negative.
4. Give 2-3 supporting reads with SQL under each.
5. Give 3 actions for next 7 days. Each must be a daily_plan row change. Make the changes, list before/after.
6. If data doesn't support a conclusion, say so.

FORMAT:
[Finding with numbers and dates].

Supporting reads:
1. [finding] — [SQL]

Changes made to plan:
- [table]: [before] → [after]

RULES:
- Keep under 3,500 characters.
- Send SQL as second message if over limit.
- No encouragement if data is insufficient."""

    return chat_id, gemini.generate(prompt)
