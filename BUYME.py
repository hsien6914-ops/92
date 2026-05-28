import requests
import json
import time
import threading
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "7811189125"
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

TIMES_FILE = "strauss_keys.json"

SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15"]

manual_times = []
user_states = {}

# =========================
# STORAGE
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

def send(text, markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    if markup:
        payload["reply_markup"] = markup

    requests.post(url, json=payload)

# =========================
# MOCK API (תחליף לשרת שלך)
# =========================

def get_all_items():
    return {
        "BUYME 25": {"stock": int(time.time()) % 2, "points": 10},
        "ארון נעליים": {"stock": 5, "points": 20},
        "משטח גיימינג": {"stock": 1, "points": 5},
    }

# =========================
# STATE
# =========================

last_buyme_state = None
sent_times = set()

# =========================
# BUYME WATCH (חכם)
# =========================

def watch_buyme():
    global last_buyme_state

    while True:
        try:
            items = get_all_items()
            buyme = {t: d for t, d in items.items() if "BUY" in t.upper()}

            has_stock = any(d.get("stock") and d["stock"] > 0 for d in buyme.values())

            # יש מלאי
            if has_stock:
                if last_buyme_state != "available":
                    send("🔥 <b>BUYME זמין!</b>\n🟢 יש מוצרים במלאי")
                    last_buyme_state = "available"

            # אין מלאי
            else:
                if last_buyme_state != "empty":
                    send("🔴 <b>BUYME אזל!</b>\nאין מוצרים במלאי")
                    last_buyme_state = "empty"

            time.sleep(30)

        except:
            time.sleep(5)

# =========================
# TIME ENGINE
# =========================

def time_engine():
    while True:
        try:
            now = datetime.now(ISRAEL_TZ).strftime("%H:%M")

            if now in all_times():
                key = f"{now}-{datetime.now().date()}"

                if key not in sent_times:
                    sent_times.add(key)

                    items = get_all_items()
                    buyme = {t: d for t, d in items.items() if "BUY" in t.upper()}

                    if buyme:
                        msg = "⏰ <b>התראה מתוזמנת</b>\n━━━━━━━━━━\n"

                        for t, d in buyme.items():
                            status = "🟢 במלאי" if d["stock"] else "🔴 לא במלאי"
                            msg += f"{t}\n{status}\n━━━━━━━━━━\n"

                        send(msg)

            time.sleep(20)

        except:
            time.sleep(5)

# =========================
# MENU
# =========================

def menu():
    send("🤖 <b>דשבורד</b>", {
        "keyboard": [
            [{"text": "📊 דוח"}, {"text": "🔍 בדיקה"}],
            [{"text": "🔥 BUYME"}],
            [{"text": "⏰ זמנים"}]
        ],
        "resize_keyboard": True
    })

# =========================
# MOCK HANDLER (פשוט)
# =========================

def run_bot():
    menu()

    while True:
        time.sleep(100)

# =========================
# START
# =========================

if __name__ == "__main__":
    load_times()

    threading.Thread(target=watch_buyme, daemon=True).start()
    threading.Thread(target=time_engine, daemon=True).start()

    run_bot()
