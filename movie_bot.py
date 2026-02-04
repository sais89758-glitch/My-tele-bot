import os
import asyncio
import logging
import hashlib
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
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG (FROM YOUR FILE)
# =========================
# ⚠️ Security Note: Do not share this file publicly with these keys!
os.environ["BOT_TOKEN"] = "8515688348:AAHKbL-alScUufoYbciwO-E3V4pKCRdHMVk"
os.environ["ADMIN_ID"] = "6445257462"
os.environ["VIP_CHANNEL_ID"] = "-1003863175003"
os.environ["MAIN_CHANNEL"] = "https://t.me/ZanchannelMM"
os.environ["ADMIN_USERNAME"] = "Lucus22520"

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID"))
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ZanMovieBot")

# =========================
# DATABASE SETUP
# =========================
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/movie_bot.db", check_same_thread=False)
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
    image_hash TEXT UNIQUE,
    status TEXT,
    created_at TEXT
)
""")

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

conn.commit()

# =========================
# DB HELPERS
# =========================
def is_duplicate(image_hash: str) -> bool:
    cur.execute("SELECT 1 FROM payments WHERE image_hash=?", (image_hash,))
    return cur.fetchone() is not None


def set_user(user_id: int, vip_type: str | None, expire: datetime | None):
    cur.execute(
        "REPLACE INTO users (user_id, vip_type, vip_expire) VALUES (?,?,?)",
        (user_id, vip_type, expire.isoformat() if expire else None),
    )
    conn.commit()


def add_payment(user_id: int, amount: int, method: str, image_hash: str, status: str):
    cur.execute(
        """
        INSERT OR IGNORE INTO payments
        (user_id, amount, method, image_hash, status, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (user_id, amount, method, image_hash, status, datetime.utcnow().isoformat()),
    )
    conn.commit()

# =========================
# START / MAIN MENU
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie VIP Bot\n\n"
        "⛔️ Screenshot / Screen Record / Download မရပါ\n\n"
        "🥇 Pro VIP – 30000 MMK (Lifetime)\n"
        "🥈 Basic VIP – 10000 MMK (30 Days)"
    )

    kb = [
        [InlineKeyboardButton("🌟 Pro VIP", callback_data="buy_pro")],
        [InlineKeyboardButton("📣 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL)],
        [InlineKeyboardButton("📞 Admin ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        protect_content=True,
    )

# =========================
# BUY VIP
# =========================
async def buy_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    vip_type = q.data
    context.user_data.clear()
    context.user_data["vip_type"] = vip_type

    amount = 30000 if vip_type == "buy_pro" else 10000

    text = (
        "⚠️ ငွေလွဲမီ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း မလုပ်ရ\n\n"
        f"💰 Amount: {amount} MMK"
    )

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_kbz"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_wave")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_cb"),
         InlineKeyboardButton("AYA Pay", callback_data="pay_aya")],
    ]

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =========================
# PAYMENT METHOD
# =========================
async def choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.replace("pay_", "").upper()
    context.user_data["method"] = method

    vip_type = context.user_data.get("vip_type")
    if not vip_type:
        return

    amount = 30000 if vip_type == "buy_pro" else 10000

    await q.edit_message_text(
        f"💳 {method}\n\n"
        f"Amount: {amount} MMK\n\n"
        "📸 ပြေစာ Screenshot ပို့ပါ"
    )

# =========================
# RECEIVE PAYMENT SCREENSHOT
# =========================
async def receive_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vip_type = context.user_data.get("vip_type")
    method = context.user_data.get("method")

    if not vip_type or not method:
        return

    amount = 30000 if vip_type == "buy_pro" else 10000

    # Check if message has photo
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a photo of the receipt.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    image_hash = hashlib.sha256(data).hexdigest()

    if is_duplicate(image_hash):
        await update.message.reply_text("❌ Duplicate receipt detected")
        add_payment(user_id, amount, method, image_hash, "duplicate")
        return

    add_payment(user_id, amount, method, image_hash, "approved")

    if vip_type == "buy_pro":
        set_user(user_id, "pro", None)
    else:
        set_user(user_id, "basic", datetime.utcnow() + timedelta(days=30))

    try:
        invite = await context.bot.create_chat_invite_link(VIP_CHANNEL_ID, member_limit=1)
        invite_link = invite.invite_link
    except Exception as e:
        log.error(f"Error creating invite link: {e}")
        invite_link = "Error generating link. Contact Admin."

    await update.message.reply_text(
        "✅ Payment successful\n\n"
        "🎬 VIP Channel Link 👇\n"
        f"{invite_link}",
        protect_content=True,
    )

# =========================
# AUTO EXPIRE TASK
# =========================
async def expire_task(app: Application):
    log.info("Expire task started")
    while True:
        try:
            cur.execute("SELECT user_id, vip_expire FROM users WHERE vip_type='basic'")
            rows = cur.fetchall()
            now = datetime.utcnow()

            for uid, exp in rows:
                if exp and now >= datetime.fromisoformat(exp):
                    try:
                        await app.bot.ban_chat_member(VIP_CHANNEL_ID, uid)
                        await app.bot.unban_chat_member(VIP_CHANNEL_ID, uid) # Optional: unban to allow rejoin later
                    except Exception as e:
                        log.error(f"Failed to kick user {uid}: {e}")
                    set_user(uid, None, None)
        except Exception as e:
            log.error(f"Expire task error: {e}")

        await asyncio.sleep(3600)

# =========================
# ADS SCHEDULER
# =========================
async def ads_scheduler(app: Application):
    log.info("Ads scheduler started")
    while True:
        try:
            now = datetime.utcnow().isoformat()

            cur.execute(
                """
                SELECT id, content_type, file_id, text
                FROM ads
                WHERE message_id IS NULL AND post_time <= ?
                """,
                (now,),
            )

            for ad_id, ctype, fid, text in cur.fetchall():
                try:
                    msg = None
                    caption_text = text + f"\n\n📞 @{ADMIN_USERNAME}"
                    
                    if ctype == "text":
                        msg = await app.bot.send_message(MAIN_CHANNEL, text)
                    elif ctype == "photo":
                        msg = await app.bot.send_photo(
                            MAIN_CHANNEL,
                            fid,
                            caption=caption_text,
                        )
                    else:
                        msg = await app.bot.send_video(
                            MAIN_CHANNEL,
                            fid,
                            caption=caption_text,
                        )
                    
                    if msg:
                        cur.execute(
                            "UPDATE ads SET message_id=? WHERE id=?",
                            (msg.message_id, ad_id),
                        )
                        conn.commit()
                except Exception as inner_e:
                    log.error(f"Failed to send ad {ad_id}: {inner_e}")
                    
        except Exception as e:
            log.error(f"Ads scheduler error: {e}")

        await asyncio.sleep(30)

# =========================
# POST INIT (FIX FOR LOOPS)
# =========================
async def post_init(application: Application):
    """
    Starts background tasks after the application is initialized.
    This fixes the 'Task created while app is not running' warning.
    """
    application.create_task(expire_task(application))
    application.create_task(ads_scheduler(application))

# =========================
# MAIN ENTRY
# =========================
def main():
    """
    Main function must be synchronous to avoid 'Event loop is already running'
    errors when using app.run_polling().
    """
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy_vip, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(choose_method, pattern="^pay_"))
    app.add_handler(MessageHandler(filters.PHOTO, receive_payment))

    log.info("Zan Movie Bot started...")
    # run_polling handles the asyncio loop internally
    app.run_polling()

if __name__ == "__main__":
    main()
