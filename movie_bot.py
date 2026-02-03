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

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID", "0"))
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

DB_PATH = "data/bot.db"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ================= DB =================
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

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

# ================= HELPERS =================
def is_duplicate(image_hash):
    cur.execute("SELECT 1 FROM payments WHERE image_hash=?", (image_hash,))
    return cur.fetchone() is not None

def set_user(user_id, vip_type, expire):
    cur.execute(
        "REPLACE INTO users (user_id, vip_type, vip_expire) VALUES (?,?,?)",
        (user_id, vip_type, expire.isoformat() if expire else None)
    )
    conn.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie VIP Bot\n\n"
        "🥇 Pro VIP – 30000 MMK (Lifetime)\n"
    )
    kb = [
        [InlineKeyboardButton("🌟 Buy VIP", callback_data="buy_pro")],
        [InlineKeyboardButton("📣 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL)],
        [InlineKeyboardButton("📞 Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ================= BUY =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "buy_pro":
        context.user_data["vip"] = "pro"
        await q.edit_message_text(
            "💳 30000 MMK\n\nငွေလွဲပြီး Screenshot ပို့ပါ"
        )

# ================= PAYMENT =================
async def receive_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "vip" not in context.user_data:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    h = hashlib.sha256(data).hexdigest()

    if is_duplicate(h):
        await update.message.reply_text("❌ Duplicate receipt")
        return

    set_user(update.effective_user.id, "pro", None)

    invite = await context.bot.create_chat_invite_link(VIP_CHANNEL_ID)
    await update.message.reply_text(
        f"✅ Approved!\n\nVIP Link 👇\n{invite.invite_link}",
        protect_content=True
    )

# ================= MAIN =================
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, receive_ss))

    log.info("Zan Movie Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
