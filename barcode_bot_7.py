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
STRAUSS_URL = "https://www.strauss-group.co.il/wp-content/themes/retlehs-roots-43f44a4/assets/ajax/products_autocomplete.php"
OUTPUT_FOLDER = "PDF_OUTPUTS"
STRAUSS_FILE = "strauss.txt"

# --- שרת בריאות (עבור Render) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- פונקציית עדכון מוצרי שטראוס ---
def update_strauss_db():
    try:
        print("Updating Strauss database...")
        response = requests.get(STRAUSS_URL, timeout=10)
        response.raise_for_status()
        products_json = response.json()
        with open(STRAUSS_FILE, 'w', encoding='utf-8') as f:
            for item in products_json:
                barcode = str(item.get('post_name', '')).strip()
                name = str(item.get('post_title', '')).strip()
                if barcode and name:
                    f.write(f"{barcode}, {name}\n")
        print(f"Database updated: {len(products_json)} products.")
    except Exception as e:
        print(f"Update error: {e}")

# --- לוגיקת הבוט ---
def fix_hebrew(text):
    if not text: return ""
    if any("\u0590" <= c <= "\u05ea" for c in text):
        return text[::-1]
    return text

def clean_barcode(raw_barcode):
    raw_barcode = str(raw_barcode)
    return re.sub(r'\D', '', raw_barcode.split("_")[0])

def load_strauss():
    products = []
    if os.path.exists(STRAUSS_FILE):
        with open(STRAUSS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "," in line:
                    b, n = line.split(",", 1)
                    products.append({"barcode": b.strip(), "name": n.strip()})
    return products

def fetch_from_chp(keyword, limit):
    products = []
    try:
        url = "https://chp.co.il/autocompletion/product_extended"
        params = {"term": keyword, "shopping_address_city_id": "8400"}
        res = requests.get(url, params=params, timeout=5).json()
        for item in res[:limit]:
            name = item.get('label', '').split('<br>')[0].replace('<b>','').replace('</b>','').strip()
            barcode = clean_barcode(item.get('barcode', ''))
            products.append({"name": name, "barcode": barcode})
    except: pass
    return products

def create_pdf(products, filepath):
    pdf = FPDF()
    pdf.add_page()
    # שימוש ב-Arial מובנה (ללא תלות בקובץ מקומי)
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=fix_hebrew("רשימת מוצרים"), ln=1, align='C')
    pdf.ln(5)

    for i, p in enumerate(products, 1):
        line = f"{i}. {fix_hebrew(p['name'][:40])} : {p['barcode']}"
        pdf.cell(0, 10, txt=line, ln=1, align='R')
    pdf.output(filepath)

def handle_bot():
    print("--- Telegram Bot Started ---")
    update_strauss_db() # עדכון רשימה עם הפעלת הבוט
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
                        text = update["message"].get("text", "")
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      data={'chat_id': chat_id, 'text': "I am alive! Generating your PDF..."})

                        # בחירת דאטה
                        strauss_db = load_strauss()
                        random.shuffle(strauss_db)
                        
                        if text == "3":
                            data = strauss_db[:60] + fetch_from_chp("אסם", 10) + fetch_from_chp("תנובה", 10)
                        elif text == "2":
                            data = strauss_db[:40] + fetch_from_chp("אסם", 5) + fetch_from_chp("תנובה", 5)
                        else:
                            data = strauss_db[:40]

                        if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                        path = os.path.join(OUTPUT_FOLDER, "list.pdf")
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
