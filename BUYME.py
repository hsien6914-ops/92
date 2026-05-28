import requests
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEYS_FILE = "strauss_keys.json"
# הכתובת של השירות שלך ב-Render
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"

# --- פונקציית שמירה על השרת פעיל ---
def keep_awake():
    print("[SYSTEM] Keep-alive thread started.")
    while True:
        try:
            requests.get(KEEP_ALIVE_URL, timeout=10)
            print("[SYSTEM] Ping sent to keep alive.")
        except Exception as e:
            print(f"[ERROR] Keep-alive failed: {e}")
        time.sleep(600)  # פינג כל 10 דקות

# --- פונקציות סריקה ---
def get_all_items():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers = keys["url"], keys["headers"]
        base_payload = keys.get("payload", {})
    except: return {}

    unique_items = {}
    for cat in [None, 1000, 1001, 1002, 1003, 1004, 1005]:
        for page in range(0, 5): 
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

# --- פונקציות טלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def handle_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        
                        if text in ["/start", "ok", "היי"]:
                            send_telegram(chat_id, "🤖 מערכת מוכנה:", reply_markup={"keyboard": [[{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}], [{"text": "🤖 סטטוס בוט"}]], "resize_keyboard": True})
                        elif text == "🔍 בדיקה מהירה":
                            send_telegram(chat_id, "סורק... אנא המתן.")
                            items = get_all_items()
                            found = [f"{t} (כמות: {d['stock']})" for t, d in items.items() if d['stock'] and d['stock'] > 0 and "BUY" in t.upper()]
                            send_telegram(chat_id, f"נמצא מלאי: {', '.join(found)}" if found else "לא נמצא מלאי BUYME.")
                        elif text == "📄 דוח מלאי":
                            send_telegram(chat_id, f"נסרקו {len(get_all_items())} פריטים. המערכת פעילה.")
        except: time.sleep(5)

# --- שרת בריאות ---
def run_health_server():
    server = HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), lambda *args: None)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start() # כאן הוספתי את הפונקציה
    handle_updates()
