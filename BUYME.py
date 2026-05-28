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
MY_CHAT_ID = "7811189125"
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

TIMES_FILE = "times.json"

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]

manual_times = []
user_states = {}

# =========================
# TIMES STORAGE
# =========================

def load_times():
    global manual_times
    try:
        with open(TIMES_FILE, "r") as f:
            manual_times = json.load(f)
    except:
        manual_times = []

def save_times():
    with open(TIMES_FILE, "w") as f:
        json.dump(manual_times, f)

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

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

def get_status():
    now = datetime.now(ISRAEL_TZ)
    return (
        f"🤖 <b>סטטוס מערכת</b>\n"
        f"🕒 {now.strftime('%H:%M:%S')}\n"
        f"⏰ זמנים:\n" + ", ".join(all_times())
    )

# =========================
# MOCK DATA (תחליף לAPI שלך)
# =========================

def get_all_items():
    # כאן אתה מחבר את ה-API שלך
    return {
        "BUYME 25": {"stock": 0, "points": 10},
        "ארון נעליים": {"stock": 5, "points": 20},
        "מוצר בדיקה": {"stock": 1, "points": 5},
    }

# =========================
# MENU
# =========================

def main_menu(chat_id):
    send_telegram(chat_id,
        "🤖 <b>דשבורד ראשי</b>",
        {
            "keyboard": [
                [{"text": "📊 דשבורד"}],
                [{"text": "🔍 בדיקה"}, {"text": "📄 דוח"}],
                [{"text": "🔥 BUYME"}],
                [{"text": "⏰ זמנים"}, {"text": "⚙️ הגדרות"}]
            ],
            "resize_keyboard": True
        }
    )

# =========================
# BUYME
# =========================

def buyme_report(chat_id):
    items = get_all_items()
    buyme = {t: d for t, d in items.items() if "BUY" in t.upper()}

    if not buyme:
        send_telegram(chat_id, "לא נמצא BUYME")
        return

    msg = "🔥 <b>BUYME</b>\n━━━━━━━━━━━━\n"

    for t, d in buyme.items():
        icon = "🟢" if d["stock"] else "🔴"
        status = "במלאי" if d["stock"] else "לא במלאי"

        msg += f"{icon} {t}\n📦 {status} | ⭐ {d['points']}\n━━━━━━━━━━━━\n"

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

                if "message" in u:
                    chat_id = u["message"]["chat"]["id"]
                    text = u["message"]["text"]

                    # START
                    if text == "/start":
                        main_menu(chat_id)

                    elif text == "📊 דשבורד":
                        send_telegram(chat_id, "📊 מערכת פעילה ✔")

                    elif text == "🔍 בדיקה":
                        items = get_all_items()
                        res = [
                            f"{'🟢' if d['stock'] else '🔴'} {t}"
                            for t, d in items.items()
                        ]
                        send_telegram(chat_id, "\n".join(res))

                    elif text == "📄 דוח":
                        items = get_all_items()
                        msg = "📄 <b>דוח</b>\n━━━━━━━━━━━━\n"

                        for t, d in items.items():
                            icon = "🟢" if d["stock"] else "🔴"
                            msg += f"{icon} {t}\n━━━━━━━━━━━━\n"

                        send_telegram(chat_id, msg)

                    elif text == "🔥 BUYME":
                        buyme_report(chat_id)

                    elif text == "⏰ זמנים":
                        send_telegram(chat_id,
                            "⏰ " + (", ".join(manual_times) or "אין"),
                            {
                                "keyboard": [
                                    [{"text": "➕ הוסף זמן"}, {"text": "🗑 מחק הכל"}],
                                    [{"text": "⬅️ חזור"}]
                                ],
                                "resize_keyboard": True
                            }
                        )

                    elif text == "⚙️ הגדרות":
                        send_telegram(chat_id, "⚙️ מערכת פעילה")

                    elif text == "⬅️ חזור":
                        main_menu(chat_id)

                    # ADD TIME MODE
                    elif text == "➕ הוסף זמן":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "שלח HH:MM")

                    elif text == "🗑 מחק הכל":
                        manual_times.clear()
                        save_times()
                        send_telegram(chat_id, "נמחק הכל")

                    elif user_states.get(chat_id) == "add_time":
                        if ":" in text:
                            manual_times.append(text)
                            save_times()
                            send_telegram(chat_id, "נוסף ✔")

                        user_states[chat_id] = None

                elif "callback_query" in u:
                    answer_callback(u["callback_query"]["id"])

        except:
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    load_times()
    handle_updates()
