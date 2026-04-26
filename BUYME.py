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

# --- ניהול זמנים ומצבים ---
SYSTEM_TIMES = ["08:00", "08:07", "08:15", "12:20", "12:40", "15:00"] 
manual_times = [] 
user_states = {}

# --- שרת בריאות (Health Check) לשמירה על השרת פעיל ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Active")
        
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def keep_awake():
    # כתובת האפליקציה שלך ב-Render למניעת שינה
    url = "https://nine2-de7r.onrender.com/"
    while True:
        try:
            time.sleep(600)
            requests.get(url, timeout=10)
        except:
            pass

# --- פונקציות עזר לטלגרם ---
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

def get_bot_status():
    now = datetime.now(ISRAEL_TZ)
    all_times = sorted(list(set(SYSTEM_TIMES + manual_times)))
    next_scan = "לא מוגדר"
    for t in all_times:
        t_hour, t_min = map(int, t.split(':'))
        scan_time = now.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
        if scan_time > now:
            diff = scan_time - now
            next_scan = f"{t} (בעוד {int(diff.total_seconds() / 60)} דק')"
            break
    
    return (
        f"<b>🤖 סטטוס מערכת:</b>\n"
        f"🕒 שעה: <code>{now.strftime('%H:%M:%S')}</code>\n"
        f"📅 תזמונים: {', '.join(all_times)}\n"
        f"⏳ סריקה קרובה: <b>{next_scan}</b>"
    )

# --- לוגיקת סריקה משולבת ואגרסיבית ---
def fetch_data_safely(url, headers, payload):
    # ניקוי כותרות שעלולות לחסום בקשות אוטומטיות
    headers.pop("content-length", None)
    headers.pop("accept-encoding", None)
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json().get('body', {})
    except: 
        return None
    return None

def get_all_items():
    """שואבת את כל הפריטים בשיטה המשולבת (שמות ומלאי ישיר)"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url = keys["url"]
        headers = keys["headers"]
        # וידוא שמתחילים מעמוד 0 או 1 בהתאם ל-JSON המקורי
        base_payload = keys.get("payload", {})
    except Exception as e:
        print(f"Error loading keys: {e}")
        return {}

    unique_items = {}
    # קטגוריה 1000 היא המרכזית למתנות שוקולד/מארזים
    categories = [None, 1000, 1003, 1002, 1001, 0]
    
    for cat in categories:
        for page in range(0, 8): # סריקת עד 8 עמודים לקטגוריה
            payload = json.loads(json.dumps(base_payload))
            
            if cat is not None:
                payload["categoryId"] = cat
            
            # עדכון עמודים בשיטה כפולה (למניעת אי-הבנה של השרת)
            payload["page"] = page
            payload["requestPage"] = page
            
            body = fetch_data_safely(url, headers, payload)
            if not body: break
                
            # הלוגיקה המנצחת: בדיקה של gifts וגם items
            items = body.get('gifts') or body.get('items') or []
            if not items: break
                
            for item in items:
                # חילוץ שם משופר (גם מתוך תת-אובייקט gift אם קיים)
                title = item.get('title') or item.get('name')
                if not title and item.get('gift'):
                    title = item.get('gift', {}).get('title') or item.get('gift', {}).get('name')
                
                title = title or "Unknown Product"
                
                # חילוץ מלאי ישיר מהקטלוג (השדה שפיצחנו)
                stock = item.get('stockCount') or item.get('quantity')
                if stock is None and item.get('gift'):
                    stock = item.get('gift', {}).get('stockCount') or item.get('gift', {}).get('quantity')
                
                # שמירה במילון (מונע כפילויות)
                unique_items[title] = {
                    "stock": stock,
                    "points": item.get('points') or item.get('gift', {}).get('points', 0),
                    "id": item.get('id')
                }
            
            time.sleep(0.3)
            
    return unique_items

def run_stock_monitor(chat_id, silent=False):
    try:
        items_dict = get_all_items()
        found = False
        
        for title, data in items_dict.items():
            name_upper = title.upper()
            stock = data.get('stock')
            
            # בדיקת BuyMe או כל פריט שיש לו מלאי חיובי (אופציונלי)
            if "BUYME" in name_upper or "BUY ME" in name_upper or "ביימי" in name_upper:
                if stock is not None and stock > 0:
                    send_telegram(chat_id, f"🔥 <b>נמצא מלאי ל: {title}!</b> 🔥\nכמות: <code>{stock}</code>")
                    found = True
                
        if not found and not silent:
            send_telegram(chat_id, f"🔍 סריקה הושלמה (נסרקו <b>{len(items_dict)}</b> פריטים).\nלא נמצא BUYME במלאי כרגע.")
    except Exception as e: 
        send_telegram(chat_id, "❌ שגיאה בסריקה.")

def run_full_report(chat_id):
    send_telegram(chat_id, "⏳ שואב דוח מלאי מפורט מכל הקטגוריות...")
    try:
        items_dict = get_all_items()
        if not items_dict:
            send_telegram(chat_id, "⚠️ לא נמצאו פריטים. ייתכן והטוקן פג תוקף.")
            return
            
        msg = f"<b>📋 דוח מלאי ({len(items_dict)} פריטים):</b>\n"
        # מיון לפי שם
        for title in sorted(items_dict.keys()):
            data = items_dict[title]
            s = data.get('stock')
            pts = data.get('points')
            
            # עיצוב שורה: אימוג'י לפי מלאי
            icon = "🟢" if (s is not None and s > 0) else "🔴"
            stock_str = s if s is not None else "?"
            msg += f"{icon} <b>{title}</b> | מלאי: <code>{stock_str}</code> | נק': {pts}\n"
            
            # פיצול הודעות ארוכות (טלגרם מגבילה ל-4096 תווים)
            if len(msg) > 3500:
                send_telegram(chat_id, msg)
                msg = ""

        if msg:
            send_telegram(chat_id, msg)
            
    except Exception as e: 
        send_telegram(chat_id, f"❌ שגיאה בהפקת דוח: {e}")

# --- טיפול בעדכונים מטלגרם ---
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
                        clean_time = text.replace(":", "")
                        if len(clean_time) == 4 and clean_time.isdigit():
                            new_t = f"{clean_time[:2]}:{clean_time[2:]}"
                            if new_t not in manual_times:
                                manual_times.append(new_t); manual_times.sort()
                                send_telegram(chat_id, f"✅ הזמן <b>{new_t}</b> נוסף לסריקות.")
                            else: send_telegram(chat_id, "⚠️ קיים כבר.")
                        else: send_telegram(chat_id, "❌ שלח 4 ספרות (למשל 1200).")
                        user_states[chat_id] = None
                        continue

                    if text in ["/start", "ok", "OK", "היי"]:
                        send_telegram(chat_id, "🤖 בוט שטראוס מוכן לעבודה!", reply_markup=get_bottom_keyboard())
                    elif text == "🔍 בדיקה מהירה":
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    elif text == "📄 דוח מלאי":
                        threading.Thread(target=run_full_report, args=(chat_id,)).start()
                    elif text == "🤖 סטטוס בוט":
                        send_telegram(chat_id, get_bot_status())
                    elif text == "⏰ ניהול זמנים":
                        msg = f"⏰ <b>זמני סריקה:</b>\n📌 מערכת: {', '.join(SYSTEM_TIMES)}\n✏️ ידני: {', '.join(manual_times) if manual_times else 'אין'}"
                        markup = {"inline_keyboard": [
                            [{"text": "➕ הוסף זמן", "callback_data": "start_add"}],
                            [{"text": "🗑️ נקה ידני", "callback_data": "clear_man"}]
                        ]}
                        send_telegram(chat_id, msg, reply_markup=markup)
                    elif text == "❓ עזרה":
                        send_telegram(chat_id, "השתמש בכפתורים למטה לסריקת מלאי.\nבמידה ומופיע '?', הטוקן ב-JSON כנראה פג תוקף.")

                if "callback_query" in update:
                    cq = update["callback_query"]; chat_id = cq["message"]["chat"]["id"]
                    if cq["data"] == "start_add":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "שלח את השעה (למשל 10:00):")
                    elif cq["data"] == "clear_man":
                        manual_times.clear()
                        send_telegram(chat_id, "🗑️ זמנים ידניים נמחקו.")

        except: time.sleep(5)

# --- מתזמן סריקות ---
def run_scheduler():
    last_min = -1
    while True:
        now = datetime.now(ISRAEL_TZ)
        now_str = now.strftime("%H:%M")
        if now_str in (SYSTEM_TIMES + manual_times) and now.minute != last_min:
            last_min = now.minute
            send_telegram(MY_CHAT_ID, f"🕒 <b>סריקה אוטומטית ({now_str}):</b>")
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
        time.sleep(20)

if __name__ == "__main__":
    # הפעלת שירותי רקע
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    # הפעלת קבלת פקודות
    handle_updates()
