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
SYSTEM_TIMES = ["08:00", "12:00", "20:00", "00:00"] # זמנים קבועים בקוד
manual_times = [] # זמנים שאתה תוסיף ידנית

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

def get_main_menu():
    return {
        "inline_keyboard": [
            [{"text": "🔍 בדיקה מהירה", "callback_data": "run_check"}, {"text": "📄 דוח מלאי", "callback_data": "run_report"}],
            [{"text": "⏰ ניהול זמנים", "callback_data": "manage_times"}, {"text": "❓ עזרה", "callback_data": "show_help"}],
            [{"text": "🔄 רענן סטטוס", "callback_data": "refresh_status"}]
        ]
    }

# --- לוגיקת הוספת זמנים ---
def add_manual_time(chat_id, time_str):
    """פונקציה חדשה להוספת זמן עם בדיקות תקינות"""
    try:
        # בדיקה אם הפורמט תקין (HH:MM)
        time.strptime(time_str, '%H:%M')
        
        if time_str in SYSTEM_TIMES or time_str in manual_times:
            send_telegram(chat_id, f"⚠️ הזמן <b>{time_str}</b> כבר קיים במערכת.")
        else:
            manual_times.append(time_str)
            manual_times.sort()
            send_telegram(chat_id, f"✅ הזמן <b>{time_str}</b> נוסף לרשימה הידנית!")
    except ValueError:
        send_telegram(chat_id, "❌ פורמט זמן לא תקין. נא לשלוח בצורה הבאה: <code>add 14:30</code>")

def get_times_status():
    """מפיק הודעה מעוצבת של כל הזמנים"""
    sys_list = ", ".join(SYSTEM_TIMES) if SYSTEM_TIMES else "אין"
    man_list = ", ".join(manual_times) if manual_times else "אין זמנים ידניים"
    
    text = (
        "⏰ <b>פירוט זמני סריקה:</b>\n\n"
        f"📌 <b>זמני מערכת (קבוע):</b>\n<code>{sys_list}</code>\n\n"
        f"✏️ <b>זמנים ידניים:</b>\n<code>{man_list}</code>\n\n"
        " כדי להוסיף: <code>add HH:MM</code> (למשל add 19:00)\n"
        " כדי למחוק הכל: לחץ על הכפתור למטה."
    )
    return text

# --- סורק ודוחות ---
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
    except: send_telegram(chat_id, "❌ שגיאה בחיבור לשרת.")

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
                
                # כפתורי Inline
                if "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]
                    data = cq["data"]
                    
                    if data == "run_check":
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    elif data == "manage_times":
                        markup = {"inline_keyboard": [[{"text": "🗑️ מחק זמנים ידניים", "callback_data": "clear_manual"}]]}
                        send_telegram(chat_id, get_times_status(), reply_markup=markup)
                    elif data == "clear_manual":
                        manual_times.clear()
                        send_telegram(chat_id, "🗑️ כל הזמנים הידניים נמחקו.")
                    elif data == "show_help":
                        send_telegram(chat_id, "💡 <b>עזרה:</b>\nשליחת <code>add 15:00</code> תוסיף זמן סריקה.\nהכפתורים למטה יפעילו סריקות מיידיות.")
                    elif data == "refresh_status":
                        now = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
                        send_telegram(chat_id, f"✅ בוט פעיל\n🕒 שעה: {now}", reply_markup=get_main_menu())

                # הודעות טקסט
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"].strip().lower()

                    if text in ["/start", "ok"]:
                        send_telegram(chat_id, "🤖 ברוך הבא למערכת הסריקה!", reply_markup=get_main_menu())
                    elif text.startswith("add "):
                        t_val = text.replace("add ", "").strip()
                        add_manual_time(chat_id, t_val)

        except: time.sleep(5)

# --- המתזמן ---
def run_scheduler():
    last_min = -1
    while True:
        now = datetime.now(ISRAEL_TZ)
        now_str = now.strftime("%H:%M")
        # בדיקה בשתי הרשימות
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
