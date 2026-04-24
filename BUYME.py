import requests
import json
import time
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
# טוקן ו-ID (משוך מהגדרות Render או הגדר ידנית כאן)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7538452733:AAE4MZLNJHX-afRgTbepyK3aQXT5zDHNlaU")
KEYS_FILE = "strauss_keys.json"
MY_CHAT_ID = "634863346" 

# רשימת זמנים מעודכנת (מתוקנת לפי השגיאה הקודמת)
SCHEDULED_TIMES = ["08:00", "11:41", "11:49", "13:43", "13:48", "13:50", "13:55", "14:00", "15:00"]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def send_telegram_html(chat_id, html_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': html_text, 'parse_mode': 'HTML'}, timeout=15)
    except: pass

def fetch_data_safely(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get('body', {})
        return None
    except: return None

def run_stock_monitor(chat_id_to_alert, silent_if_not_found=False):
    """בדיקת BUYME ALL"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        found = False
        
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(2):
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                items = body.get('gifts') or body.get('items') or []
                for item in items:
                    name = (item.get('title') or item.get('name') or "").upper()
                    if "BUYME ALL" in name:
                        send_telegram_html(chat_id_to_alert, "🔥 <b>נמצא מלאי ל-BUYME ALL!</b> 🔥")
                        found = True; break
                if found: break
            if found: break
        
        # אם silent_if_not_found הוא False, הוא ישלח הודעה גם כשלא מצא כלום
        if not found and not silent_if_not_found:
            send_telegram_html(chat_id_to_alert, "🔍 סריקה מתוזמנת הסתיימה: לא נמצא BUYME ALL.")
    except Exception as e:
        if not silent_if_not_found:
            send_telegram_html(chat_id_to_alert, f"❌ תקלה בבדיקה: {e}")

def run_full_report(chat_id):
    """דוח מלאי מפורט (/check2)"""
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        url, headers, payload = keys["url"], keys["headers"], keys.get("payload", {})
        all_gifts = {}
        for cat in [None, 1003, 1002, 1001, 1004, 1005]:
            payload["categoryId"] = cat
            for page in range(4):
                payload["requestPage"] = page
                body = fetch_data_safely(url, headers, payload)
                if not body: continue
                items = body.get('gifts') or body.get('items') or []
                for item in items:
                    name = item.get('title') or item.get('name') or "Unknown"
                    stock = item.get('stockCount')
                    all_gifts[name] = stock
                time.sleep(0.2)
        
        if all_gifts:
            msg = "<b>📋 דוח מלאי מלא:</b>\n\n"
            for name in sorted(all_gifts.keys()):
                stock = all_gifts[name]
                status = f"🟢 <b>{name}</b> (מלאי: {stock})" if stock != 0 else f"🔴 <s>{name}</s> (אזל)"
                msg += status + "\n"
            send_telegram_html(chat_id, msg)
    except: pass

def run_scheduler():
    """מנגנון התזמון - בודק שעה בכל דקה"""
    print(f"Scheduler is running for: {SCHEDULED_TIMES}")
    while True:
        now = datetime.now().strftime("%H:%M")
        if now in SCHEDULED_TIMES:
            # הגדרתי False כדי שתראה הודעה בטלגרם בכל מקרה (לבדיקה)
            threading.Thread(target=run_stock_monitor, args=(MY_CHAT_ID, False)).start()
            time.sleep(61) # מונע הרצה כפולה
        time.sleep(30)

def handle_bot():
    global SCHEDULED_TIMES
    last_id = 0
    print("Bot is listening for messages...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "").strip()

                        if text == "/check":
                            send_telegram_html(chat_id, "⏳ בודק BUYME ALL...")
                            threading.Thread(target=run_stock_monitor, args=(chat_id, False)).start()
                        
                        elif text == "/check2":
                            send_telegram_html(chat_id, "📄 מפיק דוח מלא...")
                            threading.Thread(target=run_full_report, args=(chat_id,)).start()

                        elif text.upper() == "OK":
                            now_str = datetime.now().strftime("%H:%M:%S")
                            sched_str = ", ".join(sorted(list(set(SCHEDULED_TIMES))))
                            menu = (
                                f"<b>🤖 סטטוס בוט (Render)</b>\n"
                                f"🕒 שעה נוכחית: <code>{now_str}</code>\n"
                                f"📅 תזמונים: {sched_str}\n\n"
                                "🔍 /check | 📄 /check2"
                            )
                            send_telegram_html(chat_id, menu)
        except:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    handle_bot()
