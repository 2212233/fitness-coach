import os
import requests

BASE = "https://api.nal.usda.gov/fdc/v1"

_GRAMS_PER_UNIT = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "mg": 0.001,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
    "ml": 1.0,
    "ea": 1.0,
}


def _api_key():
    return os.environ["USDA_API_KEY"]


def search_food(query, page_size=25):
    r = requests.get(
        f"{BASE}/foods/search",
        params={
            "query": query,
            "pageSize": page_size,
            "sort": "dataType.keyword",
            "sortDirection": "desc",
            "api_key": _api_key(),
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("foods", [])


def _unit_to_grams(unit):
    if not unit:
        return None
    return _GRAMS_PER_UNIT.get(str(unit).lower())


def get_nutrients(food):
    """Return per-100g macros. USDA reports Energy in kJ on many entries."""
    per_serving = {}
    for n in food.get("foodNutrients", []):
        name = n.get("nutrientName", "")
        val = n.get("value") or 0
        unit = n.get("unitName", "").upper()
        if name.startswith("Energy"):
            per_serving["calories"] = val / 4.184 if unit == "KJ" else val
        elif name == "Protein":
            per_serving["protein_g"] = val
        elif name == "Carbohydrate, by difference":
            per_serving["carbs_g"] = val
        elif name == "Total lipid (fat)":
            per_serving["fat_g"] = val

    serving = food.get("servingSize")
    unit = food.get("servingSizeUnit")
    fac = _unit_to_grams(unit)
    serving_g = (serving * fac) if (serving and fac) else 100.0

    return {
        "per_serving": per_serving,
        "serving_g": serving_g,
    }


_TYPE_PRIORITY = {
    "Foundation": 3,
    "SR Legacy": 3,
    "Survey (FNDDS)": 3,
    "Branded": 0,
}


def _score(food, query):
    desc = (food.get("description") or "").lower()
    toks = [t for t in query.lower().split() if len(t) > 2]
    score = _TYPE_PRIORITY.get(food.get("dataType"), 1) * 10
    if all(t in desc for t in toks):
        score += 3
    elif any(t in desc for t in toks):
        score += 1
    if desc.startswith(query.lower()):
        score += 5
    if "whole" in desc:
        score += 2
    if any(seg in desc for seg in ("egg white", "egg yolk")):
        score -= 3
    if any(kw in desc for kw in (" raw", " fresh", " cooked")):
        score += 1
    if query == "rice":
        if "white" in desc or "cooked" in desc:
            score += 2
    unit = food.get("servingSizeUnit")
    if unit and _unit_to_grams(unit):
        score += 1
        if str(unit).lower() in ("mg", "ml"):
            score -= 5
    if any(bad in desc for bad in (
        "sauce", "dressing", "patty", "tenders", "breaded", "crunchy", "crispy",
        "crackers", "chips", "bun", "roll", "cereal", "cake", "cookie", "candy",
        "syrup", "jelly", "jam", "soup", "batter", "flour mix", "baking mix",
        "dry mix", "candied",
    )):
        score -= 3
    return score


def lookup(name):
    """Best-effort FDC lookup, normalized to per-100g macros."""
    foods = search_food(name)
    if not foods:
        return None

    foods.sort(key=lambda f: _score(f, name), reverse=True)

    best = None
    for food in foods:
        nut = get_nutrients(food)
        cal = nut["per_serving"].get("calories", 0)
        if cal and not (0 < cal / (nut["serving_g"] / 100.0) <= 1500):
            continue
        if nut["serving_g"] and nut["serving_g"] < 1:
            continue
        best = food
        break

    if best is None:
        best = foods[0]

    nut = get_nutrients(best)
    ps = nut["per_serving"]
    scale = 100.0 / nut["serving_g"]
    desc = (best.get("description") or name).lower()

    return {
        "name": desc,
        "brand": "",
        "serving_size": 100,
        "serving_unit": "g",
        "calories": round(ps.get("calories", 0) * scale, 1),
        "protein_g": round(ps.get("protein_g", 0) * scale, 1),
        "carbs_g": round(ps.get("carbs_g", 0) * scale, 1),
        "fat_g": round(ps.get("fat_g", 0) * scale, 1),
        "source_url": f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{best['fdcId']}",
    }