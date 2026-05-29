import requests
import json
import time
import threading
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = "YOUR_TOKEN"
MY_CHAT_ID = "7811189125"
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]
manual_times = []
user_states = {}

last_triggered_time = None
last_status = {}

# =========================
# STRAUSS SCANNER (שלך)
# =========================

def get_all_items():
    try:
        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)

        headers = keys["headers"]
        headers.pop("content-length", None)
        headers.pop("accept-encoding", None)

        list_url = "https://cc.strauss-group.com/api/gifts/getGiftsPaginated"

        final_inventory = {}
        categories = [None, 1000, 1001, 1002, 1003, 1004, 1005]

        for cat in categories:
            for page in range(0, 5):

                payload = {
                    "requestPage": page,
                    "pageSize": 50,
                    "searchTerm": "",
                    "subCategoryId": None
                }

                if cat:
                    payload["categoryId"] = cat

                try:
                    res = requests.post(
                        list_url,
                        headers=headers,
                        json=payload,
                        timeout=10
                    )

                    if res.status_code != 200:
                        break

                    body = res.json().get("body", {})

                    items = body.get("gifts") or body.get("items") or []

                    if not items:
                        break

                    for item in items:

                        title = item.get("title") or item.get("name") or "Unknown"
                        stock = item.get("stockCount")
                        points = item.get("points", 0)

                        final_inventory[title] = {
                            "stock": stock if stock is not None else 0,
                            "points": points
                        }

                    time.sleep(0.2)

                except:
                    break

        return final_inventory

    except Exception as e:
        print("SCAN ERROR:", e)
        return {}

# =========================
# TIMES
# =========================

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

# =========================
# TELEGRAM
# =========================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": MY_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except:
        pass

# =========================
# BUYME FILTER
# =========================

def filter_buyme(items):
    return {
        k: v for k, v in items.items()
        if "BUY" in k.upper()
    }

# =========================
# MONITOR (התראות לפי שעות + שינוי מלאי)
# =========================

def monitor():
    global last_triggered_time, last_status

    while True:
        try:
            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")

            if now in all_times():

                if last_triggered_time != now:
                    last_triggered_time = now

                    items = get_all_items()
                    buyme = filter_buyme(items)

                    if not buyme:
                        send_telegram("🔴 אין BUYME כרגע")
                        time.sleep(30)
                        continue

                    for name, data in buyme.items():

                        stock = data["stock"]
                        old = last_status.get(name)

                        if old != stock:

                            if stock > 0:
                                send_telegram(f"🟢 {name}\nחזר למלאי!")
                            else:
                                send_telegram(f"🔴 {name}\nנגמר המלאי")

                            last_status[name] = stock

                        else:
                            # עדכון סטטוס גם בלי שינוי
                            if stock > 0:
                                send_telegram(f"🟢 {name}\nבמלאי")
                            else:
                                send_telegram(f"🔴 {name}\nלא במלאי")

            time.sleep(20)

        except Exception as e:
            print("MONITOR ERROR:", e)
            time.sleep(5)

# =========================
# ZONE RUN
# =========================

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()

    while True:
        time.sleep(60)
