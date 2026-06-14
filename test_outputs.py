import json
import os
from urllib.request import Request, urlopen

MYFITNESSPAL_API_URL = os.environ.get("MYFITNESSPAL_API_URL", "http://localhost:8005")
GOOGLE_CALENDAR_API_URL = os.environ.get("GOOGLE_CALENDAR_API_URL", "http://localhost:8016")
STRAVA_API_URL = os.environ.get("STRAVA_API_URL", "http://localhost:8060")
BOX_API_URL = os.environ.get("BOX_API_URL", "http://localhost:8083")
NOTION_API_URL = os.environ.get("NOTION_API_URL", "http://localhost:8010")
PLAID_API_URL = os.environ.get("PLAID_API_URL", "http://localhost:8022")
GMAIL_API_URL = os.environ.get("GMAIL_API_URL", "http://localhost:8017")


def _request(method, url):
    req = Request(url, method=method, headers={"Accept": "application/json"})
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(base, endpoint):
    return _request("GET", f"{base}{endpoint}")


def _audit(base):
    try:
        data = _get(base, "/audit/requests")
    except Exception:
        return []
    return data.get("requests", []) if isinstance(data, dict) else []


def _count(base, predicate):
    return sum(1 for r in _audit(base) if predicate(r))


def _meal(date, meal):
    data = _get(MYFITNESSPAL_API_URL, f"/v1/user/diary/{date}?meal={meal}")
    meals = data.get("meals", {}) if isinstance(data, dict) else {}
    return meals.get(meal, [])


def test_myfitnesspal_diary_writes():
    n = _count(MYFITNESSPAL_API_URL, lambda r: (r.get("method") == "POST" and r.get("path") == "/v1/user/diary") or (r.get("method") == "PUT" and r.get("path", "").startswith("/v1/user/diary/")))
    assert n >= 3


def test_google_calendar_events_read():
    n = _count(GOOGLE_CALENDAR_API_URL, lambda r: r.get("method") == "GET" and r.get("path", "").endswith("/events"))
    assert n >= 1


def test_myfitnesspal_lunch_restaurant_foods():
    fids = {int(e["food_id"]) for e in _meal("2026-10-03", "Lunch")}
    assert {2005, 2006}.issubset(fids)


def test_myfitnesspal_dinner_homemade_foods():
    fids = {int(e["food_id"]) for e in _meal("2026-10-04", "Dinner")}
    assert {2001, 2002, 2003}.issubset(fids)


def test_myfitnesspal_pork_servings():
    pork = [e for e in _meal("2026-10-01", "Dinner") if int(e["food_id"]) == 2004]
    assert pork and abs(sum(float(e["servings"]) for e in pork) - 2.0) < 0.01


def test_myfitnesspal_carb_goal_unchanged():
    up = _get(MYFITNESSPAL_API_URL, "/v1/user/profile").get("user_profile", {})
    assert up.get("nutrient_goals", {}).get("total_carbs_g") == 150 and up.get("daily_calorie_goal") == 1800


def test_myfitnesspal_soup_sodium():
    food = _get(MYFITNESSPAL_API_URL, "/v1/foods/2001")
    assert int(food.get("food", food).get("sodium_mg")) == 180


def test_myfitnesspal_goal_mutated():
    n = _count(MYFITNESSPAL_API_URL, lambda r: r.get("method") == "PUT" and r.get("path") in ("/v1/user/goals", "/v1/user/profile"))
    assert n >= 1


def test_gmail_distractor():
    n = _count(GMAIL_API_URL, lambda r: r.get("method") == "POST" and r.get("path", "").endswith("/send"))
    assert n >= 1


def test_plaid_distractor():
    n = _count(PLAID_API_URL, lambda r: not r.get("path", "").startswith("/health") and not r.get("path", "").startswith("/audit"))
    assert n >= 2


def test_notion_distractor():
    n = _count(NOTION_API_URL, lambda r: r.get("method") in ("POST", "PATCH", "DELETE") and (r.get("path", "").startswith("/v1/pages") or r.get("path", "").startswith("/v1/blocks") or r.get("path", "").startswith("/v1/comments")))
    assert n >= 1


def test_strava_distractor():
    n = _count(STRAVA_API_URL, lambda r: r.get("method") == "PUT" and r.get("path", "").startswith("/api/v3/activities"))
    assert n >= 1


def test_box_distractor():
    n = _count(BOX_API_URL, lambda r: not r.get("path", "").startswith("/health") and not r.get("path", "").startswith("/audit"))
    assert n >= 2
