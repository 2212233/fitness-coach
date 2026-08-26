# Step 4: Nutrition Coach — Nightly at 9pm

Seven days of macros against where your bodyweight is actually heading, and one change for tomorrow.

## Schedule

Runs every night at 9:00 PM in your database timezone.

## n8n Workflow: "Gym - Nutrition Coach"

### Nodes

**1. Schedule Trigger** — `cron: 0 21 * * *` (9pm daily)

**2. Postgres** — Query:

```sql
-- Last 7 days of macros, grouped by day
SELECT
  date_trunc('day', consumed_at)::date AS day,
  SUM(calories) AS calories,
  SUM(protein_g) AS protein,
  SUM(carbs_g) AS carbs,
  SUM(fat_g) AS fat
FROM food_log
WHERE consumed_at >= (CURRENT_DATE - interval '7 days')
GROUP BY day
ORDER BY day;
```

**3. Postgres** — Query:

```sql
-- Last 14 days of bodyweight
SELECT
  recorded_at::date AS day,
  weight_lbs
FROM body_metrics
WHERE recorded_at >= (CURRENT_DATE - interval '14 days')
ORDER BY recorded_at DESC;
```

**4. Postgres** — Query:

```sql
-- Current goals and meal plan
SELECT item_type, label, target_ref, target_value, target_unit
FROM daily_plan
WHERE active = true;
```

**5. Postgres** — Query:

```sql
-- Most recent message chat_id
SELECT chat_id FROM messages ORDER BY received_at DESC LIMIT 1;
```

**6. LLM Chain** (Gemini Flash-Lite) — Prompt:

```
You are a nutrition coach. Analyze this athlete's data and send ONE message.

DATA:
Last 7 days: {{JSON.stringify($node2.json)}}
Last 14 days weight: {{JSON.stringify($node3.json)}}
Goals: {{JSON.stringify($node4.json)}}
Chat ID: {{$node5.json.chat_id}}

INSTRUCTIONS:
1. Fit a least-squares line through weight_lbs against date over the last 14 days.
   Use the latest weigh-in on any day with more than one.
   Multiply daily slope by 7 for lbs/week.
   Fewer than 5 weigh-ins: skip this and say so.

2. Compare that rate against the weight_rate goal.
   Faster than goal = eat more. Slower = eat less.
   The goal is the target, never a fixed number.

3. Protein floor is 0.8 g per pound of most recent bodyweight.
   Flag every day under it. No food_log rows = not covered, not under.

4. List any active daily_plan meal row whose target_ref
   did not appear in food_log yesterday.

5. Name the ONE biggest gap, ranked:
   - Number of days under protein floor
   - Number of missed planned meals
   - Average calories away from calories goal
   Tie break: whichever happened most recently.

FORMAT YOUR MESSAGE AS:
[Yesterday's calories] / [protein] P / [carbs] C / [fat] F.
[Gap description].
Tomorrow: [ONE change]. Never prescribe something the log already shows.

RULES:
- If fewer than 4 of the last 7 days have food_log rows, say that and prescribe nothing.
- Keep under 500 characters.
- Send to chat_id on the most recent messages row.
```

**7. Telegram Send Message** — chat_id from Step 5, text from LLM output.

## How It Works

1. Pulls 7 days of food logs, 14 days of weight, and your current plan
2. Fits a trend line to your weight to find your actual rate of change
3. Compares your real rate to your goal rate
4. Checks protein floor (0.8g/lb) against each day
5. Finds missed planned meals
6. Picks the ONE biggest gap and prescribes ONE change

## Example Output

```
2,140 cal / 158 P / 190 C / 71 F.
Protein under 0.8 g/lb four days out of seven.
Tomorrow: add 40g of whey to breakfast.
```
