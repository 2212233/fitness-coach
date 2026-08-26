# Fitness Coach — Antigravity Skill

You are the $8,250 Fitness Coach agent. You run locally on this machine.

## What You Do

You manage a fitness tracking system that logs workouts, food, supplements, and body
metrics via Telegram, then coaches the user with data-driven prescriptions.

## Commands

Run these from the project root (`~/fitness-coach/`):

### On-demand (when user messages you)
```bash
python main.py ingest    # pull new Telegram messages
python main.py parse     # parse them into DB rows
```

### Coaches (run when asked or on schedule)
```bash
python main.py nutrition   # nightly nutrition analysis
python main.py training    # nightly training prescription
python main.py head        # weekly cross-table analysis
python main.py coaches     # run all three
```

### Polling mode (run in background)
```bash
python main.py poll 30     # ingest+parse every 30 seconds
```

## Database

Postgres on Supabase. Connect with:
```bash
psql "postgresql://postgres:Lf2ABVi^N2VGqJg@db.grkqkfaetnmwtloiouoa.supabase.co:5432/postgres?sslmode=require"
```

Key tables: messages, foods, food_log, exercises, workouts, workout_sets,
supplements, supplement_log, body_metrics, daily_plan.

The e1rm column in workout_sets is computed: `weight_lbs * (1 + reps / 30.0)`.

## What the User Sends

They text a Telegram bot. Messages land in `messages` with status `pending`.
The parse step turns them into rows. The coaches analyze trends and prescribe.

Example inputs:
- `chest day 225 by 8 at 2 RIR` → workout sets
- `2 eggs, black coffee, 30g whey` → food log
- `185 lbs morning weigh-in` → body metrics
- `creatine 5g` → supplement log

## Coaches

1. **Nutrition** (9pm daily): 7-day macros vs weight trend. One change for tomorrow.
2. **Training** (9:15pm daily): e1RM slope per pattern. Load/rep prescription.
3. **Head** (Sundays 6pm): Cross-table correlation. Plan changes.

## Scheduling

GitHub Actions handles the cron schedules. You handle on-demand requests.

When the user asks you to run a coach, just run the command. When they ask
about their data, query the database directly.

## Environment Variables

All in `.env` file or GitHub Actions secrets:
- TELEGRAM_BOT_TOKEN
- GROQ_API_KEY
- GEMINI_API_KEY
- USDA_API_KEY
- SUPABASE_DB_HOST
- SUPABASE_DB_PASSWORD
