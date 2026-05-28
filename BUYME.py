import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות בסיס ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "7811189125" 
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

SYSTEM_TIMES = ["08:00", "08:07", "08:15", "12:00", "00:00", "15:00"] 
manual_times = [] 
user_states = {}

# --- שרת בריאות ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")
    def log_message(self, format, *args): pass

def run_health_server():
    # Render מגדיר את משתנה הסביבה PORT באופן אוטומטי
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health server started on port {port}")
    server.serve_forever()

def keep_awake():
    url = "https://nine2-de7r.onrender.com/"
    while True:
        try:
            time.sleep(600)
            requests.get(url, timeout=10)
        except: pass

# --- פונקציות טלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_bottom_keyboard():
    return {
        "keyboard": [
            [{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}],
            [{"text": "⏰ ניהול זמנים"}, {"text": "🤖 סטטוס בוט"}],
            [{"text": "❓ עזרה"}]
        ],
        "resize_keyboard": True, "persistent": True
    }

def get_all_items():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url = keys["url"]
        headers = keys["headers"]
        headers.pop("content-length", None)
        headers.pop("accept-encoding", None)
        base_payload = keys.get("payload", {})
    except Exception as e:
        return {}

    unique_items = {}
    categories = [None, 1000, 1001, 1002, 1003, 1004, 1005]
    for cat in categories:
        for page in range(0, 8): 
            payload = json.loads(json.dumps(base_payload))
            if cat: payload["categoryId"] = cat
            payload["requestPage"] = page
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=15)
                if res.status_code != 200: break
                body = res.json().get('body', {})
                items = body.get('gifts') or body.get('items') or []
                if not items: break
                for item in items:
                    title = item.get('title') or item.get('name') or "מוצר ללא שם"
                    stock = item.get('stockCount') or item.get('quantity')
                    unique_items[title] = {"stock": stock, "points": item.get('points', 0)}
                time.sleep(0.4)
            except: break
    return unique_items

def run_stock_monitor(chat_id, silent=False):
    items_dict = get_all_items()
    found = False
    for title, data in items_dict.items():
        if any(x in title.upper() for x in ["BUYME", "ביימי"]):
            if data.get('stock', 0) > 0:
                send_telegram(chat_id, f"🔥 <b>נמצא מלאי ל: {title}!</b> 🔥\nכמות: {data.get('stock')}")
                found = True
    if not found and not silent:
        send_telegram(chat_id, f"🔍 סריקה הסתיימה. לא נמצא BUYME.")

# --- לולאת עדכונים ראשית ---
def handle_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if not res.get("ok"): continue
            for update in res.get("result", []):
                last_id = update["update_id"]
                # כאן באה הלוגיקה שלך לטיפול בהודעות...
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    handle_updates()
