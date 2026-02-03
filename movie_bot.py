# =========================
# Zan Movie VIP Bot (FIXED & CONSOLIDATED)
# python-telegram-bot==21.7 compatible
# =========================

import os
import asyncio
import logging
import hashlib
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# =========================
# CONFIG (ENV ONLY)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID", "0"))
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")  # channel username or URL
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_PATH = "data/movie_bot.db"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# =========================
# DB SETUP
# =========================
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT,
    file_id TEXT,
    text TEXT,
    post_time TEXT,
    delete_time TEXT,
    message_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    vip_type TEXT,
    vip_expire TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    method TEXT,
    image_hash TEXT,
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def set_user(user_id: int, vip_type: str, expire: datetime | None):
    cur.execute(
        "REPLACE INTO users (user_id, vip_type, vip_expire) VALUES (?,?,?)",
        (user_id, vip_type, expire.isoformat() if expire else None)
    )
    conn.commit()


def add_payment(user_id, amount, method, image_hash, status):
    cur.execute("""
        INSERT INTO payments (user_id, amount, method, image_hash, status, created_at)
        VALUES (?,?,?,?,?,?)
    """, (user_id, amount, method, image_hash, status, datetime.utcnow().isoformat()))
    conn.commit()


def is_duplicate(image_hash: str) -> bool:
    cur.execute("SELECT 1 FROM payments WHERE image_hash=?", (image_hash,))
    return cur.fetchone() is not None

# =========================
# START / MAIN MENU
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot / Screen Record / Download / save မရပါ\n\n"
        "🥇 Pro VIP – 30000 MMK (Lifetime)\n\n"
    )
    kb = [
        [InlineKeyboardButton("🌟 VIP", callback_data="buy_pro")],
        [InlineKeyboardButton("📣 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL)],
        [InlineKeyboardButton("📞 Admin ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =========================
# BUY FLOW
# =========================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    vip_type = q.data
    context.user_data["vip_type"] = vip_type
    amount = 30000

    warn = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n\n"
        f"💳 Amount: {amount} MMK"
    )

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_kbz"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_wave")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await q.edit_message_text(warn, reply_markup=InlineKeyboardMarkup(kb))

# =========================
# PAYMENT METHOD
# =========================
async def pay_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.replace("pay_", "").upper()
    context.user_data["method"] = method

    text = (
        f"💳 {method}\n\n"
        "⚠️ ငွေလွဲပြီးပါက ပြေစာ Screenshot ကို ပို့ပေးပါ"
    )
    await q.edit_message_text(text)

# =========================
# RECEIVE PAYMENT
# =========================
async def receive_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    vip_type = context.user_data.get("vip_type")
    method = context.user_data.get("method")

    if not vip_type or not method:
        return

    amount = 30000

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()

    image_hash = hashlib.sha256(data).hexdigest()

    if is_duplicate(image_hash):
        await update.message.reply_text("❌ ပြေစာအတု / ထပ်တူ ဖြစ်နိုင်ပါသည်။")
        add_payment(user_id, amount, method, image_hash, "duplicate")
        return

    add_payment(user_id, amount, method, image_hash, "approved")
    set_user(user_id, "pro", None)

    invite = await context.bot.create_chat_invite_link(
        chat_id=VIP_CHANNEL_ID,
        creates_join_request=False
    )

    await update.message.reply_text(
        "✅ ငွေပေးချေမှု အောင်မြင်ပါသည်။\n\n"
        "🎬 VIP Channel သို့ဝင်ရန် link 👇\n"
        f"{invite.invite_link}",
        protect_content=True
    )

# =========================
# AUTO EXPIRE TASK (BASIC ONLY)
# =========================
async def expire_task(app: Application):
    while True:
        try:
            cur.execute("SELECT user_id, vip_expire FROM users WHERE vip_type='basic'")
            rows = cur.fetchall()
            now = datetime.utcnow()

            for uid, exp in rows:
                if exp and now >= datetime.fromisoformat(exp):
                    try:
                        await app.bot.ban_chat_member(VIP_CHANNEL_ID, uid)
                    except Exception:
                        pass
                    cur.execute(
                        "UPDATE users SET vip_type=NULL, vip_expire=NULL WHERE user_id=?",
                        (uid,)
                    )
                    conn.commit()
        except Exception as e:
            log.error(e)

        await asyncio.sleep(3600)

# =========================
# CALLBACK ROUTER
# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "buy_pro":
        await buy(update, context)
    elif data.startswith("pay_"):
        await pay_method(update, context)
    elif data == "back":
        await start(update, context)

# =========================
# MAIN
# =========================
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, receive_ss))

    app.create_task(expire_task(app))

    log.info("Zan Movie VIP Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
