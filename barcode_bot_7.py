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
# קישור ישיר (Raw) לקובץ המוצרים שלך ב-GitHub
STRAUSS_FILE_URL = "https://raw.githubusercontent.com/hsien6914-ops/92/main/strauss.txt"
PDF_PATH = "/tmp/list.pdf"

# --- שרת בריאות למניעת כיבוי הבוט ב-Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- לוגיקה לטיפול בטקסט ועברית ---
def fix_hebrew_for_pdf(text):
    """הופך את הטקסט כדי שיוצג נכון ב-PDF ללא פונט עברי מיוחד"""
    if not text: return ""
    # הסרת תווים שאינם נתמכים ב-Latin-1 כדי למנוע קריסה
    clean_text = "".join([c for c in text if ord(c) < 256 or 0x0590 <= ord(c) <= 0x05EA])
    if any("\u0590" <= c <= "\u05ea" for c in clean_text):
        return clean_text[::-1] # היפוך לוגי
    return clean_text

def fetch_local_products():
    """מושך את רשימת המוצרים מהקובץ שהעלית ל-GitHub"""
    products = []
    try:
        response = requests.get(STRAUSS_FILE_URL, timeout=10)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if "," in line:
                    barcode, name = line.split(",", 1)
                    products.append({
                        "barcode": barcode.strip(),
                        "name": name.strip()
                    })
        print(f"Loaded {len(products)} products from GitHub file.")
    except Exception as e:
        print(f"Error loading file: {e}")
    return products

def create_pdf(products):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10) # פונט יציב בשרתים
        
        # כותרת
        title = fix_hebrew_for_pdf("רשימת ברקודים מעודכנת")
        pdf.cell(200, 10, txt=title, ln=1, align='C')
        pdf.ln(5)
        
        # בניית הטבלה
        pdf.set_font("Courier", size=9)
        for i, p in enumerate(products, 1):
            name = fix_hebrew_for_pdf(p['name'][:45])
            barcode = p['barcode']
            line = f"{i:02}. {name:<45} | {barcode:>15}"
            pdf.cell(0, 8, txt=line, ln=1)
            
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF error: {e}")
        return False

def handle_bot():
    last_update_id = 0
    print("Bot is listening...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        
                        # הודעת טקסט מיידית
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      data={'chat_id': chat_id, 'text': "מושך מוצרים מקובץ ה-GitHub ושולח PDF..."})
                        
                        # טעינת נתונים
                        all_products = fetch_local_products()
                        if not all_products:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "שגיאה בטעינת הקובץ."})
                            continue
                        
                        random.shuffle(all_products)
                        selected = all_products[:60] # לוקח 60 מוצרים אקראיים
                        
                        if create_pdf(selected):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
