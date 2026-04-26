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
SYSTEM_TIMES = ["08:00", "08:10", "08:20", "12:20", "12:40", "15:00"] 
manual_times = [] 
user_states = {}

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

# --- לוגיקת סריקה חדשה ואגרסיבית ---
def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json().get('body', {})
    except: 
        return None
    return None

def get_all_items():
    """שואבת את כל הפריטים באופן יסודי, מסננת כפילויות ומחזירה מילון מאוחד"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers = keys["url"], keys["headers"]
        base_payload = keys.get("payload", {})
    except Exception as e:
        print(f"Error loading keys: {e}")
        return {}

    unique_items = {}
    categories = [None, 1003, 1002, 1001, 1004, 1005]
    
    for cat in categories:
        # סורק עד 10 עמודים בכל קטגוריה
        for page in range(0, 10): 
            # העתק עמוק של ה-payload כדי למנוע "זיהום" של נתונים בין בקשות
            payload = json.loads(json.dumps(base_payload))
            
            if cat is not None:
                payload["categoryId"] = cat
            elif "categoryId" in payload:
                del payload["categoryId"]
                
            payload["page"] = page
            payload["requestPage"] = page
            
            body = fetch_data_safely(url, headers, payload)
            if not body: 
                break
                
            items = body.get('gifts') or body.get('items') or []
            if not items:
                break # אם העמוד ריק, אין טעם להמשיך לעמוד הבא בקטגוריה הזו
                
            # שמירה בתוך מילון כדי למנוע פריטים כפולים במערכת
            for item in items:
                title = item.get('title') or item.get('name') or "Unknown"
                unique_items[title] = item
                
            time.sleep(0.3) # השהייה קלה למניעת חסימה
            
    return unique_items

def run_stock_monitor(chat_id, silent=False):
    try:
        items_dict = get_all_items()
        found = False
        
        for title, item_data in items_dict.items():
            name_upper = title.upper()
            # חיפוש רחב לכל וריאציה של ביימי
            if "BUYME" in name_upper or "BUY ME" in name_upper or "ביימי" in name_upper:
                send_telegram(chat_id, f"🔥 <b>נמצא מלאי ל: {title}!</b> 🔥")
                found = True
                
        if not found and not silent:
            send_telegram(chat_id, f"🔍 סרקתי <b>{len(items_dict)}</b> מתנות שונות בקטלוג.\nלא נמצא BUYME כרגע.")
    except Exception as e: 
        send_telegram(chat_id, "❌ שגיאה בסריקה.")

def run_full_report(chat_id):
    send_telegram(chat_id, "⏳ שואב נתונים מכל הקטגוריות... (זה עשוי לקחת כמה שניות)")
    try:
        items_dict = get_all_items()
        
        if not items_dict:
            send_telegram(chat_id, "⚠️ לא נמצאו פריטים כלל. ייתכן שהטוקן של שטראוס פג תוקף! רענן את הקובץ.")
            return
            
        msg = f"<b>📋 דוח מלאי (נסרקו {len(items_dict)} פריטים שונים):</b>\n"
        for title in sorted(items_dict.keys()):
            s = items_dict[title].get('stockCount')
            msg += f"{'🟢' if s and s > 0 else '🔴'} <b>{title}</b> ({s if s is not None else '?'})\n"
            
        # פיצול הדוח אם הוא ארוך מדי עבור טלגרם
        if len(msg) > 4000:
            send_telegram(chat_id, msg[:4000] + "\n\n...[הדוח ארוך מדי ונחתך, אבל הסריקה מלאה]...")
        else:
            send_telegram(chat_id, msg)
            
    except Exception as e: 
        send_telegram(chat_id, "❌ שגיאה בדוח.")

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
                        clean_time = text.replace(":", "")
                        if len(clean_time) == 4 and clean_time.isdigit():
                            new_t = f"{clean_time[:2]}:{clean_time[2:]}"
                            if new_t not in manual_times:
                                manual_times.append(new_t); manual_times.sort()
                                send_telegram(chat_id, f"✅ הזמן <b>{new_t}</b> נוסף לרשימה הידנית.")
                            else: send_telegram(chat_id, "⚠️ כבר קיים.")
                        else: send_telegram(chat_id, "❌ פורמט שגוי. שלח 4 ספרות (למשל 1400).")
                        user_states[chat_id] = None
                        continue

                    if text in ["/start", "ok", "OK"]:
                        send_telegram(chat_id, "🤖 מערכת מוכנה:", reply_markup=get_bottom_keyboard())
                    elif text == "🔍 בדיקה מהירה":
                        threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                    elif text == "📄 דוח מלאי":
                        threading.Thread(target=run_full_report, args=(chat_id,)).start()
                    elif text == "🤖 סטטוס בוט":
                        send_telegram(chat_id, get_bot_status())
                    elif text == "⏰ ניהול זמנים":
                        msg = f"⏰ <b>זמנים נוכחיים:</b>\n📌 מערכת: {', '.join(SYSTEM_TIMES)}\n✏️ ידני: {', '.join(manual_times) if manual_times else 'אין'}"
                        markup = {"inline_keyboard": [
                            [{"text": "➕ הוסף זמן חדש", "callback_data": "start_add"}],
                            [{"text": "🗑️ נקה ידני", "callback_data": "clear_man"}]
                        ]}
                        send_telegram(chat_id, msg, reply_markup=markup)
                    elif text == "❓ עזרה":
                        send_telegram(chat_id, "💡 <b>עזרה:</b>\nהשתמש בכפתורים למטה. להוספת זמן לחץ על 'ניהול זמנים'.")

                if "callback_query" in update:
                    cq = update["callback_query"]; chat_id = cq["message"]["chat"]["id"]
                    if cq["data"] == "start_add":
                        user_states[chat_id] = "add_time"
                        send_telegram(chat_id, "⌨️ <b>שלח לי את השעה להוספה:</b>\n(למשל: 14:00 או 1400)")
                    elif cq["data"] == "clear_man":
                        manual_times.clear()
                        send_telegram(chat_id, "🗑️ הזמנים הידניים נמחקו.")

        except: time.sleep(5)

def run_scheduler():
    last_min = -1
    while True:
        now = datetime.now(ISRAEL_TZ)
        now_str = now.strftime("%H:%M")
        if now_str in (SYSTEM_TIMES + manual_times) and now.minute != last_min:
            last_min = now.minute
            send_telegram(MY_CHAT_ID, f"🕒 <b>סריקה מתוזמנת ({now_str}):</b>")
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_updates()
