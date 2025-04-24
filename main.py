import os
import json
import logging
import pandas as pd
import requests
from io import BytesIO
from flask import Flask
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ——— إعداد اللوقينج ———
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# ——— متغيّر بيئي واحد ———
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    log.error("❌ BOT_TOKEN غير معرف. الرجاء ضبط المتغيّر البيئي BOT_TOKEN ثم إعادة التشغيل.")
    exit(1)

# ——— ثوابت ضمنية ———
CHANNEL    = '@discountcoupononline'
EXCEL_FILE = 'coupons.xlsx'
STATE_FILE = 'state.json'
TZ         = 'Africa/Algiers'
PORT       = 8080

# ——— تهيئة بوت تيليجرام تزامني ———
try:
    bot = Bot(token=BOT_TOKEN)
    log.info("✅ تم تهيئة بوت تيليجرام (v13.15) بنجاح")
except Exception as e:
    log.error(f"❌ خطأ في تهيئة بوت تيليجرام: {e}")
    exit(1)

coupons = []
current_index = 0

# ——— دوال الحالة ———
def load_state():
    global current_index
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                current_index = json.load(f).get('current_index', 0)
            log.info(f"✅ تم تحميل الحالة: current_index={current_index}")
        except Exception as e:
            log.warning(f"⚠️ فشل قراءة {STATE_FILE}, البدء من الصفر: {e}")
            current_index = 0
    else:
        save_state()

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'current_index': current_index}, f)
        log.info(f"✅ تم حفظ الحالة: current_index={current_index}")
    except Exception as e:
        log.error(f"❌ فشل حفظ الحالة: {e}")

# ——— تحميل الكوبونات من الإكسل ———
def load_coupons():
    global coupons
    try:
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        coupons = df.to_dict('records')
        log.info(f"✅ تم تحميل {len(coupons)} كوبونات من {EXCEL_FILE}")
    except Exception as e:
        log.error(f"❌ فشل تحميل {EXCEL_FILE}: {e}")
        exit(1)

# ——— دالة نشر كوبون تزامني ———
def post_coupon():
    global current_index
    log.info(f"🔄 بدء post_coupon (index={current_index})")
    if not coupons:
        log.warning("⚠️ لا توجد كوبونات للنشر")
        return

    coupon = coupons[current_index]
    # تحميل الصورة
    try:
        resp = requests.get(coupon['image'], timeout=10)
        resp.raise_for_status()
        photo = BytesIO(resp.content)
        log.info("✅ تم تحميل الصورة بنجاح")
    except Exception as e:
        log.error(f"❌ خطأ في تحميل الصورة: {e}")
        return

    # صياغة الرسالة
    message = (
        f"🎉 كوبون {coupon['title']}\n\n"
        f"🔥 {coupon['description']}\n\n"
        f"✅ الكوبون: {coupon['code']}\n\n"
        f"🌍 صالح لـ: {coupon['countries']}\n\n"
        f"📌 ملاحظة: {coupon['note']}\n\n"
        f"🛒 رابط الشراء: {coupon['link']}\n\n"
        "💎 لمزيد من الكوبونات:\nhttps://www.discountcoupon.online"
    )

    # إرسال الصورة مع الكابتشن (تزامني)
    try:
        bot.send_photo(chat_id=CHANNEL, photo=photo, caption=message)
        log.info(f"✅ تم نشر كوبون #{current_index + 1}")
    except TelegramError as e:
        log.error(f"❌ خطأ أثناء إرسال الرسالة إلى تيليجرام: {e}")

    # تحديث الحالة
    current_index = (current_index + 1) % len(coupons)
    save_state()

# ——— التحميل الأولي ———
load_coupons()
load_state()

# ——— جدولة APScheduler ———
scheduler = BackgroundScheduler(timezone=timezone(TZ))
scheduler.add_job(
    post_coupon,
    trigger='cron',
    minute='*',    # كل دقيقة
    second=0,      
    id='post_coupon'
)
scheduler.start()
log.info("✅ تم تشغيل المجدول لكل دقيقة بتوقيت الجزائر")

# ——— نشر أول كوبون فورياً لاختبار ———
post_coupon()

# ——— خادم Flask للـ Keep-Alive ———
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive 👍"

if __name__ == '__main__':
    log.info(f"🚀 بدء خادم Flask على 0.0.0.0:{PORT}")
    app.run(host='0.0.0.0', port=PORT)
