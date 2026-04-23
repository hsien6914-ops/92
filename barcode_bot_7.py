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
PDF_PATH = "/tmp/list.pdf"

# רשימת גיבוי מובנית (אם האתרים חוסמים את השרת)
BACKUP_PRODUCTS = [
    "7290000066271", "7290000066318", "7290000302300", "7290004131074", 
    "7290110112226", "7290000066110", "7296073236350", "7290000473376",
    "7290000066202", "7290000066240", "7290000066257", "7290110112233"
]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def fetch_products_safe():
    products = [{"barcode": b} for b in BACKUP_PRODUCTS] # מתחיל מרשימת הגיבוי
    keywords = ["עלית", "אסם", "תנובה"]
    for kw in keywords:
        try:
            url = "https://chp.co.il/autocompletion/product_extended"
            res = requests.get(url, params={"term": kw}, timeout=5).json()
            for item in res[:10]:
                b = re.sub(r'\D', '', str(item.get('barcode', '')).split("_")[0])
                if len(b) >= 8: products.append({"barcode": b})
        except: continue
    return products

def create_pdf(products):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=12)
        pdf.cell(200, 10, txt="BARCODE LIST - STABLE VERSION", ln=1, align='C')
        pdf.ln(10)
        for i, p in enumerate(products, 1):
            pdf.cell(0, 10, txt=f"{i}. Barcode: {p['barcode']}", ln=1)
        pdf.output(PDF_PATH)
        return True
    except: return False

def handle_bot():
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
                                      data={'chat_id': chat_id, 'text': "Generating stable PDF list..."})
                        data = fetch_products_safe()
                        random.shuffle(data)
                        if create_pdf(data[:60]):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
