import requests
import json
import time
import threading
from datetime import datetime
import pytz
import os
from flask import Flask

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MY_CHAT_ID = "7811189125"

ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

# זמנים לשליחת דוח/דשבורד אוטומטי
SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]
manual_times = []
user_states = {} # מילון ששומר את המצב של המשתמש (למשל: ממתין להכנסת זמן)

last_status = {}
last_sent_dashboard = {}

dashboard_enabled = True

# =========================
# MENUS
# =========================

def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "🔥 בדוק BUYME עכשיו", "callback_data": "check_buyme"}],
            [{"text": "📄 דוח מלאי", "callback_data": "report"}],
            [{"text": "⏰ ניהול זמנים", "callback_data": "times"}],
            [{"text": f"📊 דשבורד אוטומטי: {'ON 🟢' if dashboard_enabled else 'OFF 🔴'}", "callback_data": "toggle_dashboard"}]
        ]
    }

def time_menu():
    return {
        "inline_keyboard": [
            [{"text": "➕ הוסף זמן", "callback_data": "add_time"}],
            [{"text": "🗑 מחק זמן", "callback_data": "delete_time"}],
            [{"text": "📋 רשימת זמנים", "callback_data": "list_times"}],
            [{"text": "⬅️ חזרה לתפריט", "callback_data": "back_main"}]
        ]
    }

# =========================
# TELEGRAM API HELPERS
# =========================

def send_telegram(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def edit_telegram(message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    payload = {"chat_id": MY_CHAT_ID, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error editing message: {e}")

def answer_callback(callback_id, text=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# =========================
# STRAUSS API
# =========================

def get_all_items():
    try:
        if not os.path.exists("strauss_keys.json"):
            print("ERROR: strauss_keys.json not found!")
            return {}

        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)

        headers = keys.get("headers", {})
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
                        final_inventory[title] = {"stock": stock, "points": points}
                except:
                    break
        return final_inventory
    except Exception as e:
        print(f"API Error: {e}")
        return {}

def filter_buyme(items):
    return {k: v for k, v in items.items() if "BUY" in k.upper()}

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

# =========================
# ACTIONS
# =========================

def send_dashboard_report():
    items = get_all_items()
    if not items:
        send_telegram("⚠️ שגיאה בשליפת נתונים (אולי חסר קובץ מפתחות?)")
        return

    buyme = filter_buyme(items)
    total = len(items)
    in_stock = sum(1 for v in items.values() if v["stock"] > 0)
    out_stock = total - in_stock
    now = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")

    text = f"📊 <b>דוח מצב מלאי</b>\n\n"
    text += f"🔥 BUYME במערכת: {len(buyme)}\n"
    text += f"📦 סה״כ פריטים: {total}\n"
    text += f"🟢 במלאי: {in_stock}\n"
    text += f"🔴 אזל: {out_stock}\n\n"
    text += f"🕒 נכון לשעה: {now}"
    
    send_telegram(text)

def check_buyme_now():
    items = get_all_items()
    buyme = filter_buyme(items)
    
    if not buyme:
        return "לא נמצאו פריטי BUYME במערכת כרגע."
    
    in_stock = {k: v for k, v in buyme.items() if v["stock"] > 0}
    if not in_stock:
        return "🔴 כל פריטי ה-BUYME אזלו מהמלאי."
    
    text = "🟢 <b>פריטי BUYME זמינים עכשיו:</b>\n\n"
    for name, data in in_stock.items():
        text += f"• {name} ({data['stock']} במלאי)\n"
    return text

# =========================
# BACKGROUND MONITORS
# =========================

def monitor_stock():
    global last_status
    while True:
        try:
            items = get_all_items()
            buyme = filter_buyme(items)

            for name, data in buyme.items():
                current_stock = data["stock"]
                old_stock = last_status.get(name)

                if old_stock is not None and old_stock != current_stock:
                    if current_stock > 0 and old_stock == 0:
                        send_telegram(f"🟢 <b>{name}</b>\nחזר למלאי! 🎉 ({current_stock} זמינים)")
                    elif current_stock == 0 and old_stock > 0:
                        send_telegram(f"🔴 <b>{name}</b>\nאזל מהמלאי.")

                last_status[name] = current_stock

            time.sleep(60)
        except Exception as e:
            time.sleep(60)

def monitor_schedules():
    global last_sent_dashboard
    while True:
        try:
            if not dashboard_enabled:
                time.sleep(30)
                continue

            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")
            today = datetime.now(ISRAEL_TZ).date()

            if now in all_times():
                if last_sent_dashboard.get(now) != today:
                    send_dashboard_report()
                    last_sent_dashboard[now] = today

            time.sleep(30)
        except Exception as e:
            time.sleep(30)

# =========================
# TELEGRAM BOT HANDLER
# =========================

def handle_updates():
    last_id = 0
    send_telegram("🚀 הבוט הופעל מחדש וזמין לפעולה!\nשלח /start כדי לפתוח את התפריט.")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_id + 1, "timeout": 20},
                timeout=30
            )
            data = r.json()

            for u in data.get("result", []):
                last_id = u["update_
