import os
import requests

API_KEY = os.environ["USDA_API_KEY"]
BASE = "https://api.nal.usda.gov/fdc/v1"


def search_food(query, page_size=1):
    r = requests.get(
        f"{BASE}/foods/search",
        params={"query": query, "pageSize": page_size, "api_key": API_KEY},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("foods", [])


def get_nutrients(food):
    nutrients = {}
    for n in food.get("foodNutrients", []):
        name = n.get("nutrientName", "")
        val = n.get("value", 0)
        if name == "Energy":
            nutrients["calories"] = val
        elif name == "Protein":
            nutrients["protein_g"] = val
        elif name == "Carbohydrate, by difference":
            nutrients["carbs_g"] = val
        elif name == "Total lipid (fat)":
            nutrients["fat_g"] = val
    return nutrients


def lookup(name):
    foods = search_food(name)
    if not foods:
        return None
    fdc = foods[0]
    nutrients = get_nutrients(fdc)
    serving_size = fdc.get("servingSize") or 100
    serving_unit = fdc.get("servingSizeUnit") or "g"
    return {
        "name": name.lower(),
        "brand": "",
        "serving_size": serving_size,
        "serving_unit": serving_unit,
        "calories": nutrients.get("calories", 0),
        "protein_g": nutrients.get("protein_g", 0),
        "carbs_g": nutrients.get("carbs_g", 0),
        "fat_g": nutrients.get("fat_g", 0),
        "source_url": f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{fdc['fdcId']}",
    }
