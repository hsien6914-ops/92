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

# --- שרת בריאות למניעת כיבוי הבוט ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- לוגיקה לשליפת מוצרים ---
def clean_barcode(raw_barcode):
    return re.sub(r'\D', '', str(raw_barcode).split("_")[0])

def fetch_products_safe():
    """שולף מוצרים מ-CHP כגיבוי בטוח"""
    products = []
    keywords = ["עלית", "אסם", "תנובה", "שטראוס"]
    print("Fetching data from CHP...")
    for kw in keywords:
        try:
            url = "https://chp.co.il/autocompletion/product_extended"
            params = {"term": kw, "shopping_address_city_id": "8400"}
            res = requests.get(url, params=params, timeout=7).json()
            for item in res[:15]: # לוקח 15 מכל סוג
                barcode = clean_barcode(item.get('barcode', ''))
                if len(barcode) >= 8:
                    products.append({"barcode": barcode})
        except Exception as e:
            print(f"Error fetching {kw}: {e}")
    return products

def create_pdf(products):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=12) # פונט בטוח
        pdf.cell(200, 10, txt="BARCODE LIST - GENERATED", ln=1, align='C')
        pdf.ln(10)
        
        for i, p in enumerate(products, 1):
            line = f"{i}. Barcode: {p['barcode']}"
            pdf.cell(0, 10, txt=line, ln=1)
        
        pdf.output(PDF_PATH)
        return True
    except Exception as e:
        print(f"PDF Error: {e}")
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
                                      data={'chat_id': chat_id, 'text': "Generating PDF... (Fetching fresh data)"})
                        
                        # שליפה בטוחה
                        data = fetch_products_safe()
                        
                        if not data:
                            # אם עדיין אין דאטה, ניצור דאטה דמה כדי שלא יכשל
                            data = [{"barcode": "7290000000000"}]
                            
                        random.shuffle(data)
                        if create_pdf(data[:60]):
                            with open(PDF_PATH, 'rb') as f:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                              data={'chat_id': chat_id}, files={'document': f})
                            print(f"Success: PDF sent to {chat_id}")
                        else:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': "PDF creation error."})
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handle_bot()
