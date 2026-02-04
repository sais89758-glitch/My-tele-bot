import os
import asyncio
import logging
import hashlib
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIG
# =====================================================
BOT_TOKEN = "8515688348:AAFenIGE3A5O98YRLt7mFn_NBr_Ea06gJMA"
ADMIN_ID = 6445257462
VIP_CHANNEL_ID = -1003863175003
MAIN_CHANNEL = "https://t.me/ZanchannelMM"
ADMIN_USERNAME = "Lucus22520"

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
    is_vip INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    image_hash TEXT UNIQUE,
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# =====================================================
# START
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot / Screen Record / Download / Forward မရပါ\n\n"
        "🥇 VIP – 30000 MMK (ရာသက်ပန်)"
    )

    kb = [
        [InlineKeyboardButton("👑 VIP 30000MMK", callback_data="vip_buy")],
        [InlineKeyboardButton("📣 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL)],
        [InlineKeyboardButton("📞 ကြော်ညာ / ငွေလွဲအဆင်မပြေမှု", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        protect_content=True
    )

# =====================================================
# VIP WARNING
# =====================================================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n"
        "⛔️ ခွဲလွဲထားပါက VIP မအတည်ပြုပါ\n\n"
        "⛔️ Screenshot / Screen Record / Download / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်"
    )

    kb = [
        [InlineKeyboardButton("သိရှိနားလည်ပါပြီ၊ ဆက်လုပ်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# PAYMENT METHODS
# =====================================================
async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_kbz"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_wave")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_cb"),
         InlineKeyboardButton("AYA Pay", callback_data="pay_aya")],
        [InlineKeyboardButton("🔙 Back", callback_data="vip_buy")]
    ]

    await q.edit_message_text(
        "💳 ငွေပေးချေမှုနည်းလမ်း ရွေးချယ်ပါ",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =====================================================
# PAYMENT INFO
# =====================================================
async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.replace("pay_", "").upper()
    context.user_data["method"] = method

    text = (
        f"ငွေလွဲရန် (30000MMK)\n\n"
        f"💳 {method}\n\n"
        f"📱 ဖုန်းနံပါတ်: {PAY_PHONE}\n"
        f"👤 အမည်: {PAY_NAME}\n\n"
        "‼️ ငွေကို တစ်ခါတည်း အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲ ဖြစ်ပါက\n"
        "ငွေပြန်အမ်းခြင်း၊ VIP အတည်ပြုခြင်း လုံးဝမရှိပါ\n\n"
        "⚠️ ပြေစာ Screenshot + ငွေလွဲသူအကောင့်နာမည် ပို့ပါ"
    )

    kb = [[InlineKeyboardButton("🔙 Back", callback_data="pay_methods")]]

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# RECEIVE RECEIPT
# =====================================================
async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    method = context.user_data.get("method")

    if not update.message.photo or not method:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    image_hash = hashlib.sha256(data).hexdigest()

    cur.execute("SELECT 1 FROM payments WHERE image_hash=?", (image_hash,))
    if cur.fetchone():
        await update.message.reply_text("❌ ပြေစာ အတူတူ ထပ်ပို့ထားပါသည်")
        return

    cur.execute(
        "INSERT INTO payments (user_id, method, image_hash, status, created_at) VALUES (?,?,?,?,?)",
        (user_id, method, image_hash, "pending", datetime.utcnow().isoformat())
    )
    conn.commit()

    admin_kb = [
        [
            InlineKeyboardButton("✅ ငွေရောက်ပါသည်", callback_data=f"approve_{user_id}_{image_hash}"),
            InlineKeyboardButton("❌ ငွေမရောက်ပါ", callback_data=f"reject_{user_id}_{image_hash}")
        ]
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,
        caption=f"💳 Payment Pending\nUser ID: {user_id}\nMethod: {method}",
        reply_markup=InlineKeyboardMarkup(admin_kb)
    )

    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ。\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

# =====================================================
# ADMIN APPROVE / REJECT
# =====================================================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, user_id, image_hash = q.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        cur.execute("UPDATE users SET is_vip=1 WHERE user_id=?", (user_id,))
        cur.execute("UPDATE payments SET status='approved' WHERE image_hash=?", (image_hash,))
        conn.commit()

        invite = await context.bot.create_chat_invite_link(VIP_CHANNEL_ID, member_limit=1)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ VIP အတည်ပြုပြီးပါပြီ\n\n🎬 Channel Link 👇\n{invite.invite_link}",
            protect_content=True
        )

        await q.edit_message_caption(q.message.caption + "\n\n🟢 အတည်ပြုပြီး")

    else:
        cur.execute("UPDATE payments SET status='rejected' WHERE image_hash=?", (image_hash,))
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ ဝယ်ယူမှု မအောင်မြင်ပါ\nနောက်တစ်ကြိမ် သေချာစွာ စစ်ဆေးပြီး ပြန်ကြိုးစားပါ"
        )

        await q.edit_message_caption(q.message.caption + "\n\n🔴 ပယ်ချပြီး")

# =====================================================
# MAIN
# =====================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    app.add_handler(MessageHandler(filters.PHOTO, receive_receipt))

    log.info("Zan Movie Channel Bot Started")
    app.run_polling()

if __name__ == "__main__":
    main()
