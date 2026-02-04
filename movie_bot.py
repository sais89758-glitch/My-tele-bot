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
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔ Screenshot / Screen Record / Download / Forward မရပါ\n\n"
        "👑 Pro VIP – 30000 MMK (30 Days)"
    )

    kb = [
        [InlineKeyboardButton("👑 VIP ဝင်ရန်", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]

    await target.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# VIP WARNING
# =====================================================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n"
        "⛔ ခွဲလွဲပါက VIP မအတည်ပြုပါ\n\n"
        "⛔ Screenshot / Screen Record / Download / Forward မရပါ\n\n"
        "📌 Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်"
    )

    kb = [
        [InlineKeyboardButton("သိရှိနားလည်ပါပြီ", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")],
    ]

    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# PAYMENT METHODS
# =====================================================
async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],
        [InlineKeyboardButton("⬅ Back", callback_data="back_home")],
    ]

    await q.message.edit_text("ငွေပေးချေမှုနည်းလမ်း ရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# PAYMENT INFO
# =====================================================
async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.replace("pay_", "")
    context.user_data["method"] = method

    text = (
        "ငွေလွဲရန် (30000 MMK)\n\n"
        f"💳 {method} Pay\n\n"
        f"📱 ဖုန်း: {PAY_PHONE}\n"
        f"👤 အမည်: {PAY_NAME}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    await q.message.edit_text(text)
    return WAITING_SLIP

# =====================================================
# RECEIVE SLIP
# =====================================================
async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return

    context.user_data["slip_id"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "ပြေစာ Screenshot လက်ခံရရှိပါသည် ✅\n"
        "ကျေးဇူးပြု၍ ငွေလွဲသူ အကောင့်နာမည် ပို့ပေးပါ။"
    )

    return WAITING_NAME

# =====================================================
# RECEIVE NAME → SEND TO ADMIN
# =====================================================
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    account_name = update.message.text
    slip_id = context.user_data.get("slip_id")
    method = context.user_data.get("method")

    slip_hash = hashlib.sha256(f"{slip_id}{account_name}".encode()).hexdigest()

    cur.execute(
        "INSERT INTO payments (user_id, method, slip_hash, account_name, status, created_at) VALUES (?,?,?,?,?,?)",
        (user.id, method, slip_hash, account_name, "pending", datetime.utcnow().isoformat())
    )
    conn.commit()

    admin_kb = [[
        InlineKeyboardButton(f"✅ {method} Pay ဖြင့် အောင်မြင်", callback_data=f"approve_{user.id}_{slip_hash}"),
        InlineKeyboardButton("❌ ငွေမရောက်ပါ", callback_data=f"reject_{user.id}_{slip_hash}"),
    ]]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=slip_id,
        caption=(
            "💳 ငွေလွဲပြေစာ အသစ်\n\n"
            f"👤 {user.full_name}\n"
            f"🆔 {user.id}\n"
            f"💳 Method: {method}\n"
            f"📝 Name: {account_name}"
        ),
        reply_markup=InlineKeyboardMarkup(admin_kb)
    )

    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

    return ConversationHandler.END

# =====================================================
# ADMIN ACTION
# =====================================================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, user_id, slip_hash = q.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        expiry = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?,?,?)",
                    (user_id, 1, expiry))
        cur.execute("UPDATE payments SET status='approved' WHERE slip_hash=?", (slip_hash,))
        conn.commit()

        invite = await context.bot.create_chat_invite_link(VIP_CHANNEL_ID, member_limit=1)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ VIP အတည်ပြုပြီးပါပြီ\n\n🎬 Channel Link 👇\n{invite.invite_link}",
            protect_content=True
        )

        await q.edit_message_caption(q.message.caption + "\n\n🟢 အတည်ပြုပြီး")

    else:
        cur.execute("UPDATE payments SET status='rejected' WHERE slip_hash=?", (slip_hash,))
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ ဝယ်ယူမှု မအောင်မြင်ပါ။ နောက်တစ်ကြိမ် ကြိုးစားကြည့်ပါ။"
        )
        await q.edit_message_caption(q.message.caption + "\n\n🔴 ပယ်ချပြီး")

# =====================================================
# VIP AUTO-EXPIRY CHECK (every 10 minutes)
# =====================================================
async def vip_expiry_checker(app: Application):
    while True:
        now = datetime.utcnow()
        cur.execute("SELECT user_id FROM users WHERE is_vip=1 AND vip_expiry IS NOT NULL AND vip_expiry < ?",
                    (now.strftime("%Y-%m-%d %H:%M:%S"),))
        expired = cur.fetchall()

        for (uid,) in expired:
            cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (uid,))
            conn.commit()
            try:
                await app.bot.send_message(uid, "⛔ VIP သက်တမ်းကုန်ဆုံးသွားပါပြီ။")
            except:
                pass

        await asyncio.sleep(600)

# =====================================================
# /tharngal ADMIN DASHBOARD
# =====================================================
async def tharngal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM payments WHERE status='approved'")
    total_sales = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM payments WHERE status='rejected'")
    scam_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    active_vip = cur.fetchone()[0]

    text = (
        "📊 ADMIN DASHBOARD (/tharngal)\n\n"
        f"✅ အောင်မြင်သော VIP ဝယ်ယူမှု: {total_sales}\n"
        f"❌ ပယ်ချထားသော / Scam: {scam_count}\n"
        f"👑 Active VIP: {active_vip}"
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
