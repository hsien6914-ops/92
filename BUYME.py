import requests
import json
import time
import os
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "7811189125" 
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# רשימת זמנים דינמית (מתחילה עם ברירת המחדל שלך)
SCHEDULED_TIMES = ["08:00", "12:20", "12:40", "14:15", "15:00", "20:00"]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=15)
    except: pass

def get_main_menu():
    """יוצר את תפריט הכפתורים הראשי (Inline)"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔍 בדיקה מהירה", "callback_data": "run_check"},
                {"text": "📄 דוח מלאי מלא", "callback_data": "run_report"}
            ],
            [
                {"text": "⏰ ניהול זמנים", "callback_data": "manage_times"},
                {"text": "❓ הסבר פקודות", "callback_data": "show_help"}
            ],
            [
                {"text": "🔄 רענן סטטוס", "callback_data": "refresh_status"}
            ]
        ]
    }

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
            send_telegram(chat_id, "🔍 סריקה הושלמה: לא נמצא BUYME ALL.")
    except: pass

def run_full_report(chat_id):
    send_telegram(chat_id, "📄 מפיק דוח... זה עשוי לקחת כמה שניות.")
    # (כאן תבוא הלוגיקה של ה-Full Report שכבר יש לך)
    # לצורך הקיצור, נפעיל את הפונקציה המקורית שלך...
    pass

def handle_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if not res.get("result"): continue
            
            for update in res["result"]:
                last_id = update["update_id"]
                
                # טיפול בלחיצות על כפתורי Inline
                if "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]
                    data = cq["data"]
                    
                    if data == "run_check":
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    elif data == "run_report":
                        send_telegram(chat_id, "📄 מפיק דוח מלא...")
                        # קריאה לפונקציית הדו"ח המלא שלך
                    elif data == "show_help":
                        help_text = (
                            "📖 <b>הסבר על הפקודות:</b>\n\n"
                            "🔍 <b>בדיקה מהירה:</b> סורק רק את BUYME ALL בקטגוריות הראשיות.\n"
                            "📄 <b>דוח מלאי:</b> סריקה עמוקה של כל המתנות הקיימות (יותר זמן).\n"
                            "⏰ <b>ניהול זמנים:</b> ניתן להוסיף זמני סריקה אוטומטיים.\n"
                            "➕ <b>איך מוסיפים זמן?</b> פשוט שלח הודעה בפורמט: <code>add 16:30</code>"
                        )
                        send_telegram(chat_id, help_text)
                    elif data == "manage_times":
                        times = ", ".join(SCHEDULED_TIMES)
                        send_telegram(chat_id, f"⏰ <b>זמני סריקה נוכחיים:</b>\n{times}\n\nלהוספה שלח: <code>add HH:MM</code>")
                    elif data == "refresh_status":
                        now = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
                        send_telegram(chat_id, f"✅ הבוט מחובר.\n🕒 שעה: {now}", reply_markup=get_main_menu())

                # טיפול בהודעות טקסט
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"].lower()

                    if text == "/start" or text == "ok":
                        send_telegram(chat_id, "👋 ברוך הבא לבוט המלאי המשודרג!", reply_markup=get_main_menu())
                    
                    elif text.startswith("add "):
                        new_time = text.replace("add ", "").strip()
                        if len(new_time) == 5 and ":" in new_time:
                            SCHEDULED_TIMES.append(new_time)
                            SCHEDULED_TIMES.sort()
                            send_telegram(chat_id, f"✅ הזמן <b>{new_time}</b> נוסף בהצלחה!")
                        else:
                            send_telegram(chat_id, "❌ פורמט לא תקין. השתמש ב: add 14:00")

        except: time.sleep(5)

def run_scheduler():
    last_min = -1
    while True:
        now = datetime.now(ISRAEL_TZ)
        now_str = now.strftime("%H:%M")
        if now_str in SCHEDULED_TIMES and now.minute != last_min:
            last_min = now.minute
            send_telegram(MY_CHAT_ID, f"🕒 <b>תזמון {now_str}:</b> מתחיל סריקה...")
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_updates()
