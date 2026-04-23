import requests
import random
from fpdf import FPDF
import os
import re
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# --- פרטי הבוט ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
OUTPUT_FOLDER = "PDF_OUTPUTS"

# שרת בריאות כדי ש-Render לא יכבה את הבוט
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health server started on port {port}")
    server.serve_forever()

# פונקציה לסדר את הטקסט בעברית (היפוך לוגי)
def fix_hebrew(text):
    if not text: return ""
    # הופך את סדר האותיות רק אם יש עברית במחרוזת
    if any("\u0590" <= c <= "\u05ea" for c in text):
        return text[::-1]
    return text

def clean_barcode(raw_barcode):
    if not raw_barcode: return "7290000000000"
    raw_barcode = str(raw_barcode)
    return re.sub(r'\D', '', raw_barcode.split("_")[0]) if "_" in raw_barcode else re.sub(r'\D', '', raw_barcode)

def fetch_products():
    url = "https://chp.co.il/autocompletion/product_extended"
    headers = {'User-Agent': 'Mozilla/5.0'}
    keywords = ["עלית", "שטראוס", "אסם", "תנובה"]
    all_products = []
    
    for kw in keywords:
        try:
            params = {"term": kw, "shopping_address_city_id": "8400"}
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                for item in res.json()[:15]:
                    name = item.get('label', '').split('<br>')[0].replace('<b>','').replace('</b>','').strip()
                    barcode = clean_barcode(str(item.get('barcode', '')))
                    if len(barcode) >= 8:
                        all_products.append({"name": name, "barcode": barcode})
        except: continue
    return all_products

def create_pdf(products, filepath):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # כותרת
    pdf.cell(200, 10, txt=fix_hebrew("רשימת ברקודים"), ln=1, align='C')
    pdf.ln(5)

    for i, p in enumerate(products, 1):
        # שם מוצר מתוקן + ברקוד
        line_text = f"{i}. {fix_hebrew(p['name'])} : {p['barcode']}"
        pdf.cell(0, 10, txt=line_text, ln=1, align='R')
    
    pdf.output(filepath)

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': chat_id, 'text': text})

def handle_bot():
    print("--- Telegram Bot Started ---")
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        msg_text = update["message"].get("text", "").upper()
                        
                        # בדיקת "OK"
                        if msg_text == "OK":
                            send_telegram_msg(chat_id, "I am alive and working! Sending PDF now...")
                        
                        print(f"Processing request for {chat_id}...")
                        
                        if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                        path = os.path.join(OUTPUT_FOLDER, "barcodes.pdf")
                        
                        data = fetch_products()
                        create_pdf(data, path)
                        
                        with open(path, 'rb') as f:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                          data={'chat_id': chat_id}, files={'document': f})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
