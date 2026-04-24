import requests
import json
import time
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "634863346" 

# רשימת זמנים התחלתית
SCHEDULED_TIMES = ["08:00", "11:41", "11:49", "13:55", "14:00", "15:00"]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def send_telegram_html(chat_id, html_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': html_text, 'parse_mode': 'HTML'}, timeout=15)
    except: pass

def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get('body', {})
        return None
    except: return None

def run_stock_monitor(chat_id_to_alert, silent=False):
    """הפונקציה שמבצעת את הסריקה"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        found = False
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(2):
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                items = body.get('gifts') or body.get('items') or []
                for item in items:
                    name = (item.get('title') or item.get('name') or "").upper()
                    if "BUYME ALL" in name:
                        send_telegram_html(chat_id_to_alert, "🔥 <b>נמצא מלאי ל-BUYME ALL!</b> 🔥")
                        found = True; break
                if found: break
            if found: break
        
        if not found and not silent:
            send_telegram_html(chat_id_to_alert, "🔍 בדיקה מתוזמנת: BUYME ALL לא נמצא.")
    except Exception as e:
        if not silent: send_telegram_html(chat_id_to_alert, f"❌ שגיאה: {e}")

def run_scheduler():
    """מתזמן שרץ ברקע"""
    global SCHEDULED_TIMES
    print(f"Scheduler active for: {SCHEDULED_TIMES}")
    while True:
        now = datetime.now().strftime("%H:%M")
        if now in SCHEDULED_TIMES:
            # הרצה לא שקטה כדי שתוכל לראות שזה עובד
            run_stock_monitor(MY_CHAT_ID, silent=False)
            time.sleep(61) 
        time.sleep(20)

def handle_bot():
    global SCHEDULED_TIMES
    last_id = 0
    print("Bot is listening...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "").strip()

                        if text == "/check":
                            send_telegram_html(chat_id, "⏳ בודק עכשיו...")
                            run_stock_monitor(chat_id, False)
                        
                        elif text.startswith("add "):
                            new_time = text.replace("add ", "").strip()
                            # בדיקה שזה בפורמט HH:MM
                            if len(new_time) == 5 and ":" in new_time:
                                if new_time not in SCHEDULED_TIMES:
                                    SCHEDULED_TIMES.append(new_time)
                                    send_telegram_html(chat_id, f"✅ השעה {new_time} נוספה לתזמונים!")
                                else:
                                    send_telegram_html(chat_id, f"ℹ️ השעה {new_time} כבר קיימת.")
                            else:
                                send_telegram_html(chat_id, "❌ פורמט לא תקין. שלח: add 14:30")

                        elif text.upper() == "OK":
                            now_str = datetime.now().strftime("%H:%M:%S")
                            sched_str = ", ".join(sorted(list(set(SCHEDULED_TIMES))))
                            menu = (
                                f"<b>🤖 בוט ער (Render)</b>\n\n"
                                f"🕒 שעה נוכחית: <code>{now_str}</code>\n"
                                f"📅 תזמונים פעילים: {sched_str}\n\n"
                                "<b>פקודות:</b>\n"
                                "🔍 /check - בדיקה ידנית\n"
                                "➕ add HH:MM - הוספת זמן"
                            )
                            send_telegram_html(chat_id, menu)
        except:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_bot()
