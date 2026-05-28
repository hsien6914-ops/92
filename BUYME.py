import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות בסיס ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "7811189125"
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"

if not TELEGRAM_TOKEN:
    print("❌ חסר TELEGRAM_TOKEN")
    exit()

# --- ניהול זמנים ומצבים ---
SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15", "11:00", "12:00", "15:00"]
manual_times = []
user_states = {}

# --- שרת בריאות ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def keep_awake():
    while True:
        time.sleep(600)
        try:
            requests.get(KEEP_ALIVE_URL, timeout=10)
        except Exception as e:
            print("keep_awake error:", e)

# --- טלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        r = requests.post(url, json=payload, timeout=15)
        if not r.ok:
            print("Telegram error:", r.text)
    except Exception as e:
        print("send_telegram error:", e)

def answer_callback(cb_id):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            params={"callback_query_id": cb_id},
            timeout=10
        )
    except:
        pass

# --- סטטוס ---
def get_bot_status():
    now = datetime.now(ISRAEL_TZ)
    all_times = sorted(list(set(SYSTEM_TIMES + manual_times)))

    next_scan = "לא מוגדר"
    for t in all_times:
        h, m = map(int, t.split(':'))
        scan_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if scan_time > now:
            next_scan = t
            break

    return f"<b>🤖 סטטוס מערכת:</b>\n🕒 {now.strftime('%H:%M:%S')}\n📅 {', '.join(all_times)}\n⏳ הבא: <b>{next_scan}</b>"

# --- DATA ---
def get_all_items():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)

        url = keys["url"]
        headers = keys["headers"]
        base_payload = keys.get("payload", {})

    except Exception as e:
        print("keys error:", e)
        return {}

    result = {}

    for cat in [None, 1000, 1001, 1002, 1003, 1004, 1005]:
        for page in range(0, 8):
            payload = dict(base_payload)

            if cat:
                payload["categoryId"] = cat

            payload["requestPage"] = page
            payload["page"] = page

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                data = res.json().get('body', {})

                items = data.get('gifts') or data.get('items') or []

                if not items:
                    break

                for item in items:
                    title = item.get('title') or item.get('name') or "ללא שם"

                    result[title] = {
                        "stock": item.get('stockCount') or item.get('quantity'),
                        "points": item.get('points', 0)
                    }

            except Exception as e:
                print("fetch error:", e)
                break

    return result

# --- עדכונים ---
def handle_updates():
    last_id = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            res = requests.get(url, params={"offset": last_id + 1, "timeout": 20}, timeout=30)

            data = res.json()

            for update in data.get("result", []):
                last_id = update["update_id"]

                # MESSAGE
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"].strip()

                    if user_states.get(chat_id) == "add_time":
                        if ":" in text and len(text) == 5:
                            manual_times.append(text)
                            manual_times.sort()
                            send_telegram(chat_id, f"✅ נוסף {text}")
                        else:
                            send_telegram(chat_id, "❌ פורמט HH:MM")

                        user_states[chat_id] = None
                        continue

                    if text in ["/start", "ok", "היי"]:
                        send_telegram(chat_id, "🤖 מוכן:", reply_markup={
                            "keyboard": [
                                [{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}],
                                [{"text": "⏰ ניהול זמנים"}, {"text": "🤖 סטטוס בוט"}],
                                [{"text": "❓ עזרה"}]
                            ],
                            "resize_keyboard": True
                        })

                    elif text == "🔍 בדיקה מהירה":
                        items = get_all_items()
                        found = [
                            f"{t} (כמות: {d['stock']})"
                            for t, d in items.items()
                            if d["stock"] and d["stock"] > 0 and "BUY" in t.upper()
                        ]
                        send_telegram(chat_id, "\n".join(found) if found else "לא נמצא")

                    elif text == "📄 דוח מלאי":
                        items = get_all_items()
                        msg = f"<b>📋 דוח ({len(items)})</b>\n\n"

                        for t, d in items.items():
                            icon = "🟢" if d["stock"] else "🔴"
                            msg += f"{icon} {t} | {d['stock']} | {d['points']}\n"

                        send_telegram(chat_id, msg)

                    elif text == "🤖 סטטוס בוט":
                        send_telegram(chat_id, get_bot_status())

                    elif text == "⏰ ניהול זמנים":
                        send_telegram(chat_id, "זמנים: " + (", ".join(manual_times) or "אין"),
                                      reply_markup={
                                          "inline_keyboard": [
                                              [{"text": "➕ הוסף", "callback_data": "add"}],
                                              [{"text": "🗑️ נקה", "callback_data": "clear"}]
                                          ]
                                      })

                # CALLBACK
                elif "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]

                    answer_callback(cq["id"])

                    if cq["data"] == "add":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "שלח HH:MM")

                    elif cq["data"] == "clear":
                        manual_times.clear()
                        send_telegram(chat_id, "נמחק")

        except Exception as e:
            print("loop error:", e)
            time.sleep(3)

# --- START ---
if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    handle_updates()
