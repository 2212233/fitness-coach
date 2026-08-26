-- $8,250 Fitness Coach — Free Stack
-- Step 1: Database Schema
-- Run this against your Supabase/Neon Postgres database

-- ============================================================
-- 0. Timezone setup (uncomment and set your timezone)
-- ============================================================
-- ALTER DATABASE postgres SET timezone TO 'America/New_York';
-- SELECT set_config('timezone', 'America/New_York', true);

-- ============================================================
-- 1. messages — every inbound message lands here first
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
  id          bigserial PRIMARY KEY,
  source      text NOT NULL,
  chat_id     bigint,
  kind        text NOT NULL CHECK (kind IN ('text', 'voice')),
  raw_text    text,
  transcript  text,
  status      text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'parsing', 'parsed', 'needs_review')),
  parsed_data jsonb,
  received_at timestamptz DEFAULT now()
);

-- ============================================================
-- 2. foods — your personal food database (macros stored once)
-- ============================================================
CREATE TABLE IF NOT EXISTS foods (
  id            bigserial PRIMARY KEY,
  name          text NOT NULL,
  brand         text NOT NULL DEFAULT '',
  serving_size  numeric,
  serving_unit  text,
  calories      numeric,
  protein_g     numeric,
  carbs_g       numeric,
  fat_g         numeric,
  source_url    text,
  UNIQUE (name, brand, serving_size, serving_unit)
);

-- ============================================================
-- 3. food_log — what you ate and when
-- ============================================================
CREATE TABLE IF NOT EXISTS food_log (
  id          bigserial PRIMARY KEY,
  food_id     bigint REFERENCES foods(id),
  quantity    numeric,
  calories    numeric,
  protein_g   numeric,
  carbs_g     numeric,
  fat_g       numeric,
  consumed_at timestamptz,
  message_id  bigint REFERENCES messages(id)
);

-- ============================================================
-- 4. exercises — your exercise library
-- ============================================================
CREATE TABLE IF NOT EXISTS exercises (
  id            bigserial PRIMARY KEY,
  name          text NOT NULL UNIQUE,
  pattern       text,
  primary_muscle text,
  equipment     text,
  is_compound   boolean
);

-- ============================================================
-- 5. workouts — one row per session
-- ============================================================
CREATE TABLE IF NOT EXISTS workouts (
  id            bigserial PRIMARY KEY,
  session_date  date,
  split         text,
  duration_min  int,
  bodyweight_lbs numeric,
  message_id    bigint REFERENCES messages(id)
);

-- ============================================================
-- 6. workout_sets — individual sets with computed e1rm
-- ============================================================
CREATE TABLE IF NOT EXISTS workout_sets (
  id          bigserial PRIMARY KEY,
  workout_id  bigint REFERENCES workouts(id),
  exercise_id bigint REFERENCES exercises(id),
  set_index   int,
  weight_lbs  numeric,
  reps        int,
  rir         int,
  e1rm        numeric GENERATED ALWAYS AS (weight_lbs * (1 + reps / 30.0)) STORED
);
-- ↑ Write 30.0, not 30. Integer division returns the bench weight
--   as your 1RM and never errors — so you'd never find out.

-- ============================================================
-- 7. supplements — your supplement database
-- ============================================================
CREATE TABLE IF NOT EXISTS supplements (
  id                bigserial PRIMARY KEY,
  name              text NOT NULL,
  brand             text NOT NULL DEFAULT '',
  form              text,
  serving_size      numeric,
  serving_unit      text,
  key_ingredients   jsonb,
  cost_per_serving  numeric
);

-- ============================================================
-- 8. supplement_log — what you took and when
-- ============================================================
CREATE TABLE IF NOT EXISTS supplement_log (
  id            bigserial PRIMARY KEY,
  supplement_id bigint REFERENCES supplements(id),
  quantity      numeric,
  taken_at      timestamptz,
  message_id    bigint REFERENCES messages(id)
);

-- ============================================================
-- 9. body_metrics — weigh-ins and measurements
-- ============================================================
CREATE TABLE IF NOT EXISTS body_metrics (
  id            bigserial PRIMARY KEY,
  weight_lbs    numeric,
  bodyfat_pct   numeric,
  waist_in      numeric,
  resting_hr    int,
  recorded_at   timestamptz,
  message_id    bigint REFERENCES messages(id)
);

-- ============================================================
-- 10. daily_plan — your meal plan, supplement schedule, goals
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_plan (
  id            bigserial PRIMARY KEY,
  time_local    time,
  item_type     text,
  label         text,
  target_ref    text,
  target_value  numeric,
  target_unit   text,
  active        boolean NOT NULL DEFAULT true
);
-- target_ref holds the exact lower-cased foods.name,
-- supplements.name or exercises.pattern that row points at.

-- ============================================================
-- 11. v_adherence — last 30 days, one row per day
-- ============================================================
CREATE OR REPLACE VIEW v_adherence AS
WITH day_series AS (
  SELECT generate_series(
    (CURRENT_DATE - interval '30 days')::date,
    CURRENT_DATE::date,
    '1 day'::interval
  )::date AS day
),
planned AS (
  SELECT day, count(*) AS planned
  FROM day_series, daily_plan
  WHERE active = true AND item_type != 'goal'
  GROUP BY day
),
hit AS (
  SELECT
    day,
    count(*) AS hit
  FROM day_series
  LEFT JOIN food_log fl ON fl.consumed_at::date = day_series.day
  LEFT JOIN supplement_log sl ON sl.taken_at::date = day_series.day
  LEFT JOIN workouts w ON w.session_date = day_series.day
  WHERE fl.id IS NOT NULL OR sl.id IS NOT NULL OR w.id IS NOT NULL
  GROUP BY day
)
SELECT
  d.day,
  COALESCE(p.planned, 0) AS planned,
  COALESCE(h.hit, 0) AS hit,
  COALESCE(p.planned, 0) - COALESCE(h.hit, 0) AS missed,
  ROUND(100.0 * COALESCE(h.hit, 0) / NULLIF(COALESCE(p.planned, 0), 0)) AS pct
FROM day_series d
LEFT JOIN planned p ON p.day = d.day
LEFT JOIN hit h ON h.day = d.day
ORDER BY d.day;

-- ============================================================
-- 12. Seed your goals (uncomment and fill in)
-- ============================================================
-- INSERT INTO daily_plan (item_type, label, target_value, target_unit) VALUES
--   ('goal', 'weight_rate', -1.0, 'lbs/week'),   -- negative = cutting
--   ('goal', 'calories', 2200, 'kcal');

-- ============================================================
-- 13. Indexes for the coaches' queries
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at);
CREATE INDEX IF NOT EXISTS idx_food_log_date ON food_log(consumed_at);
CREATE INDEX IF NOT EXISTS idx_food_log_message ON food_log(message_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_workout ON workout_sets(workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise ON workout_sets(exercise_id);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(session_date);
CREATE INDEX IF NOT EXISTS idx_workouts_message ON workouts(message_id);
CREATE INDEX IF NOT EXISTS idx_supplement_log_date ON supplement_log(taken_at);
CREATE INDEX IF NOT EXISTS idx_body_metrics_date ON body_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_daily_plan_active ON daily_plan(active);
CREATE INDEX IF NOT EXISTS idx_daily_plan_type ON daily_plan(item_type);
