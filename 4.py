import requests
import json
import time
import os

def run_auto_stock():
    txt_filename = 'FINAL_STOCK_REPORT.txt'

    try:
        if not os.path.exists("strauss_keys.json"):
            print("❌ קובץ strauss_keys.json לא נמצא!")
            return

        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys["url"]
        headers = keys["headers"]
        # שימוש במקור בדיוק כפי שסיפקת
        base_payload = keys.get("payload", {})
        
        all_results = []
        # רשימת קטגוריות נפוצות כדי לוודא שאתה מקבל "עוד מלא"
        # 1003 זה רק קטע אחד, הוספתי סריקה של הקטגוריות הראשיות
        categories = [None, 1003, 1002, 1001, 1004, 1005] 
        
        print("🚀 מתחיל שאיבת מלאי מהמפתח...")
        print("-" * 50)
        
        for cat in categories:
            page = 0
            base_payload["categoryId"] = cat
            if cat:
                print(f"--- סורק קטגוריה {cat} ---")
            else:
                print(f"--- סורק קטגוריה כללית ---")

            while True:
                base_payload["requestPage"] = page
                
                try:
                    response = requests.post(url, headers=headers, json=base_payload, timeout=15)
                    
                    if response.status_code != 200:
                        break
                        
                    data = response.json()
                    if not data or 'body' not in data:
                        break
                        
                    body = data.get('body', {})
                    # בשטראוס זה יכול להיות 'gifts' או 'items'
                    items = body.get('gifts') or body.get('items') or []

                    if not items:
                        break
                    
                    for item in items:
                        name = item.get('title') or item.get('name') or "מתנה"
                        stock = item.get('stockCount')
                        stock_display = stock if stock is not None else "זמין"
                        points = item.get('points') or 0
                        
                        res_line = f"🎁 {name[:40]:<40} | מלאי: {str(stock_display):<7} | נק': {points}"
                        
                        # מניעת כפילויות ברשימה
                        if res_line not in all_results:
                            all_results.append(res_line)
                            print(res_line)
                    
                    page += 1
                    time.sleep(0.4)

                except Exception:
                    break

        if all_results:
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"דו\"ח מלאי שטראוס - {time.strftime('%d/%m/%Y %H:%M')}\n")
                f.write("-" * 65 + "\n")
                f.write("\n".join(all_results))
            
            print("-" * 50)
            print(f"✅ הצלחה! {len(all_results)} פריטים נשמרו ב-TXT.")
            print(f"📂 הקובץ: {os.path.abspath(txt_filename)}")
        else:
            print("❌ לא התקבלו נתונים. ייתכן וה-Token פג תוקף.")

    except Exception as e:
        print(f"❌ תקלה כללית: {e}")

if __name__ == "__main__":
    run_auto_stock()
    input("\nלחץ Enter לסיום...")