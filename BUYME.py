import requests
import json
import time
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import random

# --- הגדרות בוט טלגרם ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
KEYS_FILE = "strauss_keys.json"
STRAUSS_DATA = "strauss.txt"

# --- שרת בריאות (Render) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot & Monitor are running")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- פונקציות עזר לטלגרם ---
def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': chat_id, 'text': text})

# --- לוגיקת סורק המלאי (Monitor) ---
def run_stock_monitor(chat_id_to_alert):
    """סורק מלאי ושולח התראה לטלגרם אם נמצא BUYME ALL"""
    print("--- Stock Monitor Started ---")
    
    if not os.path.exists(KEYS_FILE):
        print(f"Error: {KEYS_FILE} not found!")
        return

    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys["url"]
        headers = keys["headers"]
        base_payload = keys.get("payload", {})
        categories = [None, 1003, 1002, 1001, 1004, 1005]
        
        found_any = False
        for cat in categories:
            page = 0
            base_payload["categoryId"] = cat
            while page < 5: # הגבלה ל-5 דפים למניעת לופ אינסופי
                base_payload["requestPage"] = page
                try:
                    response = requests.post(url, headers=headers, json=base_payload, timeout=10)
                    if response.status_code != 200: break
                    data = response.json()
                    items = data.get('body', {}).get('gifts') or data.get('body', {}).get('items') or []
                    if not items: break
                    
                    for item in items:
                        name = item.get('title') or item.get('name') or "Unknown"
                        stock = item.get('stockCount')
                        
                        if "BUYME ALL" in name.upper():
                            alert_msg = f"🚨 התראת מלאי קריטית! 🚨\n\nמתנה: {name}\nמלאי: {stock if stock is not None else 'זמין'}\n\nרוץ לקנות!"
                            send_telegram_msg(chat_id_to_alert, alert_msg)
                            found_any = True
                            return # עוצר אחרי מציאה
                    
                    page += 1
                    time.sleep(0.5)
                except: break
        
        if not found_any:
            print("Scan finished - No BUYME ALL found.")
            
    except Exception as e:
        print(f"Monitor error: {e}")

# --- לוגיקת הבוט הראשי (פקודות) ---
def handle_bot():
    last_id = 0
    print("--- Bot is listening ---")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "")

                        if text == "/check":
                            send_telegram_msg(chat_id, "מתחיל סריקת מלאי עבור BUYME ALL... 🔍")
                            # מריץ את הסורק בשרשור נפרד כדי לא לתקוע את הבוט
                            threading.Thread(target=run_stock_monitor, args=(chat_id,)).start()
                        
                        elif text == "OK":
                            send_telegram_msg(chat_id, "הבוט חי וסורק המלאי מוכן! שלח /check לסריקה.")
                        
                        else:
                            send_telegram_msg(chat_id, "שלח 'OK' לבדיקת חיים או /check לסריקת מלאי.")
                            
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # 1. שרת בריאות ל-Render
    threading.Thread(target=run_health_server, daemon=True).start()
    # 2. הרצת הבוט
    handle_bot()
