# ============================================================
# Zan Movie Channel Bot – FINAL STABLE VERSION
# python-telegram-bot v20+
# ============================================================

import os
import logging
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============================================================
# ENV CONFIG (USE WHAT YOU GAVE)
# ================= CONFIG =================
# ⚠️ Direct values (NOT os.getenv)

BOT_TOKEN = "8515688348:AAHKbL-alScUufoYbciwO-E3V4pKCRdHMVk"

ADMIN_ID = 6445257462
ADMIN_USERNAME = "Lucus22520"

MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
VIP_CHANNEL_URL = "https://t.me/+bDFiZZ9gwRRjY2M1"
VIP_CHANNEL_ID = -1003863175003

VIP_PRICE = 30000

PAY_PHONE = "09960202983"
PAY_NAME = "Sai Zaw Ye Lwin"

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ============================================================
# DATABASE
# ============================================================

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
    account_name TEXT,
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# ============================================================
# STATES
# ============================================================

WAITING_SLIP = 1
WAITING_NAME = 2

# ============================================================
# /start
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔ Screenshot (SS) မရ\n"
        "⛔ Screen Record မရ\n"
        "⛔ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    keyboard = [
        [InlineKeyboardButton("👑 VIP ဝင်ရန် (30000 MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# VIP WARNING
# ============================================================

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔ တစ်ကြိမ်ထဲ အပြည့်လွဲရပါမည်\n\n"
        "ဆက်လက်လုပ်ဆောင်မလား?"
    )

    keyboard = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")],
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# PAYMENT METHODS
# ============================================================

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")],
    ]

    await query.message.edit_text(
        "ငွေပေးချေမှုနည်းလမ်း ရွေးပါ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# PAYMENT INFO
# ============================================================

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    text = (
        f"ငွေလွဲရန် (30000 MMK)\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {PAY_PHONE}\n"
        f"👤 အမည်: {PAY_NAME}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    await query.message.edit_text(text)
    return WAITING_SLIP

# ============================================================
# RECEIVE SLIP
# ============================================================

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("ပြေစာ Screenshot ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည် ပို့ပါ")
    return WAITING_NAME

# ============================================================
# RECEIVE NAME → SEND TO ADMIN
# ============================================================

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = update.message.text
    method = context.user_data["method"]
    slip = context.user_data["slip"]

    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (user.id, method, name, "PENDING", datetime.now().isoformat())
    )
    conn.commit()

    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "KBZ Pay ဖြင့် ပေးချေမှုအောင်မြင်ပါသည်",
                callback_data=f"admin_ok_{user.id}"
            )
        ],
        [
            InlineKeyboardButton(
                "ငွေမရောက်ပါ",
                callback_data=f"admin_fail_{user.id}"
            )
        ]
    ])

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=slip,
        caption=(
            "🔔 VIP Payment Request\n\n"
            f"User ID: {user.id}\n"
            f"Username: @{user.username}\n"
            f"Method: {method}\n"
            f"Name: {name}"
        ),
        reply_markup=keyboard
    )

    return ConversationHandler.END

# ============================================================
# ADMIN ACTION
# ============================================================

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")[1:]
    user_id = int(user_id)

    if action == "ok":
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)",
            (user_id, expiry)
        )
        cur.execute(
            "UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'",
            (user_id,)
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ VIP အတည်ပြုပြီးပါပြီ",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("VIP Channel ဝင်ရန်", url=VIP_CHANNEL_URL)]
            ])
        )

        await query.edit_message_caption("✅ APPROVED")

    else:
        cur.execute(
            "UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'",
            (user_id,)
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ ငွေပေးချေမှု မအောင်မြင်ပါ"
        )
        await query.edit_message_caption("❌ REJECTED")

# ============================================================
# MAIN
# ============================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))

    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^admin_"))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, receive_slip)],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    log.info("Zan Movie Channel Bot Started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
