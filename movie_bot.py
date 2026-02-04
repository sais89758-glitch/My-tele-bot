# Zan Movie Channel Bot – FINAL FULL CODE (Event Loop FIXED)
# --------------------------------------------------
# FIX SUMMARY:
# ❌ Error: RuntimeError: This event loop is already running
# ❌ Cause: Using asyncio.run(main()) together with app.run_polling()
# ✅ Solution: Use python-telegram-bot v20 CORRECT ENTRY STYLE
#    -> DO NOT wrap run_polling() inside asyncio.run()
#    -> main() must be NORMAL (not async)
# --------------------------------------------------

"""
REQUIREMENTS (MUST INSTALL BEFORE RUN):

pip install -U python-telegram-bot==20.8

If you are on Render / Railway / VPS:
- Add this line to requirements.txt
  python-telegram-bot==20.8
"""

import sys

# --------------------------------------------------
# SAFE IMPORT GUARD
# --------------------------------------------------
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ContextTypes,
        filters,
        ConversationHandler,
    )
except ModuleNotFoundError:
    print("❌ ERROR: python-telegram-bot is not installed")
    print("👉 Run: pip install -U python-telegram-bot==20.8")
    sys.exit(1)

# --------------------------------------------------
# STANDARD LIBS
# --------------------------------------------------
import logging
import hashlib
import sqlite3
from datetime import datetime

# =====================================================
# CONFIG
# =====================================================
BOT_TOKEN = "8515688348:AAFenIGE3A5O98YRLt7mFn_NBr_Ea06gJMA"
ADMIN_ID = 6445257462
VIP_CHANNEL_ID = -1003863175003
MAIN_CHANNEL = "https://t.me/ZanchannelMM"
ADMIN_USERNAME = "lucus2252"

VIP_PRICE = 30000  # MMK
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

# migrate old table if needed
try:
    cur.execute("ALTER TABLE users ADD COLUMN vip_expiry TEXT")
except Exception:
    pass

cur.execute("""
CREATE TABLE IF NOT EXISTS users_old (
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
    account_name TEXT,
    created_at TEXT
)
""")

conn.commit()

# =====================================================
# STATES
# =====================================================
WAITING_ACCOUNT_NAME = 1

# =====================================================
# START
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # handle both message & callback
    target = update.message or update.callback_query.message
    text = (
        "ငွေလွဲရန် (30000 MMK)

"
        f"💳 {method} Pay

"
        f"📱 ဖုန်း: {PAY_PHONE}
"
        f"👤 အမည်: {PAY_NAME}

"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ
"
        "ခွဲလွဲ / မှားလွဲ ဖြစ်ပါက
"
        "ငွေပြန်မအမ်းပါ၊ VIP အတည်ပြုမည် မဟုတ်ပါ

"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    kb = [[InlineKeyboardButton("🔙 Back", callback_data="pay_methods")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# RECEIVE SCREENSHOT
# =====================================================
async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return

    context.user_data["slip_file_id"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "ပြေစာ Screenshot လက်ခံရရှိပါသည် ✅\n\n"
        "ကျေးဇူးပြု၍ ငွေလွဲသူအကောင့်အမည် ကို ပို့ပေးပါ။"
    )
    return WAITING_ACCOUNT_NAME

# =====================================================
# RECEIVE ACCOUNT NAME → SEND TO ADMIN
# =====================================================
async def receive_account_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    slip_file_id = context.user_data.get("slip_file_id")
    method = context.user_data.get("method")
    user = update.effective_user

    image_hash = hashlib.sha256(f"{slip_file_id}{account_name}".encode()).hexdigest()

    cur.execute(
        "INSERT INTO payments (user_id, method, image_hash, status, account_name, created_at) VALUES (?,?,?,?,?,?)",
        (user.id, method, image_hash, "pending", account_name, datetime.utcnow().isoformat())
    )
    conn.commit()

    admin_kb = [[
        InlineKeyboardButton("✅ KBZ Pay ဖြင့် ပေးချေမှုအောင်မြင်ပါသည်", callback_data=f"approve_{user.id}_{image_hash}"),
        InlineKeyboardButton("❌ ငွေမရောက်ပါ", callback_data=f"reject_{user.id}_{image_hash}")
    ]]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=slip_file_id,
        caption=(
            "💳 ငွေလွဲပြေစာ အသစ်\n\n"
            f"👤 User: {user.full_name}\n"
            f"🆔 ID: {user.id}\n"
            f"💳 Method: {method}\n"
            f"📝 ငွေလွဲသူအကောင့်အမည်: {account_name}"
        ),
        reply_markup=InlineKeyboardMarkup(admin_kb)
    )

    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

    return ConversationHandler.END

# =====================================================
# ADMIN APPROVE / REJECT (PAYMENT METHOD AWARE + VIP EXPIRY TIMER)
# =====================================================
# =====================================================
# ADMIN APPROVE / REJECT
# =====================================================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, user_id, image_hash = q.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        # set VIP expiry 30 days
        expiry = (datetime.utcnow().replace(microsecond=0) ).strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("UPDATE users SET is_vip=1, vip_expiry=? WHERE user_id=?", (expiry, user_id,))
        cur.execute("UPDATE users SET is_vip=1 WHERE user_id=?", (user_id,))
        cur.execute("UPDATE payments SET status='approved' WHERE image_hash=?", (image_hash,))
        conn.commit()

        invite = await context.bot.create_chat_invite_link(VIP_CHANNEL_ID, member_limit=1)
                pay_text = f"✅ {method} ဖြင့် ပေးချေမှုအောင်မြင်ပါသည်"
        await context.bot.send_message(
            chat_id=user_id,
            text=pay_text + "

🎬 VIP Channel Link 👇
" + invite.invite_link,
            protect_content=True
        )
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
            text="❌ ဝယ်ယူမှု မအောင်မြင်ပါ။ နောက်တစ်ကြိမ် ကြိုးစားကြည့်ပါ။"
        )
        await q.edit_message_caption(q.message.caption + "\n\n🔴 ပယ်ချပြီး")

# =====================================================
# MAIN (CORRECT ENTRY POINT)
# =====================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$") )

    # admin panel command
    app.add_handler(CommandHandler("tharngal", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, receive_receipt)],
        states={WAITING_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_account_name)]},
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    log.info("Zan Movie Channel Bot Started")
    app.run_polling()

if __name__ == "__main__":
    main()
