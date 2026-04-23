import requests
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU"
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

def send_telegram_html(chat_id, html_text):
    """שליחת הודעה מעוצבת ב-HTML"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': html_text, 'parse_mode': 'HTML'}, timeout=15)
    except:
        pass

def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, dict):
                return data.get('body', {})
        return None
    except:
        return None

def run_full_report(chat_id):
    """פקודת /check2 - הודעה מעוצבת עם צבעים (אימוג'ים)"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url, headers = keys.get("url"), keys.get("headers")
        payload = keys.get("payload", {})
        
        all_gifts = {} # שימוש במילון למניעת כפילויות
        categories = [None, 1003, 1002, 1001, 1004, 1005]

        for cat in categories:
            payload["categoryId"] = cat
            for page in range(2): # סריקה מהירה של 2 דפים לכל קטגוריה
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                for item in items:
                    name = item.get('title') or item.get('name') or "Unknown"
                    stock = item.get('stockCount')
                    # שמירה לפי שם כדי למנוע כפילויות
                    all_gifts[name] = stock
                time.sleep(0.2)

        if all_gifts:
            msg = "<b>📋 דוח מלאי מעודכן:</b>\n\n"
            for name, stock in all_gifts.items():
                if stock is not None and stock > 0:
                    # מוצר במלאי - ירוק
                    msg += f"🟢 <b>{name}</b> (מלאי: {stock})\n"
                elif stock is not None and stock == 0:
                    # מוצר אזל - אדום ומחוק
                    msg += f"🔴 <s>{name}</s> (אזל)\n"
                else:
                    # מוצר זמין (ללא כמות ספציפית)
                    msg += f"🟢 <b>{name}</b> (זמין)\n"
            
            # טלגרם מגבילה הודעה ל-4096 תווים, אם ההודעה ארוכה מדי נחתוך אותה
            if len(msg) > 4000:
                msg = msg[:3900] + "\n\n<i>...הרשימה ארוכה מדי, מוצג חלקית</i>"
            
            send_telegram_html(chat_id, msg)
        else:
            send_telegram_html(chat_id, "❌ לא נמצאו נתונים בסריקה.")
    except Exception as e:
        send_telegram_html(chat_id, f"❌ תקלה בהפקת דוח: {e}")

def run_stock_monitor(chat_id_to_alert):
    """פקודת /check - חיפוש BUYME ALL"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers = keys.get("url"), keys.get("headers")
        payload = keys.get("payload", {})
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
                        stock = item.get('stockCount')
                        msg = f"🔥 <b>נמצא מלאי ל-BUYME ALL!</b> 🔥\nכמות: {stock if stock is not None else 'זמין'}"
                        send_telegram_html(chat_id_to_alert, msg)
                        found = True; break
                if found: break
            if found: break
        
        if not found:
            send_telegram_html(chat_id_to_alert, "🔍 <b>סריקה הושלמה:</b> BUYME ALL לא נמצא.")
    except:
        send_telegram_html(chat_id_to_alert, "❌ תקלה בסריקה המהירה.")

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
                            send_telegram_html(chat_id, "⏳ מחפש BUYME ALL...")
                            threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                        elif text == "/check2":
                            send_telegram_html(chat_id, "📄 מנתח מלאי נוכחי...")
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        elif text.upper() == "OK":
                            send_telegram_html(chat_id, "🤖 <b>הבוט הישראלי פעיל!</b>\n\n/check - חיפוש מהיר\n/check2 - דוח ויזואלי")
        except:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
