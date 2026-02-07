# ============================================================
# Zan Movie Channel Bot – FINAL FIXED VERSION
# python-telegram-bot v20+
# ============================================================

import logging
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIGURATION
# =====================================================

BOT_TOKEN = "8515688348:AAG9tp1ZJ03MVmxdNe26ZO1x9SFrDA3-FYY"
ADMIN_ID = 6445257462
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
VIP_CHANNEL_ID = -1003863175003

DEFAULT_PRICE = 10000
DEFAULT_PHONE = "09960202983"
DEFAULT_NAME = "Sai Zaw Ye Lwin"
DB_NAME = "movie_bot.db"

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# =====================================================
# DATABASE
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
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
            amount INTEGER,
            status TEXT,
            created_at TEXT,
            ref_code TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_settings (
            method TEXT PRIMARY KEY,
            phone TEXT,
            name TEXT
        )
    """)

    for m in ["KBZ", "WAVE", "AYA", "CB"]:
        cur.execute(
            "INSERT OR IGNORE INTO payment_settings(method, phone, name) VALUES (?,?,?)",
            (m, DEFAULT_PHONE, DEFAULT_NAME)
        )

    conn.commit()
    conn.close()

# =====================================================
# STATES
# =====================================================
WAITING_SLIP, WAITING_NAME, WAITING_REF = range(3)

# =====================================================
# USER SIDE
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
   text = (
    "🎬 Zan Movie Channel Bot\n\n"
    "⛔ Screenshot (SS) မရ\n"
    "⛔ Screen Record မရ\n"
    "⛔ Download / Save / Forward မရ\n\n"
    "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
)
    kb = [
        [InlineKeyboardButton(f"VIP ဝင်ရန် ({DEFAULT_PRICE} MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)]
    ]

    if update.effective_user.id == ADMIN_ID:
        kb.append([InlineKeyboardButton("Admin Dashboard", callback_data="admin_dashboard")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

   text = (
    "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
    "⛔ channel နှင့် bot ကိုထွက်မိ၊ဖျတ်မိပါက link ပြန်မပေးပါ\n"
    "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
    "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
    "⛔ တစ်ကြိမ်ထဲ အပြည့်လွဲရပါမည်\n\n"
    "ဆက်လက်လုပ်ဆောင်မလား?"
)
    kb = [
        [InlineKeyboardButton("ဆက်လုပ်မည်", callback_data="choose_payment")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]

    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA"),
         InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")]
    ]

    await update.callback_query.message.edit_text(
        "ငွေပေးချေမှုနည်းလမ်းရွေးပါ",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.split("_")[1]
    context.user_data["method"] = method

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT phone, name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()

    phone = row[0] if row else DEFAULT_PHONE
    name = row[1] if row else DEFAULT_NAME

    text = (
        f"{method} Pay\n"
        f"Phone: {phone}\n"
        f"Name: {name}\n\n"
        "Screenshot ပို့ပါ"
    )

    await query.message.edit_text(text)
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Screenshot ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("ငွေလွဲသူအမည် ပို့ပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text
    await update.message.reply_text("Referral Code ရှိရင်ထည့်ပါ (မရှိရင် skip)")
    return WAITING_REF

async def process_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = update.message.text if update.message else None
    uid = update.effective_user.id

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments(user_id,method,account_name,amount,status,created_at,ref_code) VALUES (?,?,?,?,?,?,?)",
        (
            uid,
            context.user_data["method"],
            context.user_data["account_name"],
            DEFAULT_PRICE,
            "PENDING",
            datetime.now().isoformat(),
            ref
        )
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("Admin ထံပို့ပြီးပါပြီ")
    return ConversationHandler.END

# =====================================================
# ADMIN
# =====================================================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("Stats", callback_data="stats")],
        [InlineKeyboardButton("Back", callback_data="back_home")]
    ]

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text("Admin Dashboard", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("Admin Dashboard", reply_markup=InlineKeyboardMarkup(kb))

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total = cur.fetchone()[0] or 0

    conn.close()

    await update.callback_query.message.edit_text(
        f"Total Income: {total} MMK",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_dashboard")]])
    )

# =====================================================
# MAIN
# =====================================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ref)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard))

    app.add_handler(user_conv)
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^choose_payment$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(show_stats, pattern="^stats$"))

    app.run_polling()

if __name__ == "__main__":
    main()
