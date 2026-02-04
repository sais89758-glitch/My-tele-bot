# Zan Movie Channel Bot – FULL FINAL WORKING CODE
# python-telegram-bot v20+

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
from datetime import datetime, timedelta
import hashlib
import asyncio

# ================= CONFIG =================
BOT_TOKEN = "8515688348:AAH45NOcsGPPD9UMyc43u8zDLLnlKS8eGs0"
ADMIN_ID = 6445257462
ADMIN_USERNAME = "lucus2252"

VIP_PRICE = 30000
PAY_PHONE = "09960202983"
PAY_NAME = "Sai Zaw Ye Lwin"

MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ================= DB =================
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

# ================= STATES =================
WAITING_SLIP, WAITING_NAME = range(2)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message

    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot (SS) မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    keyboard = [
        [InlineKeyboardButton("👑 VIP ဝင်ရန်", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]

    await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ================= VIP WARNING =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n"
        "⛔️ ခွဲလွဲပါက VIP မအတည်ပြုပါ\n\n"
        "⛔️ Screenshot / Screen Record / Download / Forward မရ\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )

    kb = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")],
    ]

    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))


# ================= PAYMENT METHODS =================
async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")],
    ]

    await update.callback_query.message.edit_text(
        "ငွေပေးချေမှုနည်းလမ်းရွေးပါ",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ================= PAYMENT INFO =================
async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.replace("pay_", "")
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

    await query.message.edit_text(text)
    return WAITING_SLIP


# ================= RECEIVE SLIP =================
async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file_id = photo.file_id
    slip_hash = hashlib.md5(file_id.encode()).hexdigest()

    context.user_data["slip_hash"] = slip_hash
    context.user_data["slip_file"] = file_id

    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည်ကို ပို့ပါ")
    return WAITING_NAME


# ================= RECEIVE NAME =================
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    user_id = update.effective_user.id

    cur.execute(
        "INSERT INTO payments (user_id, method, slip_hash, account_name, status, created_at) VALUES (?,?,?,?,?,?)",
        (
            user_id,
            context.user_data["method"],
            context.user_data["slip_hash"],
            account_name,
            "PENDING",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()

    kb = [
        [
            InlineKeyboardButton(
                "✅ KBZ Pay ဖြင့် ပေးချေမှုအောင်မြင်ပါသည်",
                callback_data=f"approve_{user_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ ငွေမရောက်ပါ",
                callback_data=f"reject_{user_id}",
            )
        ],
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=context.user_data["slip_file"],
        caption=f"User ID: {user_id}\nName: {account_name}",
        reply_markup=InlineKeyboardMarkup(kb),
    )

    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

    return ConversationHandler.END


# ================= ADMIN ACTION =================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?,?,?)",
            (user_id, 1, expiry),
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ VIP အတည်ပြုပြီးပါပြီ။ (30 ရက်)",
        )
        await query.edit_message_caption("✅ အတည်ပြုပြီး")

    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ ဝယ်ယူမှု မအောင်မြင်ပါ။ နောက်တစ်ကြိမ် ကြိုးစားကြည့်ပါ။",
        )
        await query.edit_message_caption("❌ ပယ်ချပြီး")


# ================= VIP EXPIRY CHECK =================
async def vip_expiry_checker(app: Application):
    while True:
        now = datetime.now().isoformat()
        cur.execute("SELECT user_id FROM users WHERE is_vip=1 AND vip_expiry < ?", (now,))
        expired = cur.fetchall()

        for (uid,) in expired:
            cur.execute(
                "UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?",
                (uid,),
            )
            conn.commit()
            await app.bot.send_message(uid, "⛔️ VIP သက်တမ်းကုန်သွားပါပြီ")

        await asyncio.sleep(3600)


# ================= MAIN =================
async def post_init(app: Application):
    app.create_task(vip_expiry_checker(app))


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", start))

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
