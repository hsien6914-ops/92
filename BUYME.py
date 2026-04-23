import requests
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
KEYS_FILE = "strauss_keys.json"
REPORT_PATH = "/tmp/full_stock_report.txt"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

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

def get_data_safe(url, headers, payload):
    """פונקציה לביצוע בקשה בצורה בטוחה עם בדיקת שגיאות"""
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            return None
        data = res.json()
        if not data or not isinstance(data, dict):
            return None
        return data.get('body', {})
    except:
        return None

def run_full_report(chat_id):
    if not os.path.exists(KEYS_FILE):
        send_telegram_msg(chat_id, "❌ קובץ המפתחות חסר")
        return

    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys.get("url")
        headers = keys.get("headers")
        payload = keys.get("payload", {})
        
        all_gifts = []
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(3):
                payload["requestPage"] = page
                body = get_data_safe(url, headers, payload)
                if not body: break
                
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                for item in items:
                    name = item.get('title') or item.get('name') or "Unknown"
                    stock = item.get('stockCount')
                    all_gifts.append(f"🎁 {name} | מלאי: {stock if stock is not None else 'זמין'}")
                time.sleep(0.2)

        if all_gifts:
            unique_gifts = list(set(all_gifts))
            with open(REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(f"--- דוח מלאי ({time.strftime('%H:%M:%S')}) ---\n")
                for line in unique_gifts: f.write(line + "\n")
            
            with open(REPORT_PATH, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                              data={'chat_id': chat_id, 'caption': f"נמצאו {len(unique_gifts)} פריטים."}, 
                              files={'document': f})
        else:
            send_telegram_msg(chat_id, "לא נמצאו נתונים בסריקה.")
    except Exception as e:
        send_telegram_msg(chat_id, f"❌ תקלה: {str(e)}")

def run_stock_monitor(chat_id_to_alert):
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        found = False
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(3):
                payload["requestPage"] = page
                body = get_data_safe(url, headers, payload)
                if not body: break
                
                items = body.get('gifts') or body.get('items') or []
                for item in items:
                    name = (item.get('title') or item.get('name') or "").upper()
                    if "BUYME ALL" in name:
                        send_telegram_msg(chat_id_to_alert, f"🚨 נמצא מלאי! 🚨\n{item.get('title')}")
                        found = True; break
                if found: break
            if found: break
        if not found: send_telegram_msg(chat_id_to_alert, "סריקה הושלמה: BUYME ALL לא נמצא. 🔍")
    except:
        send_telegram_msg(chat_id_to_alert, "❌ תקלה בחיבור לשרת.")

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
                            send_telegram_msg(chat_id, "מחפש BUYME ALL... ⏳")
                            threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                        elif text == "/check2":
                            send_telegram_msg(chat_id, "מפיק דוח מלאי מלא... 📄")
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        elif text.upper() == "OK":
                            send_telegram_msg(chat_id, "הבוט פעיל!")
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
