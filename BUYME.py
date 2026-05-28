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
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"

if not TELEGRAM_TOKEN:
    print("Missing TELEGRAM_TOKEN")
    exit()

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]
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
        payload["reply_markup"] = reply_markup

    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print("send error:", e)

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

    return (
        f"🤖 <b>סטטוס מערכת</b>\n"
        f"🕒 {now.strftime('%H:%M:%S')}\n"
        f"📅 זמנים: {', '.join(all_times)}"
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

    for cat in [None, 1000, 1001, 1002]:
        for page in range(0, 5):
            payload = dict(base_payload)

            if cat:
                payload["categoryId"] = cat

            payload["requestPage"] = page

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
# FORMAT HELPERS
# =========================

def stock_text(stock):
    if stock is None:
        return "לא במלאי"
    if stock and stock > 0:
        return f"במלאי ({stock})"
    return "לא במלאי"

def stock_icon(stock):
    if stock and stock > 0:
        return "🟢"
    return "🔴"

# =========================
# MENU
# =========================

def main_menu(chat_id):
    send_telegram(chat_id, "🤖 <b>תפריט ראשי</b>", {
        "keyboard": [
            [{"text": "📊 דשבורד"}],
            [{"text": "🔍 בדיקה"}, {"text": "📄 דוח"}],
            [{"text": "🔥 BUYME"}],
            [{"text": "⏰ זמנים"}, {"text": "⚙️ הגדרות"}]
        ],
        "resize_keyboard": True
    })

# =========================
# BUYME REPORT (CLEAN)
# =========================

def buyme_report(chat_id):
    items = get_all_items()
    buyme = {t: d for t, d in items.items() if "BUY" in t.upper()}

    if not buyme:
        send_telegram(chat_id, "לא נמצא BUYME")
        return

    msg = "🔥 <b>BUYME דוח מסודר</b>\n━━━━━━━━━━━━\n"

    for t, d in sorted(buyme.items()):
        icon = stock_icon(d["stock"])
        status = stock_text(d["stock"])

        points = d.get("points", 0)

        msg += f"{icon} {t}\n📦 {status} | ⭐ {points}\n━━━━━━━━━━━━\n"

    send_telegram(chat_id, msg)

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

                    if text in ["/start"]:
                        main_menu(chat_id)

                    elif text == "📊 דשבורד":
                        send_telegram(chat_id,
                            "📊 <b>דשבורד</b>\n"
                            "✔ בדיקות מלאי\n"
                            "✔ דוחות בזמן אמת\n"
                            "✔ BUYME מוצרים\n"
                            "✔ ניהול זמנים"
                        )

                    elif text == "🔍 בדיקה":
                        items = get_all_items()
                        res = [
                            f"{stock_icon(d['stock'])} {t}"
                            for t, d in items.items()
                            if d["stock"] and d["stock"] > 0
                        ]
                        send_telegram(chat_id, "\n".join(res) if res else "לא נמצא")

                    elif text == "📄 דוח":
                        items = get_all_items()
                        msg = "📄 <b>דוח מלא</b>\n━━━━━━━━━━━━\n"

                        for t, d in sorted(items.items()):
                            msg += f"{stock_icon(d['stock'])} {t}\n📦 {stock_text(d['stock'])}\n━━━━━━━━━━━━\n"

                        send_telegram(chat_id, msg)

                    elif text == "🔥 BUYME":
                        buyme_report(chat_id)

                    elif text == "⚙️ הגדרות":
                        send_telegram(chat_id,
                            "⚙️ מערכת פעילה\n✔ סריקות ON\n✔ דוחות ON"
                        )

                    elif text == "⏰ זמנים":
                        send_telegram(chat_id,
                            "⏰ זמני מערכת:\n" + (", ".join(manual_times) or "אין")
                        )

                # CALLBACK
                elif "callback_query" in u:
                    cq = u["callback_query"]
                    answer_callback(cq["id"])

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
