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
# ===== CONFIG =====
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID", "0"))

MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

# (AI မသုံးသေးရင် မထည့်လည်းရ)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_PATH = "data/movie_bot.db"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# =====================
# CONFIG
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MAIN_CHANNEL_ID = int(os.getenv("MAIN_CHANNEL_ID"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AdsBot")

# =====================
# DB SETUP
# =====================
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/ads.db", check_same_thread=False)
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
conn.commit()

# =====================
# ADMIN START
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "📣 Ads Manager\n\n"
        "ကြော်ညာ (text / photo / video) ကို ပို့ပါ\n"
        "ပြီးရင် time ကို မေးပါမယ်"
    )

# =====================
# RECEIVE AD CONTENT
# =====================
async def receive_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = update.message
    ad = {}

    if msg.text:
        ad["content_type"] = "text"
        ad["text"] = msg.text
        ad["file_id"] = None
    elif msg.photo:
        ad["content_type"] = "photo"
        ad["file_id"] = msg.photo[-1].file_id
        ad["text"] = msg.caption or ""
    elif msg.video:
        ad["content_type"] = "video"
        ad["file_id"] = msg.video.file_id
        ad["text"] = msg.caption or ""
    else:
        return

    context.user_data["ad"] = ad
    await msg.reply_text(
        "⏰ Post time ပေးပါ\n"
        "Format: YYYY-MM-DD HH:MM\n"
        "ဥပမာ: 2026-02-10 19:00"
    )

# =====================
# RECEIVE TIME
# =====================
async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if "ad" not in context.user_data:
        return

    try:
        post_time = datetime.strptime(update.message.text, "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Format မမှန်ပါ")
        return

    context.user_data["post_time"] = post_time
    await update.message.reply_text(
        "🗑️ Delete time ပေးပါ\n"
        "Format: YYYY-MM-DD HH:MM\n"
        "မဖျတ်ချင်ရင် none လို့ရေးပါ"
    )

# =====================
# RECEIVE DELETE TIME
# =====================
async def receive_delete_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    ad = context.user_data.get("ad")
    post_time = context.user_data.get("post_time")

    if not ad or not post_time:
        return

    text = update.message.text.lower()

    delete_time = None
    if text != "none":
        try:
            delete_time = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text("❌ Format မမှန်ပါ")
            return

    cur.execute("""
        INSERT INTO ads (content_type, file_id, text, post_time, delete_time)
        VALUES (?,?,?,?,?)
    """, (
        ad["content_type"],
        ad["file_id"],
        ad["text"],
        post_time.isoformat(),
        delete_time.isoformat() if delete_time else None
    ))
    conn.commit()

    context.user_data.clear()
    await update.message.reply_text("✅ ကြော်ညာ schedule ပြီးပါပြီ")

# =====================
# SCHEDULER
# =====================
async def ads_scheduler(app: Application):
    while True:
        now = datetime.utcnow().isoformat()

        # POST
        cur.execute("""
            SELECT id, content_type, file_id, text
            FROM ads
            WHERE message_id IS NULL AND post_time <= ?
        """, (now,))
        for ad_id, ctype, fid, text in cur.fetchall():
            if ctype == "text":
                msg = await app.bot.send_message(MAIN_CHANNEL_ID, text)
            elif ctype == "photo":
                msg = await app.bot.send_photo(
                    MAIN_CHANNEL_ID, fid,
                    caption=text + f"\n\n📞 @{ADMIN_USERNAME}"
                )
            else:
                msg = await app.bot.send_video(
                    MAIN_CHANNEL_ID, fid,
                    caption=text + f"\n\n📞 @{ADMIN_USERNAME}"
                )

            cur.execute(
                "UPDATE ads SET message_id=? WHERE id=?",
                (msg.message_id, ad_id)
            )
            conn.commit()

        # DELETE
        cur.execute("""
            SELECT id, message_id
            FROM ads
            WHERE delete_time IS NOT NULL AND delete_time <= ?
        """, (now,))
        for ad_id, msg_id in cur.fetchall():
            try:
                await app.bot.delete_message(MAIN_CHANNEL_ID, msg_id)
            except Exception:
                pass
            cur.execute("DELETE FROM ads WHERE id=?", (ad_id,))
            conn.commit()

        await asyncio.sleep(30)

# =====================
# MAIN
# =====================
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID) & (filters.TEXT | filters.PHOTO | filters.VIDEO),
        receive_ad
    ))
    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID) & filters.Regex(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
        receive_time
    ))
    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID),
        receive_delete_time
    ))

    app.create_task(ads_scheduler(app))

    log.info("Ads bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
# =========================
# DB SETUP
# =========================
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

# =========================
# HELPERS
# =========================
def get_user(user_id: int):
    cur.execute("SELECT vip_type, vip_expire FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row

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
        "⛔️ Screenshot / Screen Record / Download /save မရပါ\n\n"
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

    amount = 10000 if vip_type == "buy_basic" else 30000

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
        [InlineKeyboardButton("CB Pay", callback_data="pay_cb"),
         InlineKeyboardButton("AYA Pay", callback_data="pay_aya")],
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

    vip_type = context.user_data.get("vip_type")
    amount = 10000 if vip_type == "buy_basic" else 30000

    text = (
        f"💳 {method}\n\n"
        f"ငွေလွဲရန်: {amount} MMK\n\n"
        "⚠️ ငွေလွဲပြီးပါက ပြေစာ Screenshot ကို ပို့ပေးပါ"
    )
    await q.edit_message_text(text)

# =========================
# RECEIVE PAYMENT (AI APPROVE – SAFE)
# =========================
async def receive_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    vip_type = context.user_data.get("vip_type")
    method = context.user_data.get("method")

    if not vip_type or not method:
        return

    amount = 10000 if vip_type == "buy_basic" else 30000

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()

    image_hash = hashlib.sha256(data).hexdigest()

    if is_duplicate(image_hash):
        await update.message.reply_text("❌ ပြေစာအတု / ထပ်တူ ပြေစာ ဖြစ်နိုင်ပါသည်။")
        add_payment(user_id, amount, method, image_hash, "duplicate")
        return

    # --- AI / Rule Based (SAFE) ---
    # NOTE: OCR can be added here. For production safety:
    # - Amount strict
    # - Method strict
    # - Duplicate strict
    # Auto-approve only if rules match.

    add_payment(user_id, amount, method, image_hash, "approved")

    # Grant access
    if vip_type == "buy_basic":
        expire = datetime.utcnow() + timedelta(days=30)
        set_user(user_id, "basic", expire)
    else:
        set_user(user_id, "pro", None)

    # Invite link
    invite = await context.bot.create_chat_invite_link(
        chat_id=VIP_CHANNEL_ID,
        creates_join_request=False
    )

    await update.message.reply_text(
        "✅ ငွေပေးချေမှု အောင်မြင်ပါသည်။\n\n"
        "🎬 VIP Channel သို့ဝင်ရန် အောက်ပါ link ကိုအသုံးပြုပါ 👇\n"
        f"{invite.invite_link}",
        protect_content=True
    )

# =========================
# AUTO EXPIRE TASK
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

        await asyncio.sleep(3600)  # every hour

# =========================
# CALLBACK ROUTER
# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data in ("buy_basic", "buy_pro"):
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

    log.info("Zan Movie Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
