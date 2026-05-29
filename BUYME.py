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
user_states = {}

last_status = {}
last_sent_dashboard = {}

dashboard_enabled = True

# =========================
# MENUS (REPLY KEYBOARD)
# =========================

def main_menu():
    return {
        "keyboard": [
            [{"text": "🔥 בדוק BUYME עכשיו"}],
            [{"text": "📊 דוח מספרי קצר"}, {"text": "📄 דוח מוצרים מפורט"}],
            [{"text": "⏰ ניהול זמנים"}],
            [{"text": f"📊 דשבורד אוטומטי: {'ON 🟢' if dashboard_enabled else 'OFF 🔴'}"}]
        ],
        "resize_keyboard": True,       # מתאים את גודל הכפתורים למסך
        "one_time_keyboard": False     # משאיר את המקלדת פתוחה קבוע
    }

def time_menu():
    return {
        "keyboard": [
            [{"text": "➕ הוסף זמן"}, {"text": "🗑 מחק זמן"}],
            [{"text": "📋 רשימת זמנים"}],
            [{"text": "⬅️ חזרה לתפריט הראשית"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# =========================
# TELEGRAM API HELPERS
# =========================

def send_telegram(text, reply_markup=None):
    if not TELEGRAM_TOKEN:
        print("WARNING: TELEGRAM_TOKEN environment variable is missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

# =========================
# STRAUSS API
# =========================

def get_all_items():
    try:
        if not os.path.exists("strauss_keys.json"):
            print("WARNING: strauss_keys.json not found in current directory!")
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
        print(f"API General Error: {e}")
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

def send_detailed_report():
    items = get_all_items()
    if not items:
        send_telegram("⚠️ שגיאה בשליפת נתונים (אולי חסר קובץ מפתחות?)")
        return

    buyme_items = filter_buyme(items)
    
    in_stock = []
    out_of_stock = []
    
    for name, data in items.items():
        if "BUY" in name.upper():
            continue
        if data["stock"] > 0:
            in_stock.append(f"• {name} ({data['stock']} יח')")
        else:
            out_of_stock.append(f"• {name}")

    now = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")

    text = f"📊 <b>דוח מוצרים מפורט</b>\n"
    text += f"🕒 נכון לשעה: {now}\n"
    text += f"───────────────────\n\n"

    text += f"🔥 <b>פריטי BUYME במערכת:</b>\n"
    if buyme_items:
        for name, data in buyme_items.items():
            status_icon = "🟢" if data["stock"] > 0 else "🔴"
            text += f"{status_icon} {name} (מלאי: {data['stock']})\n"
    else:
        text += "לא נמצאו פריטי BUYME.\n"
        
    text += f"\n───────────────────\n\n"

    text += f"🟢 <b>מוצרים במלאי ({len(in_stock)} פריטים):</b>\n"
    if in_stock:
        text += "\n".join(in_stock[:40])
        if len(in_stock) > 40:
            text += f"\n... ועוד {len(in_stock) - 40} פריטים במלאי."
    else:
        text += "אין פריטים במלאי.\n"

    text += f"\n\n───────────────────\n\n"

    text += f"🔴 <b>מוצרים שאזלו מהמלאי ({len(out_of_stock)} פריטים):</b>\n"
    if out_of_stock:
        text += "\n".join(out_of_stock[:40])
        if len(out_of_stock) > 40:
            text += f"\n... ועוד {len(out_of_stock) - 40} פריטים שאזלו."
    else:
        text += "אין פריטים שאזלו.\n"

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
    print("Background Thread: Stock monitor initialized.")
    while True:
        try:
            items = get_all_items()
            if items:
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
            print(f"Monitor stock exception: {e}")
            time.sleep(60)

def monitor_schedules():
    global last_sent_dashboard
    print("Background Thread: Schedule monitor initialized.")
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
            print(f"Monitor schedules exception: {e}")
            time.sleep(30)

# =========================
# TELEGRAM BOT HANDLER
# =========================

def handle_updates():
    last_id = 0
    global dashboard_enabled
    print("Background Thread: Telegram updater initialized.")
    send_telegram("🚀 הבוט הופעל בהצלחה בענן! המקלדת זמינה למטה בתחתית המסך.", main_menu())

    while True:
        try:
            if not TELEGRAM_TOKEN:
                time.sleep(10)
                continue
                
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_id + 1, "timeout": 20},
                timeout=30
            )
            if r.status_code != 200:
                time.sleep(5)
                continue
                
            data = r.json()

            for u in data.get("result", []):
                last_id = u["update_id"]

                if "message" in u and "text" in u["message"]:
                    text = u["message"]["text"].strip()
                    chat_id = str(u["message"]["chat"]["id"])
                    state = user_states.get(chat_id)

                    # --- טיפול בקלט זמנים ידני (כשנמצאים בסטייט המתנה) ---
                    if state == "waiting_for_add_time":
                        if len(text) == 5 and ":" in text:
                            if text not in manual_times and text not in SYSTEM_TIMES:
                                manual_times.append(text)
                                send_telegram(f"✅ הזמן <b>{text}</b> נוסף בהצלחה!")
                            else:
                                send_telegram(f"⚠️ הזמן {text} כבר קיים.")
                        else:
                            send_telegram("❌ פורמט שגוי. יש להקליד כגון 14:30")
                        user_states[chat_id] = None
                        send_telegram("חזרה לתפריט הזמנים:", time_menu())
                        continue

                    elif state == "waiting_for_remove_time":
                        if text in manual_times:
                            manual_times.remove(text)
                            send_telegram(f"✅ הזמן <b>{text}</b> הוסר!")
                        else:
                            send_telegram("❌ הזמן לא נמצא ברשימה הידנית.")
                        user_states[chat_id] = None
                        send_telegram("חזרה לתפריט הזמנים:", time_menu())
                        continue

                    # --- טיפול בכפתורי המקלדת הראשיים ---
                    if text == "🔥 בדוק BUYME עכשיו":
                        send_telegram(check_buyme_now(), main_menu())

                    elif text == "📊 דוח מספרי קצר":
                        send_dashboard_report()

                    elif text == "📄 דוח מוצרים מפורט":
                        send_detailed_report()

                    elif text == "⏰ ניהול זמנים":
                        send_telegram("⏰ תפריט ניהול זמנים פתוח במקלדת למטה:", time_menu())

                    elif text == "⬅️ חזרה לתפריט הראשית" or text in ["/start", "תפריט"]:
                        user_states[chat_id] = None
                        send_telegram("תפריט ראשי:", main_menu())

                    elif text.startswith("📊 דשבורד אוטומטי:"):
                        dashboard_enabled = not dashboard_enabled
                        status_text = "הופעל 🟢" if dashboard_enabled else "כובה 🔴"
                        send_telegram(f"הדשבורד האוטומטי {status_text}", main_menu())

                    # --- כפתורי תפריט הזמנים ---
                    elif text == "➕ הוסף זמן":
                        user_states[chat_id] = "waiting_for_add_time"
                        send_telegram("✍️ הקלד זמן להוספה בפורמט HH:MM (למשל: 14:30):")

                    elif text == "🗑 מחק זמן":
                        user_states[chat_id] = "waiting_for_remove_time"
                        custom_times = ", ".join(manual_times) if manual_times else "אין זמנים ידניים"
                        send_telegram(f"🗑 הקלד זמן למחיקה מתוך הרשימה הידנית:\n<b>{custom_times}</b>")

                    elif text == "📋 רשימת זמנים":
                        times_str = ", ".join(all_times())
                        send_telegram(f"⏰ <b>זמנים מוגדרים:</b>\n{times_str}", time_menu())

        except Exception as e:
            print(f"Telegram Handler Exception: {e}")
            time.sleep(5)

# =========================
# WEB SERVER FOR RENDER
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "BOT IS RUNNING WELL!"

def start_bot_threads():
    print("Starting background threads...")
    threading.Thread(target=monitor_stock, daemon=True).start()
    threading.Thread(target=monitor_schedules, daemon=True).start()
    threading.Thread(target=handle_updates, daemon=True).start()

# =========================
# START
# =========================

if __name__ == "__main__":
    threading.Timer(2.0, start_bot_threads).start()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask web server on port {port}...")
    app.run(host="0.0.0.0", port=port)
