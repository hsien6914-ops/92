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

# --- ניהול זמנים ---
SYSTEM_TIMES = ["08:00", "12:20", "12:40", "15:00"] 
manual_times = [] 

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- פונקציות עזר לטלגרם ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # חלוקת הודעות ארוכות (לדוח מלא)
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            part = text[i:i+4000]
            requests.post(url, json={'chat_id': chat_id, 'text': part, 'parse_mode': 'HTML'}, timeout=15)
    else:
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
        try: requests.post(url, json=payload, timeout=15)
        except: pass

def get_bottom_keyboard():
    return {
        "keyboard": [
            [{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}],
            [{"text": "⏰ ניהול זמנים"}, {"text": "❓ עזרה"}]
        ],
        "resize_keyboard": True,
        "persistent": True
    }

# --- לוגיקת סריקה ודוחות ---
def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return res.json().get('body', {}) if res.status_code == 200 else None
    except: return None

def run_stock_monitor(chat_id, silent=False):
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        found = False
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            body = fetch_data_safely(url, headers, payload)
            if not body: continue
            items = body.get('gifts') or body.get('items') or []
            for item in items:
                if "BUYME ALL" in (item.get('title') or "").upper():
                    send_telegram(chat_id, "🔥 <b>נמצא מלאי ל-BUYME ALL!</b> 🔥")
                    found = True; break
            if found: break
        if not found and not silent:
            send_telegram(chat_id, "🔍 לא נמצא BUYME ALL.")
    except: send_telegram(chat_id, "❌ שגיאה בסריקה.")

def run_full_report(chat_id):
    """הפונקציה שהייתה חסרה - דוח מלאי מלא"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        all_gifts = {}
        categories = [None, 1003, 1002, 1001, 1004, 1005]
        
        for cat in categories:
            payload["categoryId"] = cat
            for page in range(4):
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                items = body.get('gifts') or body.get('items') or body.get('vouchers') or []
                if not items: break
                for item in items:
                    name = item.get('title') or item.get('name') or "Unknown"
                    stock = item.get('stockCount')
                    all_gifts[name] = stock
                time.sleep(0.2)

        if all_gifts:
            msg = "<b>📋 דוח מלאי מפורט:</b>\n\n"
            for name in sorted(all_gifts.keys()):
                stock = all_gifts[name]
                status = f"🟢 ({stock})" if stock and stock > 0 else "🔴 (אזל)"
                msg += f"{status} <b>{name}</b>\n"
            send_telegram(chat_id, msg)
    except Exception as e:
        send_telegram(chat_id, f"❌ שגיאה בהפקת הדוח: {e}")

# --- טיפול בעדכונים ---
def handle_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if not res.get("result"): continue
            
            for update in res["result"]:
                last_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]

                    if text in ["/start", "ok", "OK"]:
                        send_telegram(chat_id, "🤖 המערכת מוכנה:", reply_markup=get_bottom_keyboard())
                    
                    elif text == "🔍 בדיקה מהירה" or text == "/check":
                        send_telegram(chat_id, "⏳ בודק BUYME ALL...")
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    
                    elif text == "📄 דוח מלאי" or text == "/check2":
                        send_telegram(chat_id, "📄 מתחיל סריקה עמוקה...")
                        threading.Thread(target=run_full_report, args=(chat_id,)).start()
                        
                    elif text == "⏰ ניהול זמנים":
                        sys_list = ", ".join(SYSTEM_TIMES)
                        man_list = ", ".join(manual_times) if manual_times else "אין"
                        msg = f"⏰ <b>זמנים:</b>\n📌 מערכת: {sys_list}\n✏️ ידני: {man_list}"
                        markup = {"inline_keyboard": [[{"text": "🗑️ נקה ידני", "callback_data": "clear_manual"}]]}
                        send_telegram(chat_id, msg, reply_markup=markup)
                    
                    elif text == "❓ עזרה":
                        send_telegram(chat_id, "💡 <b>עזרה:</b>\nלהוספת זמן: <code>add 15:00</code>")

                    elif text.lower().startswith("add "):
                        t_val = text.lower().replace("add ", "").strip()
                        if len(t_val) == 5 and ":" in t_val:
                            manual_times.append(t_val)
                            manual_times.sort()
                            send_telegram(chat_id, f"✅ הזמן {t_val} נוסף.")

                if "callback_query" in update:
                    cq = update["callback_query"]
                    if cq["data"] == "clear_manual":
                        manual_times.clear()
                        send_telegram(cq["message"]["chat"]["id"], "🗑️ הזמנים הידניים נמחקו.")

        except: time.sleep(5)

def run_scheduler():
    last_min = -1
    while True:
        now = datetime.now(ISRAEL_TZ)
        now_str = now.strftime("%H:%M")
        all_times = SYSTEM_TIMES + manual_times
        if now_str in all_times and now.minute != last_min:
            last_min = now.minute
            send_telegram(MY_CHAT_ID, f"🕒 <b>תזמון {now_str}:</b>")
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_updates()
