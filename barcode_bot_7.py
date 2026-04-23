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
def clean_text_for_pdf(text):
    """מנקה תווים בעייתיים כדי למנוע קריסה של FPDF"""
    if not text: return "Product"
    # בגלל ש-FPDF קורסת על עברית בלי פונט חיצוני, נהפוך לעברית ויזואלית (הפוכה) 
    # ונשתמש רק בתווים בטוחים.
    hebrew_chars = re.findall(r'[\u0590-\u05ea\s]+', text)
    if hebrew_chars:
        return text[::-1] # הופך את הטקסט
    return text

def clean_barcode(raw_barcode):
    return re.sub(r'\D', '', str(raw_barcode).split("_")[0])

def fetch_strauss():
    try:
        res = requests.get(STRAUSS_URL, timeout=10).json()
        return [{"barcode": str(i.get('post_name', '')), "name": str(i.get('post_title', ''))} for i in res]
    except: return []

def create_pdf(products):
    try:
        # יצירת PDF עם הגדרות בסיסיות מאוד
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Barcode List", ln=1, align='C')
        pdf.ln(10)
        
        for i, p in enumerate(products, 1):
            # אנחנו שולחים רק את הברקוד ומספר סידורי אם השם בעייתי
            name = clean_text_for_pdf(p['name'][:30])
            barcode = p['barcode']
            try:
                line = f"{i}. {name} : {barcode}"
                pdf.cell(0, 10, txt=line, ln=1)
            except:
                # אם השורה עדיין קורסת, נשלח רק מספר וברקוד
                pdf.cell(0, 10, txt=f"{i}. Product : {barcode}", ln=1)
        
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"Critical PDF Error: {e}")
        return False

def handle_bot():
    print("--- Bot logic started ---")
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
                                      data={'chat_id': chat_id, 'text': "Generating PDF... (Safe Mode)"})
                        
                        data = fetch_strauss()
                        if not data:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "Failed to fetch data."})
                            continue
                            
                        random.shuffle(data)
                        if create_pdf(data[:50]):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "PDF generation still failing."})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
