# ============================================================
# Zan Movie Channel Bot – COMPLETE MERGED VERSION
# python-telegram-bot v20+
# ============================================================

import os
import logging
import sqlite3
import calendar
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIGURATION
# =====================================================

BOT_TOKEN = "8515688348:AAHkgGjz06M0BXBIqSuQzl2m_OFuUbakHAI"

ADMIN_ID = 6445257462

MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
# ကြော်ညာ Post တင်ရန်အတွက် Channel Username (Bot သည် Admin ဖြစ်ရမည်)
CHANNEL_USERNAME = "@ZanchannelMM" 

VIP_CHANNEL_URL = "https://t.me/+bDFiZZ9gwRRjY2M1"

# Default Values
DEFAULT_PRICE = 10000
DEFAULT_PHONE = "09960202983"
DEFAULT_NAME = "Sai Zaw Ye Lwin"

DB_NAME = "movie_bot.db"

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger("ZanMovieBot")

# ============================================================
# DATABASE INIT
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Users Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        is_vip INTEGER DEFAULT 0,
        vip_expiry TEXT
    )
    """)

    # Payments History Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method TEXT,
        account_name TEXT,
        amount INTEGER,
        status TEXT,
        created_at TEXT
    )
    """)

    # Payment Settings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_settings (
        method TEXT PRIMARY KEY,
        qr TEXT,
        phone TEXT,
        name TEXT
    )
    """)

    # Ads Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        total_days INTEGER,
        interval_hours INTEGER,
        next_post TEXT,
        end_at TEXT,
        active INTEGER
    )
    """)

    # --- MIGRATION: နာမည်ဟောင်းများကို အကြီးစာလုံးပြောင်းရန် ---
    try:
        cur.execute("UPDATE payment_settings SET method='WAVE' WHERE method='Wave'")
        cur.execute("UPDATE payment_settings SET method='AYA' WHERE method='Aya'")
        cur.execute("UPDATE payment_settings SET method='CB' WHERE method='Cb'")
        conn.commit()
    except Exception:
        pass 

    # Default Payment Methods အချက်အလက်များထည့်သွင်းခြင်း
    for m in ["KBZ", "WAVE", "AYA", "CB"]:
        cur.execute("""
            INSERT INTO payment_settings(method, phone, name) VALUES (?, ?, ?)
            ON CONFLICT(method) DO UPDATE SET phone=excluded.phone, name=excluded.name
        """, (m, DEFAULT_PHONE, DEFAULT_NAME))

    conn.commit()
    conn.close()

# ============================================================
# STATES DEFINITION
# ============================================================

# User Side States
WAITING_SLIP = 1
WAITING_NAME = 2

# Admin Side States
AD_MEDIA = 10
AD_DAYS = 11
AD_INTERVAL = 12

# Admin Payment Edit States
PAY_PHONE = 21
PAY_NAME_EDIT = 22

# ============================================================
# 1. USER SIDE LOGIC
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔ Screenshot (SS) မရ\n"
        "⛔ Screen Record မရ\n"
        "⛔ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({DEFAULT_PRICE} MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]

    # Admin ဖြစ်လျှင် Dashboard ခလုတ်ပြရန်
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin_dashboard")])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
         "⛔ channel နှင့် bot ကိုထွက်မိ၊ဖျတ်မိပါက link ပြန်မပေးပါ\n"
        "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔ တစ်ကြိမ်ထဲ အပြည့်လွဲရပါမည်\n\n"
        "ဆက်လက်လုပ်ဆောင်မလား?"
    )

    # BUG FIX: Conflict မဖြစ်စေရန် callback_data ကို choose_payment ဟု ပြောင်းလဲထားပါသည်
    keyboard = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="choose_payment")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")],
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # "Pay" စာသားများ ပြန်လည်ထည့်သွင်းပေးထားပါသည်
    keyboard = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")],
    ]

    await query.message.edit_text(
        "ငွေပေးချေမှုနည်းလမ်း ရွေးပါ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    # DB မှ အချက်အလက်ယူခြင်း
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT phone, name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()

    ph_num = row[0] if row and row[0] else DEFAULT_PHONE
    acc_name = row[1] if row and row[1] else DEFAULT_NAME

    text = (
        f"ငွေလွဲရန် ({DEFAULT_PRICE} MMK)\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: `{ph_num}`\n"
        f"👤 အမည်: {acc_name}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    await query.message.edit_text(text, parse_mode="Markdown")

    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("ပြေစာ Screenshot ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည် (သို့) Last 4 Digits ပို့ပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = update.message.text
    method = context.user_data.get("method", "Unknown")
    slip = context.user_data.get("slip")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user.id, method, name, DEFAULT_PRICE, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
    )

    # Admin ထံ ပို့မည့်ခလုတ်များ
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ လက်ခံမည်", callback_data=f"admin_ok_{user.id}")],
        [InlineKeyboardButton("❌ ငြင်းပယ်မည်", callback_data=f"admin_fail_{user.id}")]
    ])

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=slip,
            caption=(
                "🔔 **VIP Payment Request**\n\n"
                f"User ID: `{user.id}`\n"
                f"Username: @{user.username}\n"
                f"Method: {method}\n"
                f"Name: {name}\n"
                f"Amount: {DEFAULT_PRICE}"
            ),
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        log.error(f"Admin ထံ ပေးစာပို့ရန် မအောင်မြင်ပါ: {e}")

    return ConversationHandler.END

# ============================================================
# 2. ADMIN SIDE LOGIC
# ============================================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    query = update.callback_query
    if query: 
        await query.answer()
    
    kb = [
        [InlineKeyboardButton("📊 ဝင်ငွေစာရင်း", callback_data="stats")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="ads")],
        [InlineKeyboardButton("💳 Payment အချက်အလက်ပြင်ရန်", callback_data="pay_menu")],
        [InlineKeyboardButton("Back to Home", callback_data="back_home")],
    ]

   async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")[1:]
    user_id = int(user_id)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if action == "ok":
        expiry_dt = datetime.now() + timedelta(days=30)
        expiry = expiry_dt.isoformat()

        # VIP status update
        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)",
            (user_id, expiry)
        )
        cur.execute(
            "UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'",
            (user_id,)
        )
        conn.commit()

        try:
            # 🔐 Single-use invite link (1 user only)
            invite = await context.bot.create_chat_invite_link(
                chat_id=VIP_CHANNEL_ID,
                name=f"vip_{user_id}",
                member_limit=1,
                expire_date=expiry_dt
            )
            invite_link = invite.invite_link

            await context.bot.send_message(
                chat_id=user_id,
                text="✅ ငွေပေးချေမှု အောင်မြင်ပါသည်။ VIP Member ဖြစ်ပါပြီ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("VIP Channel ဝင်ရန်", url=invite_link)]
                ])
            )

            await query.edit_message_caption(
                query.message.caption + "\n\n✅ APPROVED"
            )
        except:
            pass

    else:
        cur.execute(
            "UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'",
            (user_id,)
        )
        conn.commit()

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ ငွေပေးချေမှု မအောင်မြင်ပါ။ (ငွေမဝင်ခြင်း သို့မဟုတ် အချက်အလက်မှားယွင်းခြင်း)"
            )
            await query.edit_message_caption(
                query.message.caption + "\n\n❌ REJECTED"
            )
        except:
            pass

    conn.close()


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    now = datetime.now()
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (now.date().isoformat(),))
    today_income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total_income = cur.fetchone()[0] or 0

    conn.close()

    text = f"📊 ဝင်ငွေစာရင်း\n\n📅 ယနေ့: {today_income} MMK\n💰 စုစုပေါင်း: {total_income} MMK"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_dashboard")]]))

# --- ADS SCHEDULER ---

async def ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📸 Photo သို့မဟုတ် 🎥 Video ပို့ပါ (Caption ပါထည့်ရေးပေးပါ)")
    return AD_MEDIA

async def ads_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        context.user_data["media"] = ("photo", msg.photo[-1].file_id, msg.caption or "")
    elif msg.video:
        context.user_data["media"] = ("video", msg.video.file_id, msg.caption or "")
    else:
        await msg.reply_text("Photo/Video ပို့ပေးပါ")
        return AD_MEDIA

    await msg.reply_text("📅 ဘယ်နှစ်ရက်တင်မလဲ? (နံပါတ်သာရိုက်ပါ)")
    return AD_DAYS

async def ads_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["days"] = int(update.message.text)
    except:
        return AD_DAYS
    await update.message.reply_text("⏱️ ဘယ်နှနာရီခြားတစ်ခါ တင်မလဲ? (နံပါတ်သာရိုက်ပါ)")
    return AD_INTERVAL

async def ads_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = int(update.message.text)
    except:
        return AD_INTERVAL

    media_type, file_id, caption = context.user_data["media"]
    days = context.user_data["days"]
    now = datetime.now()
    end = now + timedelta(days=days)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO ads(media_type,file_id,caption,total_days,interval_hours,next_post,end_at,active) VALUES(?,?,?,?,?,?,?,1)",
                (media_type, file_id, caption, days, hours, now.isoformat(), end.isoformat()))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ ကြော်ညာ schedule ပြီးပါပြီ")
    return ConversationHandler.END

async def post_ads_job(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT id, media_type, file_id, caption, interval_hours, end_at FROM ads WHERE active=1 AND next_post <= ?", (now.isoformat(),))
    ads = cur.fetchall()
    
    for ad in ads:
        ad_id, m_type, f_id, cap, interval, end_str = ad
        try:
            if m_type == "photo": await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=f_id, caption=cap)
            else: await context.bot.send_video(chat_id=CHANNEL_USERNAME, video=f_id, caption=cap)
        except: pass
            
        next_time = now + timedelta(hours=interval)
        if now >= datetime.fromisoformat(end_str): cur.execute("UPDATE ads SET active=0 WHERE id=?", (ad_id,))
        else: cur.execute("UPDATE ads SET next_post=? WHERE id=?", (next_time.isoformat(), ad_id))
    conn.commit()
    conn.close()

# --- PAYMENT EDIT ---

async def pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("KBZ", callback_data="edit_KBZ")],
        [InlineKeyboardButton("Wave", callback_data="edit_WAVE")],
        [InlineKeyboardButton("AYA", callback_data="edit_AYA")],
        [InlineKeyboardButton("CB", callback_data="edit_CB")],
        [InlineKeyboardButton("Back", callback_data="admin_dashboard")]
    ]
    await query.message.edit_text("💳 ပြင်လိုသော Payment ရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def pay_phone_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["edit_method"] = query.data.split("_")[1]
    await query.message.delete()
    await query.message.chat.send_message("📱 ဖုန်းနံပါတ် အသစ်ရိုက်ထည့်ပါ (မပြင်လိုလျှင် /skip)")
    return PAY_PHONE

async def pay_phone_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["new_phone"] = text if text != "/skip" else None
    await update.message.reply_text("👤 အကောင့်နာမည် အသစ်ရိုက်ထည့်ပါ (မပြင်လိုလျှင် /skip)")
    return PAY_NAME_EDIT

async def pay_name_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text if update.message.text != "/skip" else None
    method, new_phone = context.user_data["edit_method"], context.user_data.get("new_phone")
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    if new_phone: cur.execute("UPDATE payment_settings SET phone=? WHERE method=?", (new_phone, method))
    if new_name: cur.execute("UPDATE payment_settings SET name=? WHERE method=?", (new_name, method))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ သိမ်းဆည်းပြီးပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_dashboard")]]))
    return ConversationHandler.END

# ============================================================
# MAIN
# ============================================================

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Ads Job Scheduler
    if app.job_queue:
        app.job_queue.run_repeating(post_ads_job, interval=60, first=10)

    # Handlers
    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)], WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]},
        fallbacks=[CommandHandler("start", start)],
    )
    ads_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ads_start, pattern="^ads$")],
        states={AD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, ads_media)], AD_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_days)], AD_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_interval)]},
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")],
    )
    pay_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_phone_ask, pattern="^edit_")],
        states={PAY_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_phone_save), CommandHandler("skip", pay_phone_save)], PAY_NAME_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_name_save), CommandHandler("skip", pay_name_save)]},
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", tharngal_command))
    app.add_handler(user_conv); app.add_handler(ads_conv); app.add_handler(pay_edit_conv)
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^choose_payment$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(admin_payment_action, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(pay_menu, pattern="^pay_menu$"))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
