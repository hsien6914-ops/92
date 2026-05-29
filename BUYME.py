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

if not TELEGRAM_TOKEN:
    raise Exception("Missing TELEGRAM_TOKEN")

ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]
manual_times = []
user_states = {}

last_status = {}
last_sent = {}

dashboard_enabled = True
dashboard_message_id = None

# =========================
# INLINE MENU
# =========================

def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "🔥 BUYME", "callback_data": "buyme"}],
            [{"text": "📄 דוח", "callback_data": "report"}],
            [{"text": "⏰ זמנים", "callback_data": "times"}],
            [{"text": "📊 דשבורד ON/OFF", "callback_data": "toggle_dashboard"}]
        ]
    }

def time_menu():
    return {
        "inline_keyboard": [
            [{"text": "➕ הוסף זמן", "callback_data": "add_time"}],
            [{"text": "🗑 מחק זמן", "callback_data": "delete_time"}],
            [{"text": "📋 רשימה", "callback_data": "list_times"}],
            [{"text": "⬅️ חזרה", "callback_data": "back_main"}]
        ]
    }

# =========================
# SEND MESSAGE
# =========================

def send_telegram(text, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        payload = {
            "chat_id": MY_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }

        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        requests.post(url, json=payload, timeout=10)

    except Exception as e:
        print("SEND ERROR:", e)

# =========================
# STRAUSS API
# =========================

def get_all_items():
    try:
        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)

        headers = keys.get("headers", {})
        headers = headers.copy()
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
                        continue

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

                except:
                    continue

        return final_inventory

    except Exception as e:
        print("API ERROR:", e)
        return {}

# =========================
# FILTER
# =========================

def filter_buyme(items):
    return {k: v for k, v in items.items() if "BUY" in k.upper()}

# =========================
# TIMES
# =========================

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

# =========================
# DASHBOARD
# =========================

def update_dashboard():
    global dashboard_message_id

    if not dashboard_enabled:
        return

    items = get_all_items()
    buyme = filter_buyme(items)

    total = len(items)
    in_stock = sum(1 for v in items.values() if v["stock"])
    out_stock = total - in_stock

    now = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")

    text = (
        f"📊 <b>דשבורד</b>\n\n"
        f"🔥 BUYME: {len(buyme)}\n"
        f"📦 סה״כ: {total}\n"
        f"🟢 במלאי: {in_stock}\n"
        f"🔴 אזל: {out_stock}\n\n"
        f"🕒 {now}"
    )

    try:
        if dashboard_message_id:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
                json={
                    "chat_id": MY_CHAT_ID,
                    "message_id": dashboard_message_id,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": MY_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            dashboard_message_id = r.json().get("result", {}).get("message_id")

    except Exception as e:
        print("DASH ERROR:", e)

# =========================
# MONITOR LOOP
# =========================

def monitor():
    global last_status, last_sent

    while True:
        try:
            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")
            today = datetime.now(ISRAEL_TZ).date()

            if now not in all_times():
                time.sleep(5)
                continue

            if last_sent.get(now) == today:
                time.sleep(5)
                continue

            last_sent[now] = today

            items = get_all_items()
            buyme = filter_buyme(items)

            if not buyme:
                send_telegram("🔴 אין BUYME כרגע")
            else:
                for name, data in buyme.items():
                    stock = data["stock"]
                    old = last_status.get(name)

                    if old != stock:
                        if stock > 0:
                            send_telegram(f"🟢 <b>{name}</b>\nחזר למלאי 🎉")
                        else:
                            send_telegram(f"🔴 <b>{name}</b>\nנגמר המלאי")

                        last_status[name] = stock

            update_dashboard()

            time.sleep(5)

        except Exception as e:
            print("MONITOR ERROR:", e)
            time.sleep(5)

# =========================
# HANDLER
# =========================

def handle_updates():
    global dashboard_enabled

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

                if "callback_query" in u:
                    cq = u["callback_query"]
                    data_cb = cq["data"]

                    if data_cb == "toggle_dashboard":
                        dashboard_enabled = not dashboard_enabled
                        status = "🟢 מופעל" if dashboard_enabled else "🔴 כבוי"
                        send_telegram(f"דשבורד: {status}", main_menu())

        except Exception as e:
            print("HANDLER ERROR:", e)
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    handle_updates()
