import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz  # וודא שזה מופיע ב-requirements.txt
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "634863346" 
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# זמני התזמון שלך
SCHEDULED_TIMES = ["08:00", "08:10", "08:20", "12:20", "12:40", "13:56", "13:59", "14:00", "15:00"]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def send_telegram_html(chat_id, html_text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': html_text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Error: {e}")

def send_menu(chat_id):
    current_time = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
    menu_text = (
        f"<b>🤖 הבוט פעיל ומחובר!</b>\n\n"
        f"🕒 <b>שעת ישראל:</b> <code>{current_time}</code>\n"
        f"📅 <b>תזמונים פעילים:</b> {', '.join(SCHEDULED_TIMES)}\n\n"
        "לחץ על הכפתורים למטה לביצוע בדיקה:"
    )
    keyboard = {
        "keyboard": [[{"text": "/check"}, {"text": "/check2"}], [{"text": "OK"}]],
        "resize_keyboard": True
    }
    send_telegram_html(chat_id, menu_text, reply_markup=keyboard)

def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json().get('body', {})
        return None
    except:
        return None

def run_stock_monitor(chat_id_to_alert, silent_if_not_found=False):
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
            
        # כאן השינוי - אם לא נמצא, הוא ישלח הודעה אם silent_if_not_found הוא False
        if not found and not silent_if_not_found:
            current_time = datetime.now(ISRAEL_TZ).strftime("%H:%M")
            send_telegram_html(chat_id_to_alert, f"🔍 סריקת תזמון ({current_time}): לא נמצא BUYME ALL.")
    except Exception as e:
        print(f"Monitor error: {e}")

def run_scheduler():
    last_run_minute = -1
    while True:
        now_dt = datetime.now(ISRAEL_TZ)
        now_str = now_dt.strftime("%H:%M")
        
        if now_str in SCHEDULED_TIMES and now_dt.minute != last_run_minute:
            # שינינו ל-False כדי שישלח הודעה גם כשלא מצא
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
            last_run_minute = now_dt.minute
        
        time.sleep(20)

def handle_bot():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "")

                        if text == "/check":
                            send_telegram_html(chat_id, "⏳ בודק...")
                            threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                        elif text == "/check2":
                            # כאן זה דוח מלא, תמיד שולח
                            import BUYME # אם הפונקציה בקובץ אחר, או פשוט קרא ל-run_full_report
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        elif text.upper() == "OK" or text == "/start":
                            send_menu(chat_id)
        except:
            time.sleep(5)

# (הוסף כאן את run_full_report מהקוד הקודם אם הוא באותו קובץ)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_bot()
