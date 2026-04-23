import requests
import random
from fpdf import FPDF
import os
import re
import time
from datetime import datetime

# --- פרטי הבוט ---
TELEGRAM_TOKEN = "8501576610:AAH3lheXjfPkWXjcfzPQjnbm-y66Nw3fuMQ"
MY_CHAT_ID = "642954716" 

OUTPUT_FOLDER = "PDF_OUTPUTS"
EXCLUDED_WORDS = ["זהבי", "מילקה", "לאבנה", "ממולאות", "כתר", "הארק", "וודקה", "ערק", "טילון", "מגנום", "ארטיק", "הקפא", "מגנו", "רחצה", "פיתות", "מחיר", "גלידת", "שוקובו", "גודיז", "בדלי", "קוסקוס", "הארץ"]

global_sent_barcodes = set()

def clean_barcode(raw_barcode):
    if not raw_barcode: return "7290000000000"
    raw_barcode = str(raw_barcode)
    if "_" in raw_barcode:
        parts = raw_barcode.split("_")
        for part in parts:
            if len(part) >= 12: return part
        return parts[0]
    return re.sub(r'\D', '', raw_barcode)

def fetch_by_keyword(keyword, limit):
    url = "https://chp.co.il/autocompletion/product_extended"
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://chp.co.il/'}
    products = []
    current_from = 0
    
    while len(products) < limit and current_from <= 100:
        params = {"term": keyword, "from": str(current_from), "shopping_address_city_id": "8400"}
        try:
            res = requests.get(url, params=params, headers=headers, timeout=5)
            if res.status_code != 200: break
            data = res.json()
            if not data: break
            
            for item in data:
                raw_id = str(item.get('barcode', item.get('id', '')))
                barcode = clean_barcode(raw_id)
                label = item.get('label', '')
                name = label.split('<br>')[0].replace('<b>','').replace('</b>','').strip()
                
                if keyword not in ["אסם", "תנובה", "מאמא עוף"] and any(word in name for word in EXCLUDED_WORDS):
                    continue
                
                if barcode not in global_sent_barcodes and len(barcode) >= 8:
                    if not any(p['barcode'] == barcode for p in products):
                        products.append({"name": name, "barcode": barcode})
                        if len(products) >= limit: break
            
            current_from += 10
        except:
            break
    return products

def get_extensive_data():
    global global_sent_barcodes
    
    general_keywords = ["עלית", "שטראוס", "יד מרדכי", "מילקי", "אחלה", "יטבתה"]
    all_general = []
    for kw in general_keywords:
        all_general.extend(fetch_by_keyword(kw, 12))
    
    random.shuffle(all_general)
    selected_general = all_general[:40]

    osem_products = fetch_by_keyword("אסם", 10)
    tnuva_products = fetch_by_keyword("תנובה", 5)
    mama_off_products = fetch_by_keyword("מאמא עוף", 5)

    final_list = selected_general + osem_products + tnuva_products + mama_off_products
    
    for p in final_list:
        global_sent_barcodes.add(p['barcode'])
        
    return final_list

def create_shufersal_style_pdf(selected_products, filepath):
    # הגדרת PDF ללא צורך בפונט חיצוני (Arial מובנה ב-FPDF)
    pdf = FPDF(unit='mm', format='A4')
    pdf.set_margins(10, 5, 10) 
    pdf.add_page()
    pdf.set_font('Arial', size=11)
    
    def fix(t): 
        # היפוך טקסט לעברית כדי שיוצג נכון ב-PDF ללא פונט RTL
        return str(t)[::-1] if any("\u0590" <= c <= "\u05ea" for c in str(t)) else str(t)

    col_widths = [10, 110, 45, 20] 
    headers = ["#", "Product Name", "Barcode", "Qty"] 
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=1, align='C')
    pdf.ln()

    pdf.set_font('Arial', size=9)
    row_height = 5 
    
    for idx, p in enumerate(selected_products, 1):
        pdf.cell(col_widths[0], row_height, str(idx), border=1, align='C')
        # שם המוצר יהיה הפוך לקריאה נוחה
        pdf.cell(col_widths[1], row_height, fix(p['name'][:52]), border=1, align='R')
        pdf.cell(col_widths[2], row_height, str(p['barcode']), border=1, align='C')
        pdf.cell(col_widths[3], row_height, "1", border=1, align='C')
        pdf.ln()

    pdf.output(filepath)

def process_and_send(chat_id):
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    timestamp = datetime.now().strftime("%d-%m_%H-%M")
    filename = f"barcodes_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_FOLDER, filename)

    print(f"Generating PDF for chat ID: {chat_id}")
    data = get_extensive_data()
    if data:
        create_shufersal_style_pdf(data, filepath)
        send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        try:
            with open(filepath, 'rb') as file:
                requests.post(send_url, data={'chat_id': chat_id}, files={'document': file})
            print(f"PDF sent successfully!")
        except Exception as e:
            print(f"Send Error: {e}")

def run_bot():
    print("Bot is starting on Server...")
    last_update_id = 0
    
    # שליחה ראשונית למנהל לוודא ריצה
    try:
        process_and_send(MY_CHAT_ID)
    except:
        pass

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get('result'):
                for update in response['result']:
                    last_update_id = update['update_id']
                    if 'message' in update:
                        process_and_send(update['message']['chat']['id'])
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    run_bot()