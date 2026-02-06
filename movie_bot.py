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
# =====================================================
# CONFIG (DIRECT VALUES)
# =====================================================

BOT_TOKEN = "8515688348:AAHkgGjz06M0BXBIqSuQzl2m_OFuUbakHAI"

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
# ===============================
# CONFIG
# ===============================
BOT_TOKEN = "8515688348:AAHkgGjz06M0BXBIqSuQzl2m_OFuUbakHAI"
ADMIN_ID = 6445257462
MAIN_CHANNEL_ID = -1001234567890  # <-- ပြင်ပါ

DB_NAME = "admin_bot.db"

# ===============================
# LOG
# ===============================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ADMIN-BOT")

# ===============================
# STATES
# ===============================
(
    AD_MEDIA,
    AD_DAYS,
    AD_INTERVAL,
    PAY_QR,
    PAY_PHONE,
    PAY_NAME,
) = range(6)

# ===============================
# DB INIT
# ===============================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        status TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_settings (
        method TEXT PRIMARY KEY,
        qr TEXT,
        phone TEXT,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        total_days INTEGER,
        interval_hours INTEGER,
        next_post TEXT,
        end_at TEXT,
        active INTEGER
    )
    """)

    for m in ["KBZ", "Wave", "AYA", "CB"]:
        cur.execute(
            "INSERT OR IGNORE INTO payment_settings(method) VALUES (?)",
            (m,)
        )

    conn.commit()
    conn.close()

# ===============================
# /tharngal
# ===============================
async def tharngal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("📊 စာရင်း / ဝင်ငွေ", callback_data="stats")],
        [InlineKeyboardButton("📢 ကြော်ညာ", callback_data="ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="pay")],
    ]

    await update.message.reply_text(
        "🛠 Admin Dashboard",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# ===============================
# STATS
# ===============================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    now = datetime.now()
    today = now.date().isoformat()
    month_start = now.replace(day=1).isoformat()

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (today,))
    today_income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND created_at>=?", (month_start,))
    month_income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total_income = cur.fetchone()[0] or 0

    days = calendar.monthrange(now.year, now.month)[1]
    lines = []
    for d in range(1, days + 1):
        day = datetime(now.year, now.month, d).date().isoformat()
        cur.execute(
            "SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?",
            (day,)
        )
        amt = cur.fetchone()[0] or 0
        lines.append(f"{d:02d} ➜ {amt} MMK")

    conn.close()

    text = (
        f"📊 ဝင်ငွေစာရင်း\n\n"
        f"ယနေ့: {today_income} MMK\n"
        f"ယခုလ: {month_income} MMK\n"
        f"စုစုပေါင်း: {total_income} MMK\n\n"
        "📅 လစဉ် ပြက္ခဒိန်\n" +
        "\n".join(lines)
    )

    await q.message.edit_text(text)

# ===============================
# ADS FLOW
# ===============================
async def ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text("📸 Photo / 🎥 Video + Caption ပို့ပါ")
    return AD_MEDIA

async def ads_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        context.user_data["media"] = ("photo", msg.photo[-1].file_id, msg.caption or "")
    elif msg.video:
        context.user_data["media"] = ("video", msg.video.file_id, msg.caption or "")
    else:
        await msg.reply_text("Photo သို့ Video ပို့ပါ")
        return AD_MEDIA

    await msg.reply_text("📅 ဘယ်နှစ်ရက်တင်မလဲ? (ဥပမာ 7)")
    return AD_DAYS

async def ads_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["days"] = int(update.message.text)
    await update.message.reply_text("⏱️ ဘယ်နှနာရီခြားတစ်ခါတင်မလဲ?")
    return AD_INTERVAL

async def ads_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hours = int(update.message.text)
    media_type, file_id, caption = context.user_data["media"]
    days = context.user_data["days"]

    now = datetime.now()
    end = now + timedelta(days=days)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO ads(media_type,file_id,caption,total_days,interval_hours,next_post,end_at,active)
    VALUES(?,?,?,?,?,?,?,1)
    """, (
        media_type, file_id, caption, days, hours,
        now.isoformat(), end.isoformat()
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ {hours} နာရီခြားတစ်ခါ / {days} ရက် ကြော်ညာ schedule ပြီးပါပြီ"
    )
    return ConversationHandler.END

# ===============================
# PAYMENT EDIT
# ===============================
async def pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="edit_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="edit_Wave")],
        [InlineKeyboardButton("AYA Pay", callback_data="edit_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="edit_CB")],
    ]

    await q.message.edit_text(
        "💳 Payment ပြင်ရန်",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["method"] = q.data.split("_")[1]
    await q.message.edit_text("📸 QR ပုံ ပို့ပါ")
    return PAY_QR

async def pay_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["qr"] = update.message.photo[-1].file_id
    await update.message.reply_text("📱 ဖုန်းနံပါတ် ပို့ပါ")
    return PAY_PHONE

async def pay_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("👤 အမည် ပို့ပါ")
    return PAY_NAME

async def pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    UPDATE payment_settings
    SET qr=?, phone=?, name=?
    WHERE method=?
    """, (
        context.user_data["qr"],
        context.user_data["phone"],
        update.message.text,
        context.user_data["method"],
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Payment အချက်အလက် သိမ်းပြီးပါပြီ")
    return ConversationHandler.END

# ===============================
# MAIN
# ===============================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("tharngal", tharngal))
    app.add_handler(CallbackQueryHandler(stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(ads_start, pattern="^ads$"))
    app.add_handler(CallbackQueryHandler(pay_menu, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(pay_qr, pattern="^edit_"))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ads_start, pattern="^ads$")],
        states={
            AD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, ads_media)],
            AD_DAYS: [MessageHandler(filters.TEXT, ads_days)],
            AD_INTERVAL: [MessageHandler(filters.TEXT, ads_interval)],
        },
        fallbacks=[]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_qr, pattern="^edit_")],
        states={
            PAY_QR: [MessageHandler(filters.PHOTO, pay_qr_save)],
            PAY_PHONE: [MessageHandler(filters.TEXT, pay_phone)],
            PAY_NAME: [MessageHandler(filters.TEXT, pay_name)],
        },
        fallbacks=[]
    ))
    log.info("Zan Movie Channel Bot Started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
