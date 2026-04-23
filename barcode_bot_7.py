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
PDF_PATH = "/tmp/barcodes_list.pdf"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def clean_for_pdf(text):
    """מנקה תווים שאינם נתמכים ומכין עברית ויזואלית"""
    if not text: return ""
    # השארת רק אותיות עבריות, מספרים ותווים בסיסיים
    clean = "".join([c for c in text if ord(c) < 128 or 0x0590 <= ord(c) <= 0x05EA])
    if any("\u0590" <= c <= "\u05ea" for c in clean):
        return clean[::-1] # היפוך עברית
    return clean

def load_db():
    products = []
    if not os.path.exists(DATA_FILE): return products
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "," in line:
                b, n = line.split(",", 1)
                products.append({"barcode": b.strip(), "name": n.strip()})
    return products

def create_pdf(selected):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        
        pdf.cell(200, 10, txt=clean_for_pdf("רשימת ברקודים"), ln=1, align='C')
        pdf.ln(5)

        for i, p in enumerate(selected, 1):
            name = clean_for_pdf(p['name'][:35])
            barcode = p['barcode']
            # שימוש בפורמט פשוט מאוד למניעת שגיאות
            line_text = f"{i}. {barcode} | {name}"
            try:
                pdf.cell(0, 8, txt=line_text, ln=1)
            except:
                # אם שורה ספציפית נכשלת, מדפיסים רק ברקוד
                pdf.cell(0, 8, txt=f"{i}. {barcode} | Product Name Error", ln=1)
            
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"Internal PDF Error: {e}")
        return False

def main():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            res = requests.get(url, timeout=30).json()
            if res.get("result"):
                for update in res["result"]:
                    last_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        
                        db = load_db()
                        if not db:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "Error: Data file missing."})
                            continue
                        
                        random.shuffle(db)
                        if create_pdf(db[:60]):
                            with open(PDF_PATH, 'rb') as doc:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': doc})
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    main()
