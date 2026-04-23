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
PDF_PATH = "/tmp/list.pdf"

# --- שרת בריאות ---
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
def clean_barcode(raw_barcode):
    return re.sub(r'\D', '', str(raw_barcode).split("_")[0])

def fetch_strauss():
    try:
        res = requests.get(STRAUSS_URL, timeout=10).json()
        return [{"barcode": str(i.get('post_name', '')), "name": str(i.get('post_title', ''))} for i in res]
    except: return []

def create_pdf(products):
    try:
        # שימוש ב-FPDF2
        pdf = FPDF()
        pdf.add_page()
        # שימוש ב-Courier - פונט שתומך בתווים בסיסיים בצורה יציבה יותר
        pdf.set_font("Courier", size=10)
        pdf.cell(200, 10, txt="BARCODE LIST", ln=1, align='C')
        pdf.ln(10)
        
        for i, p in enumerate(products, 1):
            barcode = clean_barcode(p['barcode'])
            # בגלל בעיית הפונטים בעברית ב-Render, נדפיס רק את הברקוד
            # זה מבטיח שה-PDF ייווצר ב-100% הצלחה
            line = f"{i}. Barcode: {barcode}"
            pdf.cell(0, 8, txt=line, ln=1)
        
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF creation error: {e}")
        return False

def handle_bot():
    print("--- Bot starting ---")
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
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      data={'chat_id': chat_id, 'text': "Generating PDF... (Safe Mode - Numbers Only)"})
                        
                        data = fetch_strauss()
                        if not data:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "Failed to fetch data."})
                            continue
                            
                        random.shuffle(data)
                        # ניצור PDF עם 50 מוצרים
                        if create_pdf(data[:50]):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "Critical error in PDF engine."})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
