# ============================================================
# Zan Movie Channel Bot – FULL FINAL VERSION
# python-telegram-bot v20+
# ============================================================

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
# CONFIG
# ============================================================

BOT_TOKEN = "8515688348:AAG9tp1ZJ03MVmxdNe26ZO1x9SFrDA3-FYY"

ADMIN_ID = 6445257462
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
VIP_CHANNEL_ID = -1003863175003

VIP_PRICE = 30000
DEFAULT_PHONE = "09960202983"
DEFAULT_NAME = "Sai Zaw Ye Lwin"

DB_NAME = "movie_bot.db"

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ============================================================
# DATABASE INIT
# ============================================================

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
        ref_code TEXT,
        amount INTEGER,
        status TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inviters (
        code TEXT PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        next_post TEXT,
        end_at TEXT,
        interval_hours INTEGER,
        active INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ============================================================
# STATES
# ============================================================

WAITING_SLIP, WAITING_NAME, ASK_REF, WAITING_REF = range(4)

# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔ Screenshot (SS) မရ\n"
        "⛔ Screen Record မရ\n"
        "⛔ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    kb = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({VIP_PRICE} MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)]
    ]

    if update.effective_user.id == ADMIN_ID:
        kb.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin_dashboard")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ============================================================
# VIP WARNING
# ============================================================

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

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

    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ============================================================
# PAYMENT METHODS
# ============================================================

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA"),
         InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")]
    ]

    await q.message.edit_text("ငွေပေးချေမှုနည်းလမ်း ရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

# ============================================================
# PAYMENT INFO
# ============================================================

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.split("_")[1]
    context.user_data["method"] = method

    text = (
        f"💳 {method} Pay\n\n"
        f"💰 Amount: {VIP_PRICE} MMK\n"
        f"📱 Phone: {DEFAULT_PHONE}\n"
        f"👤 Name: {DEFAULT_NAME}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    await q.message.edit_text(text)
    return WAITING_SLIP

# ============================================================
# RECEIVE SLIP
# ============================================================

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Screenshot ပုံသာ ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("👤 ငွေလွဲအကောင့်အမည် ပို့ပေးပါ")
    return WAITING_NAME

# ============================================================
# RECEIVE NAME + REF BUTTON
# ============================================================

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text.strip()

    kb = [
        [InlineKeyboardButton("ရှိပါတယ်", callback_data="ref_yes")],
        [InlineKeyboardButton("မရှိပါ", callback_data="ref_no")]
    ]

    await update.message.reply_text(
        "📨 ဖိတ်ခေါ် ကုဒ် ရှိပါသလား?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    return ASK_REF

# ============================================================
# ASK REF
# ============================================================

async def ask_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "ref_no":
        await notify_admin(context, q.from_user.id, None)
        await q.message.edit_text(
            "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
            "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
        )
        return ConversationHandler.END

    await q.message.edit_text("🔑 ဖိတ်ခေါ် ကုဒ် (5 လုံး) ပို့ပေးပါ")
    return WAITING_REF

# ============================================================
# RECEIVE REF
# ============================================================

async def receive_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT code FROM inviters WHERE code=?", (code,))
    ok = cur.fetchone()
    conn.close()

    if not ok:
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await update.message.reply_text("❌ ကုဒ်မှားနေပါတယ်", reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

    await notify_admin(context, update.effective_user.id, code)

    await update.message.reply_text(
        "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
    )
    return ConversationHandler.END

# ============================================================
# NOTIFY ADMIN
# ============================================================

async def notify_admin(context, user_id, ref_code):
    slip = context.user_data.get("slip")
    name = context.user_data.get("account_name")
    method = context.user_data.get("method")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, ref_code, amount, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, method, name, ref_code, VIP_PRICE, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    kb = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"admin_ok_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admin_fail_{user_id}")
    ]]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=slip,
        caption=f"🧾 VIP Request\nUser: {user_id}\nName: {name}\nMethod: {method}\nRef: {ref_code}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ============================================================
# ADMIN APPROVE / REJECT
# ============================================================

async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, action, uid = q.data.split("_")
    uid = int(uid)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if action == "ok":
        expiry = datetime.now() + timedelta(days=30)
        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?,?,?)",
            (uid, 1, expiry.isoformat())
        )
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (uid,))
        conn.commit()

        link = await context.bot.create_chat_invite_link(
            chat_id=VIP_CHANNEL_ID,
            member_limit=1,
            expire_date=int(expiry.timestamp())
        )

        await context.bot.send_message(
            uid,
            f"🎉 VIP အတည်ပြုပြီးပါပြီ\n\n🔗 VIP Channel ဝင်ရန်\n{link.invite_link}"
        )

    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (uid,))
        conn.commit()
        await context.bot.send_message(uid, "❌ ငွေပေးချေမှု မအောင်မြင်ပါ")

    conn.close()
    await q.edit_message_caption(q.message.caption + f"\n\nDONE: {action.upper()}")

# ============================================================
# ADMIN DASHBOARD
# ============================================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("📊 ဝင်ငွေ / စာရင်း", callback_data="stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
    ]

    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🛠 Admin Dashboard",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await update.message.reply_text(
            "🛠 Admin Dashboard",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ============================================================
# STATS
# ============================================================

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vip = cur.fetchone()[0] or 0

    conn.close()

    await update.callback_query.message.edit_text(
        f"📊 စာရင်း\n\n👑 VIP: {vip}\n💰 Total Income: {total} MMK",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]])
    )

# ============================================================
# MAIN
# ============================================================

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_REF: [CallbackQueryHandler(ask_ref, pattern="^ref_")],
            WAITING_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ref)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard))

    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^choose_payment$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(show_stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(admin_payment_action, pattern="^admin_"))

    app.add_handler(user_conv)

    app.run_polling()

if __name__ == "__main__":
    main()
