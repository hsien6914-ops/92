import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות בסיס ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "7811189125" 
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
KEEP_ALIVE_URL = "https://ase-574b.onrender.com/"

# --- ניהול זמנים ומצבים ---
SYSTEM_TIMES = ["00:00", "08:00", "08:01", "08:07", "08:11", "08:15", "11:00", "12:00", "15:00"]
manual_times = [] 
user_states = {}

# --- שרת בריאות לשמירה על השרת פעיל ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Active")
    def log_message(self, format, *args): pass

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def keep_awake():
    while True:
        try:
            time.sleep(600)
            requests.get(KEEP_ALIVE_URL, timeout=10)
        except: pass

# --- פונקציות עזר לטלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_bot_status():
    now = datetime.now(ISRAEL_TZ)
    all_times = sorted(list(set(SYSTEM_TIMES + manual_times)))
    next_scan = "לא מוגדר"
    for t in all_times:
        t_hour, t_min = map(int, t.split(':'))
        scan_time = now.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
        if scan_time > now:
            next_scan = t
            break
    return f"<b>🤖 סטטוס מערכת:</b>\n🕒 שעה: <code>{now.strftime('%H:%M:%S')}</code>\n📅 תזמונים: {', '.join(all_times)}\n⏳ סריקה קרובה: <b>{next_scan}</b>"

# --- לוגיקת סריקה ---
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

# --- טיפול בעדכונים ---
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
                    
                    if user_states.get(chat_id) == "add_time":
                        if ":" in text and len(text) == 5:
                            manual_times.append(text); manual_times.sort()
                            send_telegram(chat_id, f"✅ הזמן {text} נוסף.")
                        else: send_telegram(chat_id, "❌ שלח פורמט HH:MM")
                        user_states[chat_id] = None; continue

                    if text in ["/start", "ok", "היי"]:
                        send_telegram(chat_id, "🤖 מערכת מוכנה:", reply_markup={
                            "keyboard": [[{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}], 
                                         [{"text": "⏰ ניהול זמנים"}, {"text": "🤖 סטטוס בוט"}], 
                                         [{"text": "❓ עזרה"}]], "resize_keyboard": True
                        })
                    elif text == "🔍 בדיקה מהירה":
                        items = get_all_items()
                        found = [f"{t} (כמות: {d['stock']})" for t, d in items.items() if d['stock'] and d['stock'] > 0 and "BUY" in t.upper()]
                        send_telegram(chat_id, f"🔥 נמצא: {', '.join(found)}" if found else "לא נמצא מלאי BUYME.")
                    elif text == "📄 דוח מלאי":
                        items = get_all_items()
                        msg = f"<b>📋 דוח מלאי ({len(items)} פריטים):</b>\n\n"
                        for t in sorted(items.keys()):
                            d = items[t]
                            icon = "🟢" if (d['stock'] and d['stock'] > 0) else "🔴"
                            msg += f"{icon} {t} | מלאי: <code>{d['stock'] or '?'}</code> | נק': {d['points']}\n"
                        send_telegram(chat_id, msg)
                    elif text == "🤖 סטטוס בוט": send_telegram(chat_id, get_bot_status())
                    elif text == "⏰ ניהול זמנים":
                        send_telegram(chat_id, "זמנים ידניים: " + (", ".join(manual_times) or "אין"), 
                                      reply_markup={"inline_keyboard": [[{"text": "➕ הוסף", "callback_data": "add"}], [{"text": "🗑️ נקה", "callback_data": "clear"}]]})
                    elif text == "❓ עזרה": send_telegram(chat_id, "לחץ על הכפתורים לסריקה.")
                
                elif "callback_query" in update:
                    cq = update["callback_query"]; chat_id = cq["message"]["chat"]["id"]
                    if cq["data"] == "add": user_states[chat_id] = "add_time"; send_telegram(chat_id, "שלח שעה (HH:MM):")
                    elif cq["data"] == "clear": manual_times.clear(); send_telegram(chat_id, "נמחק.")
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    handle_updates()
