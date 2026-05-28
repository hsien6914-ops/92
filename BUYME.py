import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEYS_FILE = "strauss_keys.json"
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

SYSTEM_TIMES = ["08:00", "08:07", "08:15", "12:00", "00:00", "15:00"]
manual_times = []

# --- פונקציות עזר ---
def keep_awake():
    while True:
        try: requests.get(KEEP_ALIVE_URL, timeout=10)
        except: pass
        time.sleep(600)

def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_all_items():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers = keys["url"], keys["headers"]
        base_payload = keys.get("payload", {})
    except: return {}

    unique_items = {}
    for cat in [None, 1000, 1001, 1002, 1003, 1004, 1005]:
        for page in range(0, 8):
            payload = json.loads(json.dumps(base_payload))
            if cat: payload["categoryId"] = cat
            payload.update({"requestPage": page, "page": page})
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                items = res.json().get('body', {}).get('gifts') or res.json().get('body', {}).get('items') or []
                if not items: break
                for item in items:
                    title = item.get('title') or item.get('name') or "ללא שם"
                    unique_items[title] = {"stock": item.get('stockCount') or item.get('quantity'), "points": item.get('points', 0)}
            except: break
    return unique_items

# --- לוגיקת הודעות ---
def handle_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            for update in res.get("result", []):
                last_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"].strip()
                    
                    if text == "/start":
                        send_telegram(chat_id, "🤖 מערכת מנוהלת:", reply_markup={"keyboard": [[{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}], [{"text": "⏰ ניהול זמנים"}, {"text": "🤖 סטטוס בוט"}]], "resize_keyboard": True})
                    
                    elif text == "🔍 בדיקה מהירה":
                        items = get_all_items()
                        found = [f"{t} (כמות: {d['stock']})" for t, d in items.items() if d['stock'] and d['stock'] > 0 and "BUY" in t.upper()]
                        send_telegram(chat_id, f"🔥 נמצא: {', '.join(found)}" if found else "לא נמצא מלאי BUYME.")
                    
                    elif text == "📄 דוח מלאי":
                        items = get_all_items()
                        msg = f"<b>📋 דוח מלאי ({len(items)} פריטים):</b>\n"
                        for title, data in sorted(items.items()):
                            msg += f"• {title} | מלאי: {data['stock'] or 0}\n"
                            if len(msg) > 3000: # מניעת הודעות ארוכות מדי
                                send_telegram(chat_id, msg)
                                msg = ""
                        send_telegram(chat_id, msg)
                        
                    elif text == "⏰ ניהול זמנים":
                        send_telegram(chat_id, f"⏰ <b>זמנים מוגדרים:</b>\nמערכת: {', '.join(SYSTEM_TIMES)}\nידני: {', '.join(manual_times) if manual_times else 'אין'}")

        except: time.sleep(5)

def run_health_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    server = HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), lambda *args: None)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    handle_updates()
