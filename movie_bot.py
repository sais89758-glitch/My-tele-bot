import logging
import sqlite3
import threading
import re
import os
import base64
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Final

import httpx
import anyio

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
    ConversationHandler,
    filters,
)
from telegram.constants import ParseMode

# =====================================================
# CONFIG
# =====================================================
BOT_TOKEN: Final = "8515688348:AAEFbdCJ6HHR6p4cCgzvUvcRDr7i7u-sL6U"
ADMIN_ID: Final = 6445257462
CHANNEL_USERNAME: Final = "ZanchannelMM"
DB_NAME: Final = "movie.db"

PRICE_BASIC_VIP: Final = 10000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

ADD_MOVIE, WAIT_RECEIPT = range(2)

# =====================================================
# KEEP ALIVE (Render / Railway)
# =====================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# =====================================================
# DATABASE
# =====================================================
def db(query, args=(), one=False):
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        res = cur.fetchone() if one else cur.fetchall()
        conn.close()
        return res

def init_db():
    db("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        vip_until DATETIME
    )""")
    db("""CREATE TABLE IF NOT EXISTS movies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        price INTEGER,
        post_id INTEGER,
        created DATETIME
    )""")
    db("""CREATE TABLE IF NOT EXISTS unlocks(
        user_id INTEGER,
        movie_id INTEGER,
        PRIMARY KEY(user_id, movie_id)
    )""")

# =====================================================
# START / HOME
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    user = update.effective_user
    db("INSERT OR IGNORE INTO users (user_id, name) VALUES (?,?)", (user.id, user.full_name))

    text = (
        "🎬 **Zan Movie Bot**\n\n"
        "⚠️ သတိပြုရန်\n"
        "- Screenshot (SS) ❌\n"
        "- Screen Record ❌\n"
        "- Download ❌\n"
        "- Forward ❌\n\n"
        "VIP မဝင် / မဝယ်ပါက ၃ မိနစ် Preview သာ ရပါမည်။"
    )

    kb = [
        [InlineKeyboardButton("👑 VIP ဝင်ရန်", callback_data="vip_buy")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movies_1")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=f"https://t.me/{CHANNEL_USERNAME}")],
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# =====================================================
# ADMIN ADD MOVIE
# =====================================================
async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "🎬 Video ကို Caption နဲ့ပို့ပါ\n\n"
        "ပုံစံ👇\n"
        "#1000\n"
        "ဇာတ်ကားအမည်"
    )
    return ADD_MOVIE

async def admin_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    if not update.message.video or not update.message.caption:
        await update.message.reply_text("❌ Video + Caption လိုအပ်ပါတယ်")
        return ADD_MOVIE

    try:
        lines = update.message.caption.strip().splitlines()
        price = int(re.search(r"#(\d+)", lines[0]).group(1))
        title = lines[1].strip()

        msg = await context.bot.send_video(
            chat_id=f"@{CHANNEL_USERNAME}",
            video=update.message.video.file_id,
            caption=f"🎬 **{title}**\n💰 {price} MMK",
            parse_mode=ParseMode.MARKDOWN,
            protect_content=True
        )

        db(
            "INSERT INTO movies (title, price, post_id, created) VALUES (?,?,?,?)",
            (title, price, msg.message_id, datetime.now())
        )

        await update.message.reply_text(f"✅ `{title}` တင်ပြီးပါပြီ")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Caption ပုံစံမှားနေပါတယ်")

    return ConversationHandler.END

# =====================================================
# MOVIE MENU
# =====================================================
async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    page = int(update.callback_query.data.split("_")[1])

    movies = db(
        "SELECT id, title, price, post_id FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?",
        ((page - 1) * 6,)
    )

    if not movies:
        await update.callback_query.message.edit_text("မရှိသေးပါ")
        return

    kb = [
        [InlineKeyboardButton(f"{m[1]} ({m[2]}Ks)", url=f"https://t.me/{CHANNEL_USERNAME}/{m[3]}")]
        for m in movies
    ]

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"movies_{page-1}"))
    if len(movies) == 6:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"movies_{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await update.callback_query.message.edit_text(
        "🎬 **ဇာတ်ကားစာရင်း**",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )

# =====================================================
# VIP BUY (AUTO)
# =====================================================
async def vip_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["vip_amount"] = PRICE_BASIC_VIP

    text = (
        "👑 **VIP 1 Month**\n"
        f"💰 {PRICE_BASIC_VIP} MMK\n\n"
        "⚠️ Note မှာ Channel / Movie မရေးပါနဲ့\n"
        "ငွေလွဲပြီး Screenshot ပို့ပါ"
    )

    await update.callback_query.message.edit_text(text)
    return WAIT_RECEIPT

async def vip_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Screenshot ပို့ပါ")
        return WAIT_RECEIPT

    vip_until = datetime.now() + timedelta(days=30)
    db("UPDATE users SET vip_until=? WHERE user_id=?", (vip_until, update.effective_user.id))

    await update.message.reply_text(
        "✅ **VIP အတည်ပြုပြီးပါပြီ**\n"
        "VIP ဝင်နေချိန် ဖွင့်ထားသော ကားများကို ရာသက်ပန် ကြည့်နိုင်ပါသည်။",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

# =====================================================
# MAIN
# =====================================================
def main():
    init_db()
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={ADD_MOVIE: [MessageHandler(filters.VIDEO, admin_add_movie)]},
        fallbacks=[]
    )

    vip_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(vip_buy, pattern="^vip_buy$")],
        states={WAIT_RECEIPT: [MessageHandler(filters.PHOTO, vip_receipt)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(admin_conv)
    app.add_handler(vip_conv)

    app.add_handler(CallbackQueryHandler(start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movies_"))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
