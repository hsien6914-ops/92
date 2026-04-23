import requests
import json
import time
import os
import sys
import tkinter as tk
from tkinter import font
from bidi.algorithm import get_display  # 👈 הייבוא החדש לסידור העברית

def show_huge_popup_and_exit(gift_name, stock):
    # ... (הקוד של הפופאפ נשאר בדיוק אותו דבר) ...
    """חלון מעוצב בטירוף שסוגר את הכל בסיום"""
    root = tk.Tk()
    root.title("🚨 התראת מלאי קריטית! 🚨")
    
    root.attributes("-topmost", True)
    window_width = 700
    window_height = 400
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    root.configure(bg="#1a1a1a")

    header_f = font.Font(family="Segoe UI", size=36, weight="bold")
    name_f = font.Font(family="Segoe UI", size=24)
    stock_f = font.Font(family="Segoe UI", size=20, weight="bold")

    tk.Label(root, text="🔥 BUYME ALL! 🔥", font=header_f, bg="#1a1a1a", fg="#00FF00", pady=20).pack()
    
    frame = tk.Frame(root, bg="#333333", padx=20, pady=20, highlightbackground="#00FF00", highlightthickness=2)
    frame.pack(pady=10)

    tk.Label(frame, text=f"מתנה: {gift_name}", font=name_f, bg="#333333", fg="white").pack()
    tk.Label(frame, text=f"כמות במלאי: {stock}", font=stock_f, bg="#333333", fg="#FFD700").pack()

    def final_exit():
        root.destroy()
        # 👈 עברית מסודרת ביציאה
        print(get_display("\n👋 סוגר הכל... בהצלחה!")) 
        os._exit(0)

    exit_btn = tk.Button(
        root, 
        text="סגור והמשך לרכישה", 
        command=final_exit, 
        font=("Segoe UI", 16, "bold"), 
        bg="#FF3131", 
        fg="white", 
        activebackground="#CC0000",
        padx=40, 
        pady=10,
        cursor="hand2"
    )
    exit_btn.pack(pady=30)

    root.protocol("WM_DELETE_WINDOW", final_exit)
    root.mainloop()

def run_auto_stock():
    txt_filename = 'FINAL_STOCK_REPORT.txt'
    try:
        if not os.path.exists("strauss_keys.json"):
            # 👈 סידור עברית לשגיאה
            print(get_display("❌ קובץ strauss_keys.json לא נמצא!"))
            return

        with open("strauss_keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)
        
        url = keys["url"]
        headers = keys["headers"]
        base_payload = keys.get("payload", {})
        all_results = []
        categories = [None, 1003, 1002, 1001, 1004, 1005] 
        
        # 👈 סידור עברית להודעת פתיחה
        print(get_display("🔍 מחפש את היהלום... (BUYME ALL)"))

        for cat in categories:
            page = 0
            base_payload["categoryId"] = cat
            while True:
                base_payload["requestPage"] = page
                try:
                    response = requests.post(url, headers=headers, json=base_payload, timeout=15)
                    if response.status_code != 200: break
                    data = response.json()
                    items = data.get('body', {}).get('gifts') or data.get('body', {}).get('items') or []
                    if not items: break
                    
                    for item in items:
                        name = item.get('title') or item.get('name') or "מתנה"
                        stock = item.get('stockCount')
                        stock_display = stock if stock is not None else "זמין"
                        
                        if "BUYME ALL" in name.upper():
                            show_huge_popup_and_exit(name, stock_display)

                        res_line = f"🎁 {name[:40]:<40} | מלאי: {str(stock_display):<7}"
                        if res_line not in all_results:
                            all_results.append(res_line)
                            # 👈 סידור עברית לכל שורת מתנה
                            print(get_display(res_line))
                    
                    page += 1
                    time.sleep(0.3)
                except: break

        # 👈 סידור עברית לסיום הסריקה
        print(get_display("\n✅ סבב סריקה הסתיים ללא BUYME."))

    except Exception as e:
        print(get_display(f"❌ תקלה: {e}"))

if __name__ == "__main__":
    run_auto_stock()