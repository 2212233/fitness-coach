from . import db
from . import usda


def process_message(message_id, parsed):
    chat_id = db.fetch_one(
        "SELECT chat_id FROM messages WHERE id = %s", (message_id,)
    )["chat_id"]

    results = {"foods": 0, "sets": 0, "supplements": 0, "body": 0}

    db.execute("DELETE FROM food_log WHERE message_id = %s", (message_id,))
    db.execute(
        "DELETE FROM workout_sets WHERE workout_id IN "
        "(SELECT id FROM workouts WHERE message_id = %s)",
        (message_id,),
    )
    db.execute("DELETE FROM workouts WHERE message_id = %s", (message_id,))
    db.execute("DELETE FROM supplement_log WHERE message_id = %s", (message_id,))
    db.execute("DELETE FROM body_metrics WHERE message_id = %s", (message_id,))

    for food in parsed.get("foods", [])[:10]:
        _process_food(food, message_id)
        results["foods"] += 1

    if parsed.get("sets"):
        _process_sets(parsed["sets"], message_id)
        results["sets"] = len(parsed["sets"])

    for supp in parsed.get("supplements", []):
        _process_supplement(supp, message_id)
        results["supplements"] += 1

    for body in parsed.get("body", []):
        _process_body(body, message_id)
        results["body"] += 1

    child_count = sum(results.values())
    mentioned = parsed.get("mentioned_food") or parsed.get("mentioned_lifting")
    status = "needs_review" if (mentioned and child_count == 0) else "parsed"
    if child_count == 0:
        status = "needs_review"

    db.execute(
        "UPDATE messages SET status = %s, parsed_data = %s WHERE id = %s",
        (status, __import__("json").dumps(parsed), message_id),
    )

    return results, chat_id


def _process_food(food, message_id):
    name = food["name"].lower()
    brand = food.get("brand", "").lower()

    existing = db.fetch_one(
        "SELECT id, serving_size, serving_unit, calories, protein_g, carbs_g, fat_g "
        "FROM foods WHERE lower(name) = %s AND lower(coalesce(brand, '')) = %s LIMIT 1",
        (name, brand),
    )

    if existing:
        servings = food["quantity"] / (existing["serving_size"] or 1)
        db.execute(
            "INSERT INTO food_log "
            "(food_id, quantity, calories, protein_g, carbs_g, fat_g, consumed_at, message_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, now(), %s)",
            (
                existing["id"],
                food["quantity"],
                existing["calories"] * servings,
                existing["protein_g"] * servings,
                existing["carbs_g"] * servings,
                existing["fat_g"] * servings,
                message_id,
            ),
        )
        return

    info = usda.lookup(name)
    if not info:
        return

    existing = db.fetch_one(
        "SELECT id FROM foods WHERE lower(name) = %s AND lower(coalesce(brand, '')) = %s "
        "AND serving_size = %s LIMIT 1",
        (name, brand, info["serving_size"]),
    )

    if existing:
        food_id = existing["id"]
    else:
        row = db.fetch_one(
            "INSERT INTO foods (name, brand, serving_size, serving_unit, calories, "
            "protein_g, carbs_g, fat_g, source_url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                info["name"],
                info["brand"],
                info["serving_size"],
                info["serving_unit"],
                info["calories"],
                info["protein_g"],
                info["carbs_g"],
                info["fat_g"],
                info["source_url"],
            ),
        )
        food_id = row["id"]

    servings = food["quantity"] / info["serving_size"]
    db.execute(
        "INSERT INTO food_log "
        "(food_id, quantity, calories, protein_g, carbs_g, fat_g, consumed_at, message_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, now(), %s)",
        (
            food_id,
            food["quantity"],
            info["calories"] * servings,
            info["protein_g"] * servings,
            info["carbs_g"] * servings,
            info["fat_g"] * servings,
            message_id,
        ),
    )


def _process_sets(sets, message_id):
    workout = db.fetch_one(
        "SELECT id FROM workouts WHERE session_date = CURRENT_DATE"
    )
    if not workout:
        bw = db.fetch_one(
            "SELECT weight_lbs FROM body_metrics ORDER BY recorded_at DESC LIMIT 1"
        )
        bw_val = bw["weight_lbs"] if bw else None
        workout = db.fetch_one(
            "INSERT INTO workouts (session_date, bodyweight_lbs, message_id) "
            "VALUES (CURRENT_DATE, %s, %s) RETURNING id",
            (bw_val, message_id),
        )

    workout_id = workout["id"]

    for i, s in enumerate(sets):
        name = s["exercise"].lower()
        ex = db.fetch_one(
            "SELECT id FROM exercises WHERE lower(name) = %s", (name,)
        )
        if not ex:
            pattern = _infer_pattern(name)
            is_compound = pattern != "isolation"
            ex = db.fetch_one(
                "INSERT INTO exercises (name, pattern, is_compound) "
                "VALUES (%s, %s, %s) RETURNING id",
                (name, pattern, is_compound),
            )

        idx = db.fetch_one(
            "SELECT COALESCE(MAX(set_index), 0) + 1 AS next_idx "
            "FROM workout_sets WHERE workout_id = %s AND exercise_id = %s",
            (workout_id, ex["id"]),
        )["next_idx"]

        db.execute(
            "INSERT INTO workout_sets "
            "(workout_id, exercise_id, set_index, weight_lbs, reps, rir) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (workout_id, ex["id"], idx, s["weight_lbs"], s["reps"], s.get("rir")),
        )


def _process_supplement(supp, message_id):
    name = supp["name"].lower()
    existing = db.fetch_one(
        "SELECT id FROM supplements WHERE lower(name) = %s LIMIT 1", (name,)
    )
    if not existing:
        existing = db.fetch_one(
            "INSERT INTO supplements (name) VALUES (%s) RETURNING id", (name,)
        )
    db.execute(
        "INSERT INTO supplement_log (supplement_id, quantity, taken_at, message_id) "
        "VALUES (%s, %s, now(), %s)",
        (existing["id"], supp["quantity"], message_id),
    )


def _process_body(body, message_id):
    db.execute(
        "INSERT INTO body_metrics "
        "(weight_lbs, bodyfat_pct, waist_in, resting_hr, recorded_at, message_id) "
        "VALUES (%s, %s, %s, %s, now(), %s)",
        (
            body.get("weight_lbs"),
            body.get("bodyfat_pct"),
            body.get("waist_in"),
            body.get("resting_hr"),
            message_id,
        ),
    )


def _infer_pattern(name):
    if any(w in name for w in ("bench", "press", "push")):
        return "horizontal_push"
    if any(w in name for w in ("overhead", "shoulder")):
        return "vertical_push"
    if any(w in name for w in ("row", "pull", "lat")):
        return "horizontal_pull"
    if any(w in name for w in ("pullup", "chinup", "pulldown")):
        return "vertical_pull"
    if any(w in name for w in ("deadlift", "romain", "hip")):
        return "hinge"
    if any(w in name for w in ("squat", "leg press")):
        return "squat"
    if any(w in name for w in ("carry", "walk")):
        return "carry"
    return "isolation"
