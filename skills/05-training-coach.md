# Step 5: Training Coach — Nightly at 9:15pm

Reads every set you have ever logged, works out the slope on your estimated max, and tells you what to put on the bar.

## Schedule

Runs every night at 9:15 PM in your database timezone.

## n8n Workflow: "Gym - Training Coach"

### Nodes

**1. Schedule Trigger** — `cron: 15 21 * * *` (9:15pm daily)

**2. Postgres** — Query:

```sql
-- Best e1rm per exercise pattern per day, last 28 days
WITH daily_best AS (
  SELECT
    e.pattern,
    w.session_date,
    MAX(ws.e1rm) AS best_e1rm
  FROM workout_sets ws
  JOIN workouts w ON w.id = ws.workout_id
  JOIN exercises e ON e.id = ws.exercise_id
  WHERE w.session_date >= (CURRENT_DATE - interval '28 days')
  GROUP BY e.pattern, w.session_date
)
SELECT pattern, session_date, best_e1rm
FROM daily_best
ORDER BY pattern, session_date;
```

**3. Postgres** — Query:

```sql
-- Session count per pattern in last 28 days
SELECT
  e.pattern,
  COUNT(DISTINCT w.session_date) AS sessions
FROM workout_sets ws
JOIN workouts w ON w.id = ws.workout_id
JOIN exercises e ON e.id = ws.exercise_id
WHERE w.session_date >= (CURRENT_DATE - interval '28 days')
GROUP BY e.pattern;
```

**4. Postgres** — Query:

```sql
-- Bodyweight trend last 28 days
SELECT recorded_at::date AS day, weight_lbs
FROM body_metrics
WHERE recorded_at >= (CURRENT_DATE - interval '28 days')
ORDER BY recorded_at;
```

**5. Postgres** — Query:

```sql
-- Most recent session per pattern (for carry-forward)
WITH latest AS (
  SELECT
    e.pattern,
    w.session_date,
    ws.weight_lbs,
    ws.reps,
    ws.rir,
    ws.e1rm,
    ROW_NUMBER() OVER (PARTITION BY e.pattern ORDER BY w.session_date DESC, ws.set_index DESC) AS rn
  FROM workout_sets ws
  JOIN workouts w ON w.id = ws.workout_id
  JOIN exercises e ON e.id = ws.exercise_id
)
SELECT pattern, session_date, weight_lbs, reps, rir, e1rm
FROM latest WHERE rn = 1;
```

**6. Postgres** — Query:

```sql
-- Median gap between sessions per pattern
WITH gaps AS (
  SELECT
    e.pattern,
    w.session_date - LAG(w.session_date) OVER (PARTITION BY e.pattern ORDER BY w.session_date) AS gap_days
  FROM workout_sets ws
  JOIN workouts w ON w.id = ws.workout_id
  JOIN exercises e ON e.id = ws.exercise_id
  WHERE w.session_date >= (CURRENT_DATE - interval '28 days')
)
SELECT pattern, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_days) AS median_gap
FROM gaps
WHERE gap_days IS NOT NULL
GROUP BY pattern;
```

**7. Postgres** — Query:

```sql
-- Most recent message chat_id
SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1;
```

**8. LLM Chain** (Gemini Flash-Lite) — Prompt:

```
You are a training coach. Analyze this athlete's data and prescribe today's session.

DATA:
Best e1rm per day: {{JSON.stringify($node2.json)}}
Sessions per pattern: {{JSON.stringify($node3.json)}}
Bodyweight last 28 days: {{JSON.stringify($node4.json)}}
Latest session per pattern: {{JSON.stringify($node5.json)}}
Median gap per pattern: {{JSON.stringify($node6.json)}}
Chat ID: {{$node7.json.chat_id}}

INSTRUCTIONS:
1. For each exercises.pattern, take the single highest e1rm
   per session_date, then fit a least-squares line through
   those values over the last 28 days.
   Ignore any pattern with fewer than 3 sessions and say which.

2. Stalled = 28-day slope is zero or negative.
   Rising = positive.

3. Before prescribing for a stall, fit a line through bodyweight
   over the same 28 days. If bodyweight is falling by more than
   0.3 lbs/week, say the stall is a food problem and prescribe
   nothing for that pattern.

4. Otherwise match in this order:
   - stalled + bodyweight steady: hold load, add 1 rep to every set
   - rising + last set rir >= 2: +5 lbs compound, +2.5 lbs isolation
   - rising + rir 0/1/null: repeat last session exactly
   - falling > 2%/week: drop load 10%, repeat for 2 sessions
   Carry sets and reps from most recent session of that pattern.

5. If no workouts for longer than median gap, send a nudge:
   what you last did and how many days ago.

FORMAT YOUR MESSAGE AS:
[pattern] - [movement], [sets] x [reps] at [load] lbs (e1RM [value], [up/down] [x] on last week, RIR [value]).

RULES:
- No motivation, no encouragement.
- Order by most recent session_date first, then alphabetically.
- Send to chat_id on most recent messages row.
- Keep under 1000 characters.
```

**9. Telegram Send Message** — chat_id from Step 7, text from LLM output.

## How It Works

1. Pulls best e1RM per exercise pattern per day for 28 days
2. Counts sessions per pattern to filter low-data patterns
3. Fits trend lines to detect stalls, gains, or drops
4. Checks bodyweight trend to distinguish food stalls from training stalls
5. Prescribes load/rep changes based on the decision tree
6. Sends the prescription as a plain-text message

## Example Output

```
Horizontal push - bench, 3 x 8 at 230 lbs
(e1RM 285, up 6 on last week, RIR 2)

Vertical pull - barbell row, 4 x 8 at 185 lbs
(e1RM 231, up 5 on last week, RIR 1)

Hinge - deadlift, 3 x 5 at 315 lbs
(e1RM 367, first time logged)
```

## If You Haven't Lifted in a While

```
Nudge: You last benched 225x8 on March 15 — that's 12 days ago.
```
