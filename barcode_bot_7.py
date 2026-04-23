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
DATA_FILE = "strauss.txt"
PDF_PATH = "/tmp/barcodes.pdf"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def safe_text(text):
    """הופך עברית ומנקה תווים שאינם לטיניים/עבריים למניעת קריסת השרת"""
    if not text: return "Product"
    # משאיר רק אותיות עבריות, מספרים וסימני פיסוק בסיסיים
    clean = re.sub(r'[^\u0590-\u05ea0-9\s\-\.\,\/]', '', text)
    if any("\u0590" <= c <= "\u05ea" for c in clean):
        return clean[::-1] # היפוך עברית ויזואלית
    return clean

def load_data():
    """טוען נתונים מהקובץ המקומי strauss.txt"""
    products = []
    if not os.path.exists(DATA_FILE): return products
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "," in line:
                parts = line.split(",", 1)
                products.append({"barcode": parts[0].strip(), "name": parts[1].strip()})
    return products

def generate_pdf_safe(selected):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10) # פונט בטוח לכל מערכת
        
        pdf.cell(200, 10, txt=safe_text("רשימת ברקודים"), ln=1, align='C')
        pdf.ln(5)

        for i, p in enumerate(selected, 1):
            name = safe_text(p['name'][:35])
            barcode = p['barcode']
            try:
                # כתיבת השורה: ברקוד משמאל ושם מימין
                line = f"{i}. {barcode} | {name}"
                pdf.cell(0, 8, txt=line, ln=1)
            except:
                # אם שם המוצר עדיין גורם לשגיאה - נדפיס רק ברקוד
                pdf.cell(0, 8, txt=f"{i}. {barcode} | Error in Name", ln=1)
            
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF Error: {e}")
        return False

def bot_loop():
    last_id = 0
    print("Bot is Active...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        
                        db = load_data()
                        if not db:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "קובץ הנתונים חסר בשרת."})
                            continue
                        
                        random.shuffle(db)
                        # יצירת PDF עם 60 מוצרים
                        if generate_pdf_safe(db[:60]):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "שגיאה טכנית ביצירת הקובץ."})
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    bot_loop()
