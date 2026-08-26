# Step 6: Head Coach — Every Sunday at 6pm

The only one that can see across the tables. Your bench stalled the same week your protein dropped.

## Schedule

Runs every Sunday at 6:00 PM in your database timezone.

## n8n Workflow: "Gym - Head Coach"

### Nodes

**1. Schedule Trigger** — `cron: 0 18 * * 0` (Sundays at 6pm)

**2. Postgres** — Query (monthly rollups):

```sql
-- 90-day monthly rollups
SELECT
  date_trunc('month', day)::date AS month,
  SUM(calories) AS total_cal,
  SUM(protein_g) AS total_protein,
  AVG(protein_g / NULLIF(weight_lbs, 0)) AS avg_protein_per_lb,
  AVG(weight_lbs) AS avg_weight
FROM (
  SELECT
    fl.consumed_at::date AS day,
    fl.calories,
    fl.protein_g,
    bm.weight_lbs
  FROM food_log fl
  LEFT JOIN body_metrics bm ON bm.recorded_at::date = fl.consumed_at::date
  WHERE fl.consumed_at >= (CURRENT_DATE - interval '90 days')
) sub
GROUP BY month
ORDER BY month;
```

**3. Postgres** — Query (14-day detailed):

```sql
-- Last 14 days row by row
SELECT
  'food' AS source,
  fl.consumed_at::date AS day,
  fl.calories,
  fl.protein_g,
  fl.carbs_g,
  fl.fat_g,
  NULL AS e1rm,
  NULL AS exercise,
  NULL AS weight_lbs
FROM food_log fl
WHERE fl.consumed_at >= (CURRENT_DATE - interval '14 days')

UNION ALL

SELECT
  'training' AS source,
  w.session_date AS day,
  NULL AS calories,
  NULL AS protein_g,
  NULL AS carbs_g,
  NULL AS fat_g,
  ws.e1rm,
  e.name AS exercise,
  ws.weight_lbs
FROM workout_sets ws
JOIN workouts w ON w.id = ws.workout_id
JOIN exercises e ON e.id = ws.exercise_id
WHERE w.session_date >= (CURRENT_DATE - interval '14 days')

UNION ALL

SELECT
  'body' AS source,
  bm.recorded_at::date AS day,
  NULL AS calories,
  NULL AS protein_g,
  NULL AS carbs_g,
  NULL AS fat_g,
  NULL AS e1rm,
  NULL AS exercise,
  bm.weight_lbs
FROM body_metrics bm
WHERE bm.recorded_at >= (CURRENT_DATE - interval '14 days')

ORDER BY day;
```

**4. Postgres** — Query (e1rm trends per exercise):

```sql
-- Daily best e1rm per exercise, last 90 days
WITH daily_best AS (
  SELECT
    e.name AS exercise,
    e.pattern,
    w.session_date,
    MAX(ws.e1rm) AS best_e1rm
  FROM workout_sets ws
  JOIN workouts w ON w.id = ws.workout_id
  JOIN exercises e ON e.id = ws.exercise_id
  WHERE w.session_date >= (CURRENT_DATE - interval '90 days')
  GROUP BY e.name, e.pattern, w.session_date
)
SELECT exercise, pattern, session_date, best_e1rm
FROM daily_best
ORDER BY exercise, session_date;
```

**5. Postgres** — Query (protein per pound per day):

```sql
-- Daily protein per pound, last 14 days
SELECT
  fl.consumed_at::date AS day,
  SUM(fl.protein_g) AS total_protein,
  bm.weight_lbs,
  ROUND(SUM(fl.protein_g) / NULLIF(bm.weight_lbs, 0), 2) AS protein_per_lb
FROM food_log fl
LEFT JOIN body_metrics bm ON bm.recorded_at::date = fl.consumed_at::date
  OR bm.recorded_at = (
    SELECT MAX(recorded_at) FROM body_metrics
    WHERE recorded_at <= fl.consumed_at
  )
WHERE fl.consumed_at >= (CURRENT_DATE - interval '14 days')
GROUP BY fl.consumed_at::date, bm.weight_lbs
ORDER BY day;
```

**6. Postgres** — Query (current plan):

```sql
SELECT * FROM daily_plan WHERE active = true;
```

**7. Postgres** — Query (chat_id):

```sql
SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1;
```

**8. LLM Chain** (Gemini Flash-Lite) — Prompt:

```
You are the head coach — the only one who can see across all tables.
Find ONE cross-table link the nightly coaches missed.

DATA:
90-day monthly rollups: {{JSON.stringify($node2.json)}}
14-day detailed: {{JSON.stringify($node3.json)}}
e1rm trends: {{JSON.stringify($node4.json)}}
Protein per pound: {{JSON.stringify($node5.json)}}
Current plan: {{JSON.stringify($node6.json)}}

INSTRUCTIONS:
1. Find ONE link between two tables that neither nutrition
   nor training coach could see alone. Example: an e1rm that
   stopped rising the same week protein dropped under 0.8 g/lb.

2. Only report a link where BOTH series have at least 10 data
   points. Otherwise say data does not support one yet and stop.

3. State it with the two numbers that make it true and the
   dates they overlap. Use the same stall definition as
   training coach: 28-day slope is zero or negative.

4. Give 2-3 supporting reads, each with the SQL you ran under it.

5. Give 3 actions for the next 7 days. Every action must be
   a change to a row in daily_plan. Make the changes in the
   database, then list each row touched with before/after values.

6. If data does not support a conclusion, say so.
   Do not fill the gap with encouragement.

FORMAT YOUR MESSAGE AS:
[Cross-table finding with numbers and dates].

Supporting reads:
1. [finding] — [SQL]
2. [finding] — [SQL]

Changes made to your plan:
- [table]: [before] → [after]
- [table]: [before] → [after]
- [table]: [before] → [after]

RULES:
- Keep under 3,500 characters total.
- Send SQL as a second message if it pushes over.
- Send to chat_id on most recent messages row.
```

**9. Telegram Send Message** — chat_id from Step 7, text from LLM output.

## How It Works

1. Aggregates 90 days of data across food, training, supplements, and body metrics
2. Looks for correlations the nightly coaches can't see alone
3. Requires statistical significance (10+ data points per series)
4. Makes concrete changes to your daily_plan
5. Reports what it found and what it changed

## Example Output

```
Your bench e1RM went 279, 279, 279 across three sessions.
Protein averaged 0.71 g/lb every day of that stall.

Supporting reads:
1. Bench stall: 28-day slope = 0 (sessions Mar 1, 8, 15)
   SELECT ... FROM workout_sets WHERE exercise = 'bench'
2. Protein deficit: 0.71 g/lb avg (14-day window)
   SELECT ... FROM food_log JOIN body_metrics

Changes made to your plan:
- daily_plan: Whey at breakfast OFF → ON (40g)
- daily_plan: Protein target 150g → 180g
- daily_plan: Bedtime snack OFF → ON (casein 30g)
```

## If Data Doesn't Support a Conclusion

```
Insufficient data to draw a cross-table conclusion.
Need at least 10 data points for both series.
Current bench sessions: 3. Current protein entries: 5.
```
