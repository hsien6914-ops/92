#!/usr/bin/env python
# coding: utf-8

import os
import random
import time
import threading
import requests
import logging

from flask import Flask
from telebot import TeleBot
from aliexpress_api import AliexpressApi, models
from deep_translator import GoogleTranslator

# ==========================================
# LOGS
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==========================================
# CONFIG
# ==========================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

ALI_APP_ID = os.environ.get("ALI_APP_ID")
ALI_APP_SECRET = os.environ.get("ALI_SECRET")

URL_RENDER = "https://ase-574b.onrender.com"
PORT = int(os.environ.get("PORT", 10000))

SEND_INTERVAL = 600
BOT_START_TIME = time.time()

JSONBIN_URL = "https://api.jsonbin.io/v3/b/6a15e64c5e02c046e3196e71"

HEADERS = {
    'X-Master-Key': "$2a$10$MyiqOwUKfW/CrW9W59aL7OxMhumTrKj9bcsl3PCMPtgMEFHnr1T8q"
}

if not BOT_TOKEN or not CHANNEL_ID:
    raise Exception("Missing BOT_TOKEN or CHANNEL_ID")

# ==========================================
# APP
# ==========================================

app = Flask(__name__)
bot = TeleBot(BOT_TOKEN)

aliexpress = AliexpressApi(
    ALI_APP_ID,
    ALI_APP_SECRET,
    models.Language.EN,
    models.Currency.USD,
    'default'
)

# ==========================================
# KEYWORDS (לא נגעתי)
# ==========================================

KEYWORDS = [
    "Gadget",
    "Smart Home",
    "Tool",
    "Kitchen",
    "Tech",
    "Gaming",
    "DIY",
    "Electronics",
    "Innovation",
    "Wireless Charger",
    "Bluetooth Speaker",
    "Smart Watch",
    "Power Bank",
    "Mini Drone",
    "Projector",
    "Robot Vacuum",
    "Action Camera",
    "Headphones",
    "Portable Printer",
    "WiFi Camera",
    "Smart Bulb",
    "Smart Plug",
    "Security System",
    "Smart Lock",
    "Humidifier",
    "Air Purifier",
    "Coffee Maker",
    "Blender",
    "Electric Kettle",
    "Kitchen Organizer",
    "Electric Drill",
    "Hand Tools",
    "Laser Level",
    "Multitool",
    "Dash Cam",
    "Car Charger",
    "Mechanical Keyboard",
    "Gaming Mouse",
    "LED Strip",
    "Tripod",
    "Ring Light",
    "Massage Gun",
    "Electric Toothbrush",
    "Fitness Tracker",
    "Camping Gear",
    "Travel Accessory",
    "Smart Ring",
    "Electric Shaver",
    "USB Hub",
    "Cable Organizer",
    "Phone Stand",
    "Laptop Stand",
    "Mini Fan",
    "Solar Power",
    "Security Alarm",
    "Home Decor",
    "Desk Lamp",
    "Webcam",
    "Microphone"
]

# ==========================================
# TEMPLATES (לא נגעתי)
# ==========================================

TEMPLATES = [
    (
        "<b>🔥 רק {round_ils} שקל 😱</b>\n"
        "{title}\n"
        "<b>📦 מספר הזמנות:</b> {orders}+\n"
        "<b>⭐ דירוג מוצר:</b> {rating}\n"
        "<b>💸 מחיר הנחות:</b> ₪{ils_price} ({usd_price}$)\n"
        "<b>👇 לרכישה מעליאקספרס 👇</b>\n"
        "{affiliate_link}\n\n"
        "{hashtags}"
    ),

    (
        "<b>💥 רק {round_ils} שקל 😱 דיל מטורף!</b>\n"
        "{title}\n"
        "<b>📦 מספר הזמנות:</b> {orders}+\n"
        "<b>⭐ דירוג מוצר:</b> {rating}\n"
        "<b>💸 מחיר הנחות:</b> ₪{ils_price} ({usd_price}$)\n"
        "<b>👇 לרכישה מעליאקספרס 👇</b>\n"
        "{affiliate_link}\n\n"
        "{hashtags}"
    ),

    (
        "<b>🔥 מחיר פגז רק {round_ils} שקל 🔥</b>\n"
        "{title}\n"
        "<b>📦 מספר הזמנות:</b> {orders}+\n"
        "<b>⭐ דירוג מוצר:</b> {rating}\n"
        "<b>💸 מחיר הנחות:</b> ₪{ils_price} ({usd_price}$)\n"
        "<b>👇 לרכישה מעליאקספרס 👇</b>\n"
        "{affiliate_link}\n\n"
        "{hashtags}"
    )
]

# ==========================================
# SCORE
# ==========================================

def score_product(volume, rating, price):
    score = 0
    try:
        score += float(volume or 0) * 0.6
    except:
        pass

    try:
        score += float(rating or 0) * 20
    except:
        pass

    try:
        if price < 20:
            score += 30
        elif price < 50:
            score += 15
        elif price < 100:
            score += 5
    except:
        pass

    return score

# ==========================================
# KEEP ALIVE
# ==========================================

def keep_alive():
    while True:
        try:
            requests.get(URL_RENDER, timeout=10)
        except:
            pass
        time.sleep(240)

# ==========================================
# JSONBIN SAFE (מתוקן קריסות)
# ==========================================

def get_sent():
    try:
        r = requests.get(JSONBIN_URL, headers=HEADERS, timeout=10).json()
        return set(r.get("record", {}).get("sent", []))
    except:
        return set()

def save_sent(name):
    try:
        sent = list(get_sent())
        sent.append(name)

        requests.put(
            JSONBIN_URL,
            json={"sent": sent[-500:]},
            headers={"Content-Type": "application/json", **HEADERS},
            timeout=10
        )
    except:
        pass

# ==========================================
# DASHBOARD
# ==========================================

@bot.message_handler(commands=['4'])
def dashboard(message):
    uptime = int(time.time() - BOT_START_TIME)
    h = uptime // 3600
    m = (uptime % 3600) // 60

    text = (
        "🤖 <b>דשבורד בוט</b>\n\n"
        f"⏱ זמן פעילות: {h}h {m}m\n"
        f"📦 מוצרים שנשלחו: {len(get_sent())}\n"
        "✔️ פעיל"
    )

    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ==========================================
# GET PRODUCT (מתוקן קריסות בלבד)
# ==========================================

def get_product():
    try:
        resp = aliexpress.get_products(
            keywords=random.choice(KEYWORDS),
            page_size=30,
            sort="LAST_VOLUME_DESC"
        )

        sent = get_sent()

        best = None
        best_score = 0

        for p in resp.products:
            try:
                if not p.product_title:
                    continue

                price = float(p.target_sale_price or 0)
                if price <= 0:
                    continue

                title = p.product_title[:60]

                if title in sent:
                    continue

                score = score_product(
                    getattr(p, "lastest_volume", 0),
                    getattr(p, "evaluate_rate", 0),
                    price
                )

                if score > best_score:
                    best_score = score
                    best = p

            except:
                continue

        if not best:
            return None

        try:
            title = GoogleTranslator(source='auto', target='iw').translate(best.product_title[:60])
        except:
            title = best.product_title[:60]

        usd = float(best.target_sale_price)
        ils = round(usd * 3.3)
        ils_price = f"{ils}.90"

        try:
            aff = aliexpress.get_affiliate_links(best.product_detail_url)[0].promotion_link
        except:
            aff = best.product_detail_url

        save_sent(title)

        template = random.choice(TEMPLATES)

        caption = template.format(
            round_ils=ils,
            title=title,
            orders=getattr(best, "lastest_volume", 0),
            rating=getattr(best, "evaluate_rate", 0),
            ils_price=ils_price,
            usd_price=round(usd, 2),
            affiliate_link=aff,
            hashtags="#AliExpress #דילים #מבצעים"
        )

        return caption, best.product_main_image_url

    except Exception as e:
        print("GET PRODUCT ERROR:", e)
        return None

# ==========================================
# LOOP
# ==========================================

def auto_loop():
    while True:
        try:
            data = get_product()

            if data:
                bot.send_photo(
                    CHANNEL_ID,
                    data[1],
                    caption=data[0],
                    parse_mode="HTML"
                )
                print("PRODUCT SENT")
            else:
                print("NO PRODUCT FOUND")

        except Exception as e:
            print("SEND ERROR:", e)

        time.sleep(SEND_INTERVAL)

# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return "Bot is running!"

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=auto_loop, daemon=True).start()

    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=PORT),
        daemon=True
    ).start()

    bot.infinity_polling(skip_pending=True)
