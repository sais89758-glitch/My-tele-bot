# Zan Movie Channel Bot – FINAL FULL CODE (WITH /tharngal DASHBOARD + VIP AUTO-EXPIRY)
# =====================================================
# python-telegram-bot v20.8 compatible
# Polling mode | Single instance safe
# =====================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

import logging
import sqlite3
import hashlib
from datetime import datetime, timedelta
import asyncio

# =====================================================
# CONFIG
# =====================================================
BOT_TOKEN = "8515688348:AAH45NOcsGPPD9UMyc43u8zDLLnlKS8eGs0"
ADMIN_ID = 6445257462
ADMIN_USERNAME = "lucus2252"
VIP_CHANNEL_ID = -1003863175003
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"

VIP_PRICE = 30000
PAY_PHONE = "09960202983"
PAY_NAME = "Sai Zaw Ye Lwin"

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# =====================================================
# DATABASE
# =====================================================
conn = sqlite3.connect("movie_bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    is_vip INTEGER DEFAULT 0,
    vip_expiry TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    slip_hash TEXT,
    account_name TEXT,
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# =====================================================
# STATES
# =====================================================
WAITING_SLIP = 1
WAITING_NAME = 2

# =====================================================
# START
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message

        text = (
        "📊 ADMIN DASHBOARD (/tharngal)

"
        f"👑 Active VIP: {active_vip}

"
        f"💰 ယနေ့ ဝင်ငွေ: {daily_revenue} MMK
"
        f"📆 ယခုလ ဝင်ငွေ: {monthly_revenue} MMK
"
        f"🏦 စုစုပေါင်း ဝင်ငွေ: {total_revenue} MMK

"
        f"❌ Scam / ပယ်ချထားမှု: {scam_count}

"
        "📅 လစဉ် ဝင်ငွေ ပြက္ခဒိန်
"
        "====================
"
        f"{calendar_text}"
    )

    await update.message.reply_text(text)

# =====================================================
# MAIN
# =====================================================
async def post_init(app: Application):
    app.create_task(vip_expiry_checker(app))


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", tharngal))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, receive_slip)],
        states={WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]},
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    log.info("Zan Movie Channel Bot Started")
    app.run_polling()


if __name__ == "__main__":
    main()
