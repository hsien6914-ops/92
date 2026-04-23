import requests
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
KEYS_FILE = "strauss_keys.json"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
    except:
        pass

def run_stock_monitor(chat_id_to_alert):
    if not os.path.exists(KEYS_FILE):
        send_telegram_msg(chat_id_to_alert, "❌ קובץ strauss_keys.json חסר")
        return

    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys.get("url")
        headers = keys.get("headers")
        base_payload = keys.get("payload", {})
        
        if not url or not headers:
            send_telegram_msg(chat_id_to_alert, "❌ חסרים פרטים (URL/Headers) ב-JSON")
            return

        categories = [None, 1003, 1002, 1001, 1004, 1005]
        found = False

        for cat in categories:
            base_payload["categoryId"] = cat
            for page in range(2): # סריקה מצומצמת לבדיקה
                base_payload["requestPage"] = page
                res = requests.post(url, headers=headers, json=base_payload, timeout=15)
                
                if res.status_code != 200:
                    continue
                
                data = res.json()
                if not data or not isinstance(data, dict):
                    continue
                
                body = data.get('body')
                if not body or not isinstance(body, dict):
                    continue
                
                # בדיקה של כמה שדות אפשריים שבהם המלאי יכול להופיע
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                
                for item in items:
                    if not isinstance(item, dict): continue
                    name = item.get('title') or item.get('name') or ""
                    stock = item.get('stockCount')
                    
                    if "BUYME ALL" in name.upper():
                        msg = f"🚨 נמצא מלאי! 🚨\nמתנה: {name}\nמלאי: {stock if stock is not None else 'זמין'}"
                        send_telegram_msg(chat_id_to_alert, msg)
                        found = True
                if found: break
            if found: break
            
        if not found:
            send_telegram_msg(chat_id_to_alert, "סריקה הושלמה: BUYME ALL לא נמצא. 🔍")
            
    except Exception as e:
        send_telegram_msg(chat_id_to_alert, f"❌ תקלה בסריקה: שרת Strauss חסם את הגישה או החזיר תשובה ריקה.")
        print(f"Detailed Error: {e}")

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
                            send_telegram_msg(chat_id, "מתחיל סריקה זהירה... ⏳")
                            threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                        elif text.upper() == "OK":
                            send_telegram_msg(chat_id, "הבוט פעיל וממתין לפקודת /check")
        except:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
