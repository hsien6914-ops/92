import requests
import json
import time
import threading
from datetime import datetime
import pytz
import os

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MY_CHAT_ID = "7811189125"

ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]
manual_times = []
user_states = {}

last_triggered_time = None
last_status = {}

# =========================
# MENU
# =========================

def main_menu():
    return {
        "keyboard": [
            [{"text": "📊 דשבורד"}],
            [{"text": "🔍 בדיקה"}, {"text": "📄 דוח"}],
            [{"text": "🔥 BUYME"}],
            [{"text": "⏰ זמנים"}, {"text": "⚙️ הגדרות"}]
        ],
        "resize_keyboard": True
    }

# =========================
# TELEGRAM
# =========================

def send_telegram(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": MY_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

# =========================
# STRAUSS API (שלך)
# =========================

def get_all_items():
    try:
        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)

        headers = keys["headers"]
        headers.pop("content-length", None)
        headers.pop("accept-encoding", None)

        url = "https://cc.strauss-group.com/api/gifts/getGiftsPaginated"

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
                    r = requests.post(url, headers=headers, json=payload, timeout=10)

                    if r.status_code != 200:
                        break

                    body = r.json().get("body", {})
                    items = body.get("gifts") or body.get("items") or []

                    if not items:
                        break

                    for item in items:
                        title = item.get("title") or item.get("name") or "Unknown"
                        stock = item.get("stockCount") or 0
                        points = item.get("points", 0)

                        final_inventory[title] = {
                            "stock": stock,
                            "points": points
                        }

                    time.sleep(0.2)

                except:
                    break

        return final_inventory

    except:
        return {}

# =========================
# BUYME FILTER
# =========================

def filter_buyme(items):
    return {
        k: v for k, v in items.items()
        if "BUY" in k.upper()
    }

# =========================
# TIMES
# =========================

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

# =========================
# MONITOR (התראות אוטומטיות לפי שעות)
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
                                send_telegram(f"🟢 <b>{name}</b>\nחזר למלאי 🎉")
                            else:
                                send_telegram(f"🔴 <b>{name}</b>\nנגמר המלאי")

                            last_status[name] = stock

            time.sleep(15)

        except Exception as e:
            print("MONITOR ERROR:", e)
            time.sleep(5)

# =========================
# TELEGRAM HANDLER
# =========================

def handle_updates():
    last_id = 0

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_id + 1, "timeout": 20},
                timeout=30
            )

            data = r.json()

            for u in data.get("result", []):
                last_id = u["update_id"]

                if "message" not in u:
                    continue

                chat_id = u["message"]["chat"]["id"]
                text = u["message"].get("text", "")

                # START
                if text == "/start":
                    send_telegram(
                        "🤖 <b>דשבורד ראשי</b>\nבחר פעולה:",
                        main_menu()
                    )

                elif text == "📊 דשבורד":
                    send_telegram("📊 מערכת פעילה ✔", main_menu())

                elif text == "🔍 בדיקה":
                    items = get_all_items()

                    msg = "\n".join([
                        f"{'🟢' if v['stock'] else '🔴'} {k}"
                        for k, v in items.items()
                    ])

                    send_telegram(msg, main_menu())

                elif text == "📄 דוח":
                    items = get_all_items()

                    msg = "📄 <b>דוח מלאי</b>\n━━━━━━━━━━━━\n"

                    for k, v in items.items():
                        msg += f"{'🟢' if v['stock'] else '🔴'} {k}\n"

                    send_telegram(msg, main_menu())

                elif text == "🔥 BUYME":
                    items = filter_buyme(get_all_items())

                    if not items:
                        send_telegram("אין BUYME", main_menu())
                    else:
                        msg = "🔥 BUYME\n━━━━━━━━━━━━\n"

                        for k, v in items.items():
                            icon = "🟢" if v["stock"] else "🔴"
                            status = "במלאי" if v["stock"] else "לא במלאי"

                            msg += f"{icon} {k}\n📦 {status} | ⭐ {v['points']}\n━━━━━━━━━━━━\n"

                        send_telegram(msg, main_menu())

                elif text == "⏰ זמנים":
                    send_telegram(
                        "⏰ זמנים:\n" + (", ".join(manual_times) or "אין"),
                        main_menu()
                    )

                elif text == "⚙️ הגדרות":
                    send_telegram("⚙️ מערכת פעילה ✔", main_menu())

                elif text == "➕ הוסף זמן":
                    user_states[chat_id] = "add_time"
                    send_telegram("שלח זמן HH:MM")

                elif text == "🗑 מחק הכל":
                    manual_times.clear()
                    send_telegram("נמחק ✔", main_menu())

                elif user_states.get(chat_id) == "add_time":
                    if ":" in text:
                        manual_times.append(text)

                    user_states[chat_id] = None
                    send_telegram("נוסף ✔", main_menu())

        except:
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    handle_updates()
