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

last_status = {}
last_sent = set()

# =========================
# DASHBOARD STATE
# =========================

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
# STRAUSS API
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

                except:
                    break

        return final_inventory

    except:
        return {}

# =========================
# BUYME FILTER
# =========================

def filter_buyme(items):
    return {k: v for k, v in items.items() if "BUY" in k.upper()}

# =========================
# TIME SYSTEM
# =========================

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

def normalize_time(t):
    try:
        h, m = t.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    except:
        return None

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

    text = f"""
📊 <b>דשבורד</b>

🔥 BUYME: {len(buyme)}
📦 סה״כ: {total}
🟢 במלאי: {in_stock}
🔴 אזל: {out_stock}

🕒 {now}
"""

    try:
        if dashboard_message_id:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
                json={
                    "chat_id": MY_CHAT_ID,
                    "message_id": dashboard_message_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": MY_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
            dashboard_message_id = r.json()["result"]["message_id"]

    except Exception as e:
        print("DASH ERROR:", e)

# =========================
# MONITOR (זמנים + התראות)
# =========================

def monitor():
    global last_sent

    while True:
        try:
            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")

            if now not in all_times():
                time.sleep(10)
                continue

            if now in last_sent:
                time.sleep(10)
                continue

            last_sent.add(now)

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

            if dashboard_enabled:
                update_dashboard()

            time.sleep(5)

        except Exception as e:
            print("MONITOR ERROR:", e)
            time.sleep(5)

# =========================
# HANDLER (INLINE BOT)
# =========================

def handle_updates():
    global dashboard_enabled, dashboard_message_id

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

                # =========================
                # CALLBACK
                # =========================

                if "callback_query" in u:
                    cq = u["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]
                    data_cb = cq["data"]

                    if data_cb == "buyme":
                        items = filter_buyme(get_all_items())

                        msg = "🔥 BUYME\n━━━━━━━━━━━━\n"
                        for k, v in items.items():
                            icon = "🟢" if v["stock"] else "🔴"
                            msg += f"{icon} {k}\n━━━━━━━━━━━━\n"

                        send_telegram(msg, main_menu())

                    elif data_cb == "report":
                        items = get_all_items()

                        msg = "📄 דוח\n━━━━━━━━━━━━\n"
                        for k, v in items.items():
                            msg += f"{'🟢' if v['stock'] else '🔴'} {k}\n"

                        send_telegram(msg, main_menu())

                    elif data_cb == "times":
                        send_telegram("⏰ זמנים:", time_menu())

                    elif data_cb == "list_times":
                        send_telegram(", ".join(all_times()) or "אין", time_menu())

                    elif data_cb == "back_main":
                        send_telegram("תפריט ראשי:", main_menu())

                    elif data_cb == "add_time":
                        user_states[chat_id] = "add_time"
                        send_telegram("שלח זמן HH:MM")

                    elif data_cb == "delete_time":
                        user_states[chat_id] = "delete_time"
                        send_telegram("שלח זמן למחיקה")

                    elif data_cb == "toggle_dashboard":
                        dashboard_enabled = not dashboard_enabled
                        status = "🟢 מופעל" if dashboard_enabled else "🔴 כבוי"
                        send_telegram(f"דשבורד: {status}", main_menu())

                # =========================
                # TEXT (זמנים)
                # =========================

                if "message" in u:
                    chat_id = u["message"]["chat"]["id"]
                    text = u["message"].get("text", "")

                    if user_states.get(chat_id) == "add_time":
                        t = normalize_time(text)

                        if t and t not in manual_times:
                            manual_times.append(t)
                            send_telegram(f"נוסף: {t}", main_menu())
                        else:
                            send_telegram("לא תקין", main_menu())

                        user_states[chat_id] = None

                    elif user_states.get(chat_id) == "delete_time":
                        t = normalize_time(text)

                        if t in manual_times:
                            manual_times.remove(t)
                            send_telegram(f"נמחק: {t}", main_menu())
                        else:
                            send_telegram("לא נמצא", main_menu())

                        user_states[chat_id] = None

        except:
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    handle_updates()
