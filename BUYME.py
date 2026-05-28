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
# LOAD / SAVE TIMES
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
# TIMES HELPERS
# =========================

def all_times():
    return sorted(set(SYSTEM_TIMES + manual_times))

def format_times():
    if not manual_times:
        return "אין זמנים שהוספת"
    return ", ".join(manual_times)

# =========================
# STATUS
# =========================

def get_status():
    now = datetime.now(ISRAEL_TZ)

    return (
        f"🤖 <b>סטטוס מערכת</b>\n"
        f"🕒 {now.strftime('%H:%M:%S')}\n"
        f"⏰ זמנים:\n{', '.join(all_times())}"
    )

# =========================
# ALERT ENGINE
# =========================

sent = set()

def time_worker():
    while True:
        try:
            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")

            for t in all_times():
                key = f"{t}-{datetime.now().date()}"

                if now == t and key not in sent:
                    sent.add(key)

                    send_telegram(
                        MY_CHAT_ID,
                        f"🔔 <b>התראה</b>\n⏰ שעה: {t}"
                    )

            time.sleep(20)

        except:
            time.sleep(5)

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

                    # START
                    if text == "/start":
                        send_telegram(chat_id,
                            "🤖 <b>מערכת זמנים</b>",
                            {
                                "keyboard": [
                                    [{"text": "⏰ הצג זמנים"}],
                                    [{"text": "➕ הוסף זמן"}, {"text": "🗑 מחק הכל"}],
                                    [{"text": "📊 סטטוס"}]
                                ],
                                "resize_keyboard": True
                            }
                        )

                    # SHOW TIMES
                    elif text == "⏰ הצג זמנים":
                        send_telegram(chat_id,
                            "⏰ זמנים:\n" + (format_times())
                        )

                    # ADD TIME MODE
                    elif text == "➕ הוסף זמן":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "שלח זמן בפורמט HH:MM")

                    # DELETE ALL
                    elif text == "🗑 מחק הכל":
                        manual_times.clear()
                        save_times()
                        send_telegram(chat_id, "נמחקו כל הזמנים שהוספת")

                    # STATUS
                    elif text == "📊 סטטוס":
                        send_telegram(chat_id, get_status())

                    # ADD TIME INPUT
                    elif user_states.get(chat_id) == "add_time":
                        if ":" in text and len(text) == 5:
                            manual_times.append(text)
                            manual_times.sort()
                            save_times()

                            send_telegram(chat_id, f"✅ נוסף: {text}")
                        else:
                            send_telegram(chat_id, "❌ פורמט לא תקין (HH:MM)")

                        user_states[chat_id] = None

                # CALLBACK (לא קריטי פה אבל נשאר)
                elif "callback_query" in u:
                    answer_callback(u["callback_query"]["id"])

        except:
            time.sleep(3)

# =========================
# START
# =========================

if __name__ == "__main__":
    load_times()

    threading.Thread(target=time_worker, daemon=True).start()
    handle_updates()
