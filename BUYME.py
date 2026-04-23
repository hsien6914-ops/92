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
    """שליחת הודעות HTML - תומך בפיצול הודעות ארוכות"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # אם ההודעה ארוכה מדי, טלגרם תדחה אותה. לכן נחתוך לבלוקים.
    if len(html_text) > 4000:
        for i in range(0, len(html_text), 4000):
            part = html_text[i:i+4000]
            requests.post(url, data={'chat_id': chat_id, 'text': part, 'parse_mode': 'HTML'}, timeout=15)
    else:
        requests.post(url, data={'chat_id': chat_id, 'text': html_text, 'parse_mode': 'HTML'}, timeout=15)

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
    """פקודת /check2 - סריקה יסודית ושליחת רשימה מלאה בפיצול הודעות"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url, headers = keys.get("url"), keys.get("headers")
        payload = keys.get("payload", {})
        
        all_gifts = {} 
        categories = [None, 1003, 1002, 1001, 1004, 1005]

        for cat in categories:
            payload["categoryId"] = cat
            for page in range(5): # סריקה עמוקה יותר (5 דפים לכל קטגוריה)
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                if not items: break # אם הדף ריק, נעבור לקטגוריה הבאה
                
                for item in items:
                    name = item.get('title') or item.get('name') or "Unknown"
                    stock = item.get('stockCount')
                    all_gifts[name] = stock
                time.sleep(0.3)

        if all_gifts:
            msg = "<b>📋 דוח מלאי מלא ומפורט:</b>\n\n"
            sorted_names = sorted(all_gifts.keys())
            for name in sorted_names:
                stock = all_gifts[name]
                if stock is not None and stock > 0:
                    msg += f"🟢 <b>{name}</b> (מלאי: {stock})\n"
                elif stock is not None and stock == 0:
                    msg += f"🔴 <s>{name}</s> (אזל)\n"
                else:
                    msg += f"🟢 <b>{name}</b> (זמין)\n"
            
            send_telegram_html(chat_id, msg)
        else:
            send_telegram_html(chat_id, "❌ לא נמצאו נתונים בסריקה המורחבת.")
    except Exception as e:
        send_telegram_html(chat_id, f"❌ תקלה בהפקת דוח: {e}")

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
                            send_telegram_html(chat_id, "📄 מתחיל סריקה עמוקה של כל הקטגוריות... (זה עשוי לקחת רגע)")
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        elif text.upper() == "OK":
                            send_telegram_html(chat_id, "🤖 הבוט פעיל וממתין לפקודות.")
        except:
            time.sleep(5)

# (הוספת הפונקציה החסרה run_stock_monitor מהקוד הקודם שלך כאן)
def run_stock_monitor(chat_id_to_alert):
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
                        send_telegram_html(chat_id_to_alert, f"🔥 נמצא מלאי ל-BUYME ALL! 🔥")
                        found = True; break
                if found: break
            if found: break
        if not found: send_telegram_html(chat_id_to_alert, "🔍 לא נמצא BUYME ALL.")
    except: pass

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
