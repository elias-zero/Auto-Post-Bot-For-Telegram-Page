import os
import json
import logging
import pandas as pd
import requests
from io import BytesIO
from flask import Flask
from telegram import Bot, TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ——— إعداد اللوقينج ———
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger()

# ——— متغير بيئي واحد ———
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    log.error("❌ BOT_TOKEN غير معرف في البيئة")
    exit(1)

# ——— ثوابت ضمنية ———
CHANNEL    = '@discountcoupononline'
EXCEL_FILE = 'coupons.xlsx'
STATE_FILE = 'state.json'
TZ         = 'Africa/Algiers'

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
        log.info(f"✅ تم تحميل {len(coupons)} كوبونات")
    except Exception as e:
        log.error(f"❌ فشل تحميل {EXCEL_FILE}: {e}")
        exit(1)

def post_coupon():
    global current_index
    if not coupons:
        log.warning("⚠️ لا توجد كوبونات للنشر")
        return

    coupon = coupons[current_index]
    try:
        resp = requests.get(coupon['image'], timeout=10)
        photo = BytesIO(resp.content)
    except Exception as e:
        log.error(f"❌ خطأ في تحميل الصورة: {e}")
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
        bot.send_photo(chat_id=CHANNEL, photo=photo, caption=message)
        log.info(f"✅ تم نشر كوبون #{current_index + 1}")
    except TelegramError as e:
        log.error(f"❌ خطأ أثناء النشر: {e}")

    current_index = (current_index + 1) % len(coupons)
    save_state()

# ——— التحميل الأولي ———
load_coupons()
load_state()

# ——— جدولة APScheduler ———
scheduler = BackgroundScheduler(timezone=timezone(TZ))
# ينفّذ كل دقيقة عند الثانية 0 بتوقيت Africa/Algiers
scheduler.add_job(post_coupon, 'cron', minute='*', second=0, id='post_coupon')
scheduler.start()

# اختياري: نشر أول كوبون فورياً لاختبار
post_coupon()

# ——— خادم Flask للـ Keep-Alive ———
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive 👍"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
