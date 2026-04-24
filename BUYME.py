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
SYSTEM_TIMES = ["08:00", "12:20", "12:40", "15:00"] # זמנים קבועים
manual_times = [] # זמנים ידניים

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
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_bottom_keyboard():
    """יוצר את הכפתורים שיופיעו תמיד למטה במקום המקלדת"""
    return {
        "keyboard": [
            [{"text": "🔍 בדיקה מהירה"}, {"text": "📄 דוח מלאי"}],
            [{"text": "⏰ ניהול זמנים"}, {"text": "❓ עזרה"}]
        ],
        "resize_keyboard": True,
        "persistent": True # שומר שהמקלדת לא תיעלם
    }

def get_times_status():
    sys_list = ", ".join(SYSTEM_TIMES) if SYSTEM_TIMES else "אין"
    man_list = ", ".join(manual_times) if manual_times else "אין זמנים ידניים"
    text = (
        "⏰ <b>סטטוס זמני סריקה:</b>\n\n"
        f"📌 <b>מערכת:</b> <code>{sys_list}</code>\n"
        f"✏️ <b>ידני:</b> <code>{man_list}</code>\n\n"
        "להוספה שלח הודעה: <code>add 14:30</code>"
    )
    return text

# --- לוגיקת סריקה ---
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
                        send_telegram(chat_id, "🤖 המערכת מוכנה. השתמש בכפתורים למטה:", reply_markup=get_bottom_keyboard())
                    
                    elif text == "🔍 בדיקה מהירה":
                        send_telegram(chat_id, "⏳ מבצע בדיקה מהירה...")
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    
                    elif text == "📄 דוח מלאי":
                        send_telegram(chat_id, "📄 מפיק דוח מלאי... (פעולה זו לוקחת זמן)")
                        # קריאה לפונקציית הדוח המלא שלך
                        
                    elif text == "⏰ ניהול זמנים":
                        # כאן נשתמש בכפתור inline בתוך הצאט למחיקה
                        markup = {"inline_keyboard": [[{"text": "🗑️ נקה זמנים ידניים", "callback_data": "clear_manual"}]]}
                        send_telegram(chat_id, get_times_status(), reply_markup=markup)
                    
                    elif text == "❓ עזרה":
                        send_telegram(chat_id, "💡 <b>עזרה:</b>\n\n1. השתמש בכפתורים למטה לבדיקה ידנית.\n2. להוספת זמן אוטומטי, כתוב הודעה: <code>add 15:00</code>")

                    elif text.lower().startswith("add "):
                        t_val = text.lower().replace("add ", "").strip()
                        try:
                            time.strptime(t_val, '%H:%M')
                            if t_val not in manual_times:
                                manual_times.append(t_val)
                                manual_times.sort()
                                send_telegram(chat_id, f"✅ הזמן <b>{t_val}</b> נוסף בהצלחה!")
                            else:
                                send_telegram(chat_id, "⚠️ הזמן כבר קיים.")
                        except:
                            send_telegram(chat_id, "❌ פורמט לא תקין. דוגמה: <code>add 14:00</code>")

                # טיפול בלחיצה על "מחיקה" (Inline)
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
            send_telegram(MY_CHAT_ID, f"🕒 <b>סריקה מתוזמנת ({now_str}):</b>")
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_updates()
