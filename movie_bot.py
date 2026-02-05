# Zan Movie Channel Bot – FINAL CLEAN VERSION
# python-telegram-bot v20+
# Polling | Single instance

import calendar
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8515688348:AAHKbL-alScUufoYbciwO-E3V4pKCRdHMVk")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6445257462"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "lucus2252")

VIP_PRICE = 30000
MAIN_CHANNEL_URL = os.getenv("MAIN_CHANNEL_URL", "https://t.me/ZanchannelMM")
MAIN_CHANNEL_ID = os.getenv("MAIN_CHANNEL_ID", "@ZanchannelMM")
VIP_CHANNEL_ID = os.getenv("VIP_CHANNEL_ID", "-1003863175003")  # numeric ID recommended
VIP_CHANNEL_FALLBACK = os.getenv("VIP_CHANNEL_URL", "https://t.me/+bDFiZZ9gwRRjY2M1")

DB_PATH = os.getenv("DB_PATH", "movie_bot.db")

PAY_PHONE_DEFAULT = "09960202983"
PAY_NAME_DEFAULT = "Sai Zaw Ye Lwin"

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ZanMovieBot")

# ================= STATES =================
(
    WAITING_SLIP,
    WAITING_NAME,
    WAITING_AD_MEDIA,
    WAITING_AD_DAYS,
    WAITING_AD_INTERVAL,
    PAY_SET_QR,
    PAY_SET_PHONE,
    PAY_SET_NAME,
) = range(8)

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def now_iso():
    return datetime.now().isoformat()


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_vip INTEGER DEFAULT 0,
        vip_expiry TEXT,
        vip_invite_link TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        method TEXT,
        account_name TEXT,
        slip_file_id TEXT,
        status TEXT,
        amount INTEGER,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_settings (
        method TEXT PRIMARY KEY,
        qr_id TEXT,
        phone TEXT,
        account_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ad_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        total_days INTEGER,
        interval_hours INTEGER,
        start_at TEXT,
        end_at TEXT,
        next_post_at TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ad_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        message_id INTEGER,
        posted_at TEXT
    )
    """)

    for m in ["KBZ", "Wave", "AYA", "CB"]:
        cur.execute(
            "INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)",
            (m, PAY_PHONE_DEFAULT, PAY_NAME_DEFAULT),
        )

    conn.commit()
    conn.close()

# ================= HELPERS =================
async def ensure_user(update: Update):
    user = update.effective_user
    if not user:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username),
    )
    cur.execute("UPDATE users SET username=? WHERE user_id=?", (user.username, user.id))
    conn.commit()
    conn.close()


async def create_personal_invite_link(context, user_id, expiry_dt):
    if not VIP_CHANNEL_ID:
        return VIP_CHANNEL_FALLBACK
    invite = await context.bot.create_chat_invite_link(
        chat_id=VIP_CHANNEL_ID,
        name=f"vip_{user_id}_{int(expiry_dt.timestamp())}",
        expire_date=expiry_dt,
        member_limit=1,
    )
    return invite.invite_link


async def send_admin_payment(context, slip_file_id, caption, keyboard):
    try:
        await context.bot.send_photo(
            chat_id=f"@{ADMIN_USERNAME}",
            photo=slip_file_id,
            caption=caption,
            reply_markup=keyboard,
        )
    except:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=slip_file_id,
            caption=caption,
            reply_markup=keyboard,
        )

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_vip, vip_expiry FROM users WHERE user_id=?", (update.effective_user.id,))
    row = cur.fetchone()
    conn.close()

    buttons = [[InlineKeyboardButton(f"👑 VIP ဝင်ရန် - {VIP_PRICE} MMK", callback_data="vip_buy")]]

    if row and row["is_vip"] == 1 and row["vip_expiry"]:
        if datetime.fromisoformat(row["vip_expiry"]) > datetime.now():
            buttons.append([InlineKeyboardButton("VIP Channel ဝင်ရန်", callback_data="open_vip_channel")])

    buttons.append([InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)])

    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ================= MAIN =================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    logger.info("Zan Movie Channel Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
