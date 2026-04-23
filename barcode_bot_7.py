import requests
import random
from fpdf import FPDF
import os
import re
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- הגדרות ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
STRAUSS_URL = "https://www.strauss-group.co.il/wp-content/themes/retlehs-roots-43f44a4/assets/ajax/products_autocomplete.php"
# ב-Render משתמשים בתיקיית /tmp/ לקבצים זמניים
PDF_PATH = "/tmp/list.pdf"

# --- שרת בריאות למניעת כיבוי הבוט ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- לוגיקה ---
def fix_hebrew(text):
    if not text: return ""
    # היפוך טקסט לעברית פשוטה ב-PDF
    return text[::-1] if any("\u0590" <= c <= "\u05ea" for c in text) else text

def clean_barcode(raw_barcode):
    return re.sub(r'\D', '', str(raw_barcode).split("_")[0])

def fetch_strauss():
    try:
        res = requests.get(STRAUSS_URL, timeout=10).json()
        return [{"barcode": str(i.get('post_name', '')), "name": str(i.get('post_title', ''))} for i in res]
    except: return []

def fetch_from_chp(keyword, limit):
    try:
        url = "https://chp.co.il/autocompletion/product_extended"
        params = {"term": keyword, "shopping_address_city_id": "8400"}
        res = requests.get(url, params=params, timeout=5).json()
        return [{"name": i.get('label', '').split('<br>')[0].replace('<b>','').replace('</b>',''), 
                 "barcode": clean_barcode(i.get('barcode', ''))} for i in res[:limit]]
    except: return []

def create_pdf(products):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12) # פונט מובנה בלבד
        pdf.cell(200, 10, txt=fix_hebrew("רשימת ברקודים"), ln=1, align='C')
        
        for i, p in enumerate(products, 1):
            name = fix_hebrew(p['name'][:40])
            barcode = p['barcode']
            pdf.cell(0, 10, txt=f"{i}. {name} : {barcode}", ln=1, align='R')
        
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF creation failed: {e}")
        return False

def handle_bot():
    print("--- Bot starting ---")
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            updates = requests.get(url, timeout=30).json()
            
            if updates.get("result"):
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        msg_text = update["message"].get("text", "")
                        
                        # שלב 1: הודעת אישור
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      data={'chat_id': chat_id, 'text': "Generating PDF... please wait."})
                        
                        # שלב 2: איסוף דאטה
                        data = fetch_strauss()
                        random.shuffle(data)
                        data = data[:40]
                        
                        if msg_text == "2":
                            data += fetch_from_chp("אסם", 10)
                        
                        # שלב 3: יצירה ושליחה
                        if create_pdf(data):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
                            print(f"PDF sent to {chat_id}")
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "Error generating PDF."})
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
