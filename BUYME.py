import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "7811189125"
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"

if not TELEGRAM_TOKEN:
    print("Missing TELEGRAM_TOKEN")
    exit()

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15", "11:00", "12:00", "15:00"]
manual_times = []
user_states = {}

# =========================
# HEALTH SERVER
# =========================

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

    def log_message(self, *args):
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

def keep_awake():
    while True:
        time.sleep(600)
        try:
            requests.get(KEEP_ALIVE_URL, timeout=10)
        except:
            pass

# =========================
# TELEGRAM
# =========================

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
        requests.post(url, json=payload, timeout=15)
    except:
        pass

def answer_callback(cid):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            params={"callback_query_id": cid},
            timeout=10
        )
    except:
        pass

# =========================
# STATUS
# =========================

def get_bot_status():
    now = datetime.now(ISRAEL_TZ)
    all_times = sorted(set(SYSTEM_TIMES + manual_times))

    next_scan = "לא מוגדר"
    for t in all_times:
        h, m = map(int, t.split(":"))
        if now.replace(hour=h, minute=m) > now:
            next_scan = t
            break

    return (
        f"🤖 <b>סטטוס</b>\n"
        f"🕒 {now.strftime('%H:%M:%S')}\n"
        f"📅 {', '.join(all_times)}\n"
        f"⏳ הבא: <b>{next_scan}</b>"
    )

# =========================
# DATA
# =========================

def get_all_items():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)

        url = keys["url"]
        headers = keys["headers"]
        base_payload = keys.get("payload", {})

    except:
        return {}

    result = {}

    for cat in [None, 1000, 1001, 1002, 1003]:
        for page in range(0, 6):
            payload = dict(base_payload)

            if cat:
                payload["categoryId"] = cat

            payload["requestPage"] = page
            payload["page"] = page

            try:
                r = requests.post(url, headers=headers, json=payload, timeout=10)
                data = r.json().get("body", {})

                items = data.get("gifts") or data.get("items") or []

                if not items:
                    break

                for i in items:
                    title = i.get("title") or i.get("name") or "ללא שם"

                    result[title] = {
                        "stock": i.get("stockCount") or i.get("quantity"),
                        "points": i.get("points", 0)
                    }

            except:
                break

    return result

# =========================
# HANDLER
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

                # MESSAGE
                if "message" in u and "text" in u["message"]:
                    chat_id = u["message"]["chat"]["id"]
                    text = u["message"]["text"].strip()

                    # ADD TIME MODE
                    if user_states.get(chat_id) == "add_time":
                        if ":" in text and len(text) == 5:
                            manual_times.append(text)
                            manual_times.sort()
                            send_telegram(chat_id, f"✅ נוסף: {text}")
                        else:
                            send_telegram(chat_id, "❌ פורמט HH:MM")

                        user_states[chat_id] = None
                        continue

                    # MENU
                    if text in ["/start", "היי", "ok"]:
                        send_telegram(chat_id, "🤖 מוכן", {
                            "keyboard": [
                                [{"text": "🔍 בדיקה"}, {"text": "📄 דוח"}],
                                [{"text": "🔥 דוח BUYME"}],
                                [{"text": "⏰ זמנים"}, {"text": "🤖 סטטוס"}]
                            ],
                            "resize_keyboard": True
                        })

                    # QUICK CHECK
                    elif text == "🔍 בדיקה":
                        items = get_all_items()
                        found = [
                            f"{t} ({d['stock']})"
                            for t, d in items.items()
                            if d["stock"] and d["stock"] > 0
                        ]
                        send_telegram(chat_id, "\n".join(found) if found else "לא נמצא")

                    # FULL REPORT
                    elif text == "📄 דוח":
                        items = get_all_items()

                        msg = f"📋 <b>דוח מלאי</b>\n━━━━━━━━━━━━\n"

                        for t, d in sorted(items.items()):
                            icon = "🟢" if d["stock"] else "🔴"
                            msg += f"{icon} {t}\n📦 {d['stock']} | ⭐ {d['points']}\n━━━━━━━━━━━━\n"

                        send_telegram(chat_id, msg)

                    # BUYME REPORT
                    elif text == "🔥 דוח BUYME":
                        items = get_all_items()

                        buyme = {t: d for t, d in items.items() if "BUY" in t.upper()}

                        if not buyme:
                            send_telegram(chat_id, "לא נמצא BUYME")
                            continue

                        msg = "🔥 <b>BUYME דוח</b>\n━━━━━━━━━━━━\n"

                        for t, d in sorted(buyme.items()):
                            icon = "🟢" if d["stock"] else "🔴"
                            msg += f"{icon} {t}\n📦 {d['stock']}\n━━━━━━━━━━━━\n"

                        send_telegram(chat_id, msg)

                    elif text == "🤖 סטטוס":
                        send_telegram(chat_id, get_bot_status())

                    elif text == "⏰ זמנים":
                        send_telegram(chat_id, "זמנים: " + (", ".join(manual_times) or "אין"), {
                            "inline_keyboard": [
                                [{"text": "➕ הוסף", "callback_data": "add"}],
                                [{"text": "🗑 נקה", "callback_data": "clear"}]
                            ]
                        })

                # CALLBACK
                elif "callback_query" in u:
                    cq = u["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]

                    answer_callback(cq["id"])

                    if cq["data"] == "add":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "שלח HH:MM")

                    elif cq["data"] == "clear":
                        manual_times.clear()
                        send_telegram(chat_id, "נמחק")

        except Exception as e:
            print("error:", e)
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    handle_updates()
