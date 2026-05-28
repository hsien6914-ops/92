import requests
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות בסיס ---
# משתמשים ב-os.environ כדי למשוך את הטוקן מהגדרות השרת (Render)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- שרת בריאות (חובה ל-Render) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")
    def log_message(self, format, *args): pass

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"[SYSTEM] Health server started on port {port}")
    server.serve_forever()

# --- פונקציות טלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    if not TELEGRAM_TOKEN:
        print("[ERROR] TELEGRAM_TOKEN is missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: 
        payload['reply_markup'] = json.dumps(reply_markup)
    try: 
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

def get_bottom_keyboard():
    return {
        "keyboard": [
            [{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}],
            [{"text": "🤖 סטטוס בוט"}, {"text": "❓ עזרה"}]
        ],
        "resize_keyboard": True, "persistent": True
    }

# --- לולאת עדכונים (הלב של הבוט) ---
def handle_updates():
    last_id = 0
    print("[SYSTEM] Starting update loop...")
    while True:
        try:
            if not TELEGRAM_TOKEN:
                print("[ERROR] Token is not defined in Environment Variables!")
                time.sleep(10)
                continue

            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        print(f"[LOG] קיבלתי מ-{chat_id}: {text}")
                        
                        # לוגיקת תגובה
                        if text in ["/start", "ok", "היי"]:
                            send_telegram(chat_id, "🤖 המערכת מוכנה:", reply_markup=get_bottom_keyboard())
                        elif text == "🤖 סטטוס בוט":
                            send_telegram(chat_id, "✅ הבוט רץ ומחובר לשרת בהצלחה.")
            
        except Exception as e:
            print(f"[ERROR] Update loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # הרצת השרת בפורט 10000 במקביל לבוט
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_updates()
