from .. import db
from .. import gemini


def run():
    food_rows = db.fetch_all(
        "SELECT date_trunc('day', consumed_at)::date AS day, "
        "SUM(calories) AS calories, SUM(protein_g) AS protein, "
        "SUM(carbs_g) AS carbs, SUM(fat_g) AS fat "
        "FROM food_log WHERE consumed_at >= (CURRENT_DATE - interval '7 days') "
        "GROUP BY day ORDER BY day"
    )

    weight_rows = db.fetch_all(
        "SELECT recorded_at::date AS day, weight_lbs FROM body_metrics "
        "WHERE recorded_at >= (CURRENT_DATE - interval '14 days') "
        "ORDER BY recorded_at DESC"
    )

    goals = db.fetch_all(
        "SELECT item_type, label, target_ref, target_value, target_unit "
        "FROM daily_plan WHERE active = true"
    )

    chat_row = db.fetch_one(
        "SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1"
    )
    if not chat_row:
        return None
    chat_id = chat_row["chat_id"]

    food_json = [dict(r) for r in food_rows]
    weight_json = [dict(r) for r in weight_rows]
    goals_json = [dict(r) for r in goals]

    prompt = f"""You are a nutrition coach. Analyze this athlete's data and send ONE message.

Last 7 days of macros:
{food_json}

Last 14 days of bodyweight:
{weight_json}

Goals and meal plan:
{goals_json}

INSTRUCTIONS:
1. Fit a least-squares line through weight_lbs against date over the last 14 days. Use the latest weigh-in on any day with more than one. Multiply daily slope by 7 for lbs/week. Fewer than 5 weigh-ins: skip this and say so.
2. Compare that rate against the weight_rate goal. Faster = eat more. Slower = eat less.
3. Protein floor is 0.8g per pound of most recent bodyweight. Flag every day under it.
4. List any active daily_plan meal row whose target_ref did not appear in food_log yesterday.
5. Name the ONE biggest gap: days under protein floor > missed meals > calories from goal.

FORMAT:
[yesterday's cal] / [protein] P / [carbs] C / [fat] F.
[gap].
Tomorrow: [ONE change]. Never prescribe something the log already shows.

RULES:
- If fewer than 4 of 7 days have food_log rows, say that and prescribe nothing.
- Keep under 500 characters.
- No motivation. Just the numbers and one change."""

    return chat_id, gemini.generate(prompt)
