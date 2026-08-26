# $8,250 Fitness Coach — Free Stack Setup

## Architecture

```
User → Telegram Bot → GitHub Actions (every 10 min) → Supabase
                                                         ↑
                              Antigravity (local agent) ──┘
                                                         ↓
                              GitHub Actions (coaches) → Telegram
```

| Slot | Tool | Cost |
|------|------|------|
| Database | Supabase | Free |
| Workflows | GitHub Actions (public repo) | Free |
| Chat | Telegram | Free |
| Voice→Text | Groq | Free tier |
| Parsing brain | Gemini Flash-Lite | Free tier |
| Food macros | USDA FoodData Central | Free |
| Agent | Google Antigravity (local) | Free |

**Total: $0/month**

---

## Setup Steps

### 1. Create the Database

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project
2. SQL Editor → paste `sql/01_schema.sql` → Run
3. Uncomment and edit goals at the bottom of the SQL:

```sql
INSERT INTO daily_plan (item_type, label, target_value, target_unit) VALUES
  ('goal', 'weight_rate', -1.0, 'lbs/week'),
  ('goal', 'calories', 2200, 'kcal');
```

4. Verify: Table Editor → 10 tables + 1 view

### 2. Push to GitHub

```bash
cd ~/fitness-coach
git init
git add -A
git commit -m "init fitness coach"
```

Create a **public** repo on GitHub (free = unlimited minutes), then:

```bash
git remote add origin git@github.com:YOUR_USER/fitness-coach.git
git push -u origin main
```

### 3. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | from `.env` file |
| `GROQ_API_KEY` | from `.env` file |
| `GEMINI_API_KEY` | from `.env` file |
| `USDA_API_KEY` | from `.env` file |
| `SUPABASE_DB_HOST` | from `.env` file |
| `SUPABASE_DB_PASSWORD` | from `.env` file |

### 4. Enable GitHub Actions

Push to main → Actions tab → enable workflows. The schedules:

| Workflow | Schedule | Runs/month |
|----------|----------|------------|
| ingest-parse | every 10 min | ~4,320 |
| nutrition | 9pm daily | 30 |
| training | 9:15pm daily | 30 |
| head | Sundays 6pm | 4 |

All free on a public repo.

### 5. Test the Bot

1. Open Telegram → find your bot → press **Start**
2. Send `testing`
3. Within 10 minutes, you should see `Got it - logging now.`
4. Send `chest day 225 by 8 at 2 RIR`
5. Within 10 minutes, you should see `Logged 3 sets.`

### 6. Set Up Antigravity (Local Agent)

```bash
cd ~/fitness-coach
pip install -r requirements.txt
```

In Antigravity, load the skill:
```
load skills/antigravity.md
```

Now you can ask Antigravity to:
- "Run the nutrition coach"
- "Show me my last 7 days of food"
- "What's my bench e1RM trend?"
- "How many workouts this week?"

---

## CLI Usage

```bash
python main.py ingest          # pull Telegram messages
python main.py parse           # parse into DB rows
python main.py nutrition       # nutrition coach
python main.py training        # training coach
python main.py head            # head coach
python main.py coaches         # all three
python main.py poll            # continuous ingest+parse loop
```

---

## Test Messages

| Send | Expect |
|------|--------|
| `testing` | `Got it - logging now.` |
| `chest day 225 by 8 at 2 RIR` | `Logged 3 sets.` |
| `2 eggs, black coffee, 30g whey` | `Logged 3 foods.` |
| `185 lbs morning weigh-in` | `Logged 1 body metrics.` |
| `creatine 5g, fish oil 2 caps` | `Logged 2 supplements.` |

---

## File Structure

```
fitness-coach/
├── .github/workflows/
│   ├── ingest-parse.yml    # every 10 min
│   ├── nutrition.yml       # 9pm daily
│   ├── training.yml        # 9:15pm daily
│   └── head.yml            # Sundays 6pm
├── src/
│   ├── db.py               # Postgres connection
│   ├── telegram.py         # Telegram Bot API
│   ├── groq.py             # Voice transcription
│   ├── gemini.py           # LLM parsing + generation
│   ├── usda.py             # Food macro lookup
│   ├── parser.py           # Process parsed JSON → DB
│   └── coaches/
│       ├── nutrition.py    # Nightly nutrition analysis
│       ├── training.py     # Nightly training prescription
│       └── head.py         # Weekly cross-table analysis
├── sql/
│   └── 01_schema.sql       # 10 tables + view
├── skills/
│   └── antigravity.md      # Agent skill file
├── main.py                 # CLI entry point
├── requirements.txt        # Python deps
└── .env                    # Local env vars (DO NOT commit)
```

---

## How It Works

1. **Every 10 min**: GitHub Actions runs `ingest` → `parse`
   - Polls Telegram for new messages
   - Voice notes → Groq transcription
   - Text → Gemini parsing → DB rows
   - Replies with what was logged

2. **9pm daily**: Nutrition coach
   - Pulls 7 days of food, 14 days of weight
   - Fits trend line, compares to goal
   - Sends ONE change for tomorrow

3. **9:15pm daily**: Training coach
   - Pulls e1RM per pattern for 28 days
   - Detects stalls/gains/drops
   - Prescribes load/rep changes

4. **Sundays 6pm**: Head coach
   - Cross-table correlation analysis
   - Makes changes to daily_plan
   - Reports findings + SQL

5. **Local**: Antigravity handles on-demand queries
   - "What did I eat today?"
   - "Run the coaches now"
   - "Show my bench progress"
