import os
import json
import threading
import time
import schedule
import pandas as pd
import requests
from io import BytesIO
from telegram import Bot
from telegram.error import TelegramError
from flask import Flask

# ◼️ متغيّر بيئي واحد فقط:
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ◼️ بقية الإعدادات داخل الكود:
CHANNEL_USERNAME = '@discountcoupononline'
EXCEL_FILE       = 'coupons.xlsx'
STATE_FILE       = 'state.json'
PORT             = 8080

bot = Bot(token=BOT_TOKEN)
coupons = []
current_index = 0

def load_state():
    global current_index
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                current_index = data.get('current_index', 0)
        except Exception:
            current_index = 0
    else:
        save_state()

def save_state():
    with open(STATE_FILE, 'w') as f:
        json.dump({'current_index': current_index}, f)

def load_coupons():
    global coupons
    try:
        df = pd.read_excel(EXCEL_FILE)
        coupons = df.to_dict('records')
        print(f"✅ تم تحميل {len(coupons)} كوبون")
    except Exception as e:
        print(f"❌ فشل تحميل الإكسل: {e}")

def post_coupon():
    global current_index
    if not coupons:
        print("⚠️ لا توجد كوبونات للنشر")
        return

    coupon = coupons[current_index]
    try:
        resp = requests.get(coupon['image'])
        photo = BytesIO(resp.content)
    except Exception as e:
        print(f"❌ خطأ في تحميل الصورة: {e}")
        return

    message = (
        f"🎉 كوبون {coupon['title']}\n\n"
        f"🔥 {coupon['description']}\n\n"
        f"✅ الكوبون: {coupon['code']}\n\n"
        f"🌍 صالح لـ: {coupon['countries']}\n\n"
        f"📌 ملاحظة: {coupon['note']}\n\n"
        f"🛒 رابط الشراء: {coupon['link']}\n\n"
        "💎 لمزيد من الكوبونات:\nhttps://www.discountcoupon.online"
    )

    try:
        bot.send_photo(chat_id=CHANNEL_USERNAME, photo=photo, caption=message)
        print(f"✅ تم نشر كوبون #{current_index + 1}")
    except TelegramError as e:
        print(f"❌ خطأ في النشر: {e}")

    current_index = (current_index + 1) % len(coupons)
    save_state()

# جدولة كل ساعة عند الدقيقة 00
schedule.every().hour.at(":00").do(post_coupon)

def scheduler_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

if __name__ == '__main__':
    load_coupons()
    load_state()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT)
