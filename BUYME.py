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

def run_full_report(chat_id):
    """סורק הכל ושולח קובץ טקסט עם כל המתנות שנמצאו"""
    if not os.path.exists(KEYS_FILE):
        send_telegram_msg(chat_id, "❌ קובץ strauss_keys.json חסר")
        return

    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys.get("url")
        headers = keys.get("headers")
        base_payload = keys.get("payload", {})
        
        all_gifts = []
        categories = [None, 1003, 1002, 1001, 1004, 1005]

        for cat in categories:
            base_payload["categoryId"] = cat
            for page in range(3): 
                base_payload["requestPage"] = page
                res = requests.post(url, headers=headers, json=base_payload, timeout=15)
                if res.status_code != 200: continue
                
                data = res.json()
                body = data.get('body', {})
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                
                for item in items:
                    name = item.get('title') or item.get('name') or "ללא שם"
                    stock = item.get('stockCount')
                    stock_str = str(stock) if stock is not None else "זמין"
                    gift_line = f"🎁 {name} | מלאי: {stock_str}"
                    if gift_line not in all_gifts:
                        all_gifts.append(gift_line)
                time.sleep(0.1)

        if all_gifts:
            with open(REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(f"--- דוח מלאי מלא ({time.strftime('%H:%M:%S')}) ---\n")
                f.write(f"נמצאו {len(all_gifts)} מתנות שונות:\n\n")
                for line in all_gifts:
                    f.write(line + "\n")
            
            with open(REPORT_PATH, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                              data={'chat_id': chat_id, 'caption': f"נמצאו {len(all_gifts)} פריטים בסריקה."}, 
                              files={'document': f})
        else:
            send_telegram_msg(chat_id, "לא נמצאו פריטים בסריקה. ייתכן שיש בעיית חיבור לשרת.")

    except Exception as e:
        send_telegram_msg(chat_id, f"❌ תקלה בהפקת דוח: {e}")

def run_stock_monitor(chat_id_to_alert):
    """סורק רגיל לחיפוש BUYME ALL"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        found = False
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(3):
                payload["requestPage"] = page
                res = requests.post(url, headers=headers, json=payload, timeout=10).json()
                items = res.get('body', {}).get('gifts') or res.get('body', {}).get('items') or []
                for item in items:
                    if "BUYME ALL" in (item.get('title') or "").upper():
                        send_telegram_msg(chat_id_to_alert, f"🚨 נמצא מלאי! 🚨\n{item.get('title')}")
                        found = True; break
                if found: break
            if found: break
        if not found: send_telegram_msg(chat_id_to_alert, "סריקה הושלמה: BUYME ALL לא נמצא. 🔍")
    except Exception as e: send_telegram_msg(chat_id_to_alert, "❌ תקלה בסריקה.")

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
                            send_telegram_msg(chat_id, "מפיק דוח מלאי מלא של כל המתנות... 📄")
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        elif text.upper() == "OK":
                            send_telegram_msg(chat_id, "הבוט פעיל!\n/check - חיפוש BUYME ALL\n/check2 - דוח מלאי מלא")
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
