import requests
import random
from fpdf import FPDF
import os
import re
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# --- הגדרות ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
# שימוש בנתיב יחסי לקובץ שנמצא באותו Repository
DATA_FILE = "strauss.txt"
PDF_PATH = "/tmp/barcodes_list.pdf"

# --- שרת בריאות עבור Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- טיפול בעברית וטקסט ---
def reverse_hebrew(text):
    """הופך טקסט עברי לתצוגה נכונה ב-PDF"""
    if not text: return ""
    # ניקוי תווים לא חוקיים למניעת קריסת ה-PDF
    clean_text = "".join([c for c in text if ord(c) < 256 or 0x0590 <= ord(c) <= 0x05EA])
    if any("\u0590" <= c <= "\u05ea" for c in clean_text):
        return clean_text[::-1]
    return clean_text

def load_products_from_file():
    """טוען מוצרים מקובץ ה-strauss.txt המקומי"""
    products = []
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found!")
        return products
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "," not in line: continue
                # פיצול לפי הפסיק הראשון בלבד
                parts = line.split(",", 1)
                barcode = parts[0].strip()
                name = parts[1].strip()
                products.append({"barcode": barcode, "name": name})
    except Exception as e:
        print(f"File reading error: {e}")
    return products

def generate_pdf(selected_products):
    """יוצר קובץ PDF מעוצב ומסודר"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10) # פונט יציב בשרתי ענן
        
        # כותרת העמוד
        pdf.set_font("Courier", 'B', 14)
        pdf.cell(200, 10, txt=reverse_hebrew("רשימת ברקודים - שטראוס"), ln=1, align='C')
        pdf.ln(5)
        
        # כותרות הטבלה
        pdf.set_font("Courier", 'B', 10)
        header = f"{reverse_hebrew('מס'):<4} | {reverse_hebrew('שם מוצר'):<40} | {reverse_hebrew('ברקוד')}"
        pdf.cell(0, 8, txt=header, ln=1)
        pdf.cell(0, 0, txt="-"*75, ln=1)
        pdf.ln(2)

        # רשימת המוצרים
        pdf.set_font("Courier", size=9)
        for i, p in enumerate(selected_products, 1):
            name = reverse_hebrew(p['name'][:38])
            barcode = p['barcode']
            line = f"{i:02}.  | {name:<40} | {barcode}"
            pdf.cell(0, 7, txt=line, ln=1)
            
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF creation error: {e}")
        return False

def bot_main():
    last_update_id = 0
    print("Bot is starting and listening for messages...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            response = requests.get(url, timeout=30).json()
            
            if response.get("result"):
                for update in response["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        
                        # שליחת הודעת סטטוס
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      data={'chat_id': chat_id, 'text': "מעבד את רשימת המוצרים... נא להמתין."})
                        
                        # טעינה ובחירה אקראית של מוצרים
                        db = load_products_from_file()
                        if not db:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "שגיאה: לא נמצאו נתונים בקובץ הטקסט."})
                            continue
                        
                        random.shuffle(db)
                        # יצירת רשימה של 60 מוצרים
                        selection = db[:60]
                        
                        if generate_pdf(selection):
                            with open(PDF_PATH, 'rb') as doc:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': doc})
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "חלה שגיאה ביצירת ה-PDF."})
        except Exception as e:
            print(f"Bot loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # הפעלת שרת הבריאות ברקע למניעת כיבוי על ידי Render
    threading.Thread(target=run_health_server, daemon=True).start()
    bot_main()
