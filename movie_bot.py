# ============================================================
# Zan Movie Channel Bot – FINAL FIXED VERSION
# python-telegram-bot v20+
# ============================================================

import logging
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
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIGURATION
# =====================================================

BOT_TOKEN = "8515688348:AAG9tp1ZJ03MVmxdNe26ZO1x9SFrDA3-FYY"
ADMIN_ID = 6445257462
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
CHANNEL_USERNAME = "@ZanchannelMM" 
VIP_CHANNEL_ID = -1003863175003

DEFAULT_PRICE = 10000 
DEFAULT_PHONE = "09960202983"
DEFAULT_NAME = "Sai Zaw Ye Lwin"
DB_NAME = "movie_bot.db"

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ============================================================
# DATABASE INIT
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, 
        account_name TEXT, amount INTEGER, status TEXT, created_at TEXT, ref_code TEXT)""")
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr TEXT, phone TEXT, name TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, media_type TEXT, file_id TEXT, caption TEXT, 
        total_days INTEGER, interval_hours INTEGER, next_post TEXT, end_at TEXT, active INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS inviters (
        code TEXT PRIMARY KEY, name TEXT, total_count INTEGER DEFAULT 0, 
        monthly_count INTEGER DEFAULT 0, last_month TEXT)""")
    
    # Default Payment Methods
    for m in ["KBZ", "WAVE", "AYA", "CB"]:
        cur.execute("INSERT OR IGNORE INTO payment_settings(method, phone, name) VALUES (?, ?, ?)", (m, DEFAULT_PHONE, DEFAULT_NAME))
    conn.commit()
    conn.close()

# ============================================================
# STATES
# ============================================================
# User Side
WAITING_SLIP, WAITING_NAME, WAITING_REF = range(1, 4)
# Admin Ads
AD_MEDIA, AD_DAYS, AD_INTERVAL = range(10, 13)
# Admin Inviter
INVITER_CODE, INVITER_NAME = range(20, 22)
# Admin Edit Pay
PAY_PHONE, PAY_NAME_EDIT = range(30, 32)

# ============================================================
# 1. USER SIDE (VIP BUY)
# ============================================================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="choose_payment")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔ channel နှင့် bot ကို ထွက်မိ / ဖျတ်မိပါက link ပြန်မပေးပါ\n"
        "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔ တစ်ကြိမ်ထဲ အပြည့်လွဲရပါမည်\n\n"
        "ဆက်လက်လုပ်ဆောင်မလား?"
    )

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# 2. ADMIN SIDE
# ============================================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    # Handle both Message and CallbackQuery updates
    if update.callback_query:
        try: await update.callback_query.answer()
        except: pass
        msg_obj = update.callback_query.message
    else:
        msg_obj = update.message

    kb = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("➕ Add Agent", callback_data="add_inviter")],
        [InlineKeyboardButton("📢 Post Ad", callback_data="ads"), InlineKeyboardButton("💳 Edit Pay", callback_data="pay_menu")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="back_home")]
    ]
    msg = "🛠 **Admin Dashboard**"
    
    if update.callback_query:
        await msg_obj.edit_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await msg_obj.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ConversationHandler.END

# --- Agent Flow ---
async def add_inviter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("🔤 Agent Code သတ်မှတ်ပါ (ဥပမာ: AG01)")
    return INVITER_CODE

async def inviter_code_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tmp_code"] = update.message.text.strip()
    await update.message.reply_text("👤 Agent အမည် ရိုက်ထည့်ပါ")
    return INVITER_NAME

async def inviter_name_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data["tmp_code"]
    name = update.message.text.strip()
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO inviters (code, name, last_month) VALUES (?,?,?)", (code, name, datetime.now().strftime("%Y-%m")))
        conn.commit()
        await update.message.reply_text(f"✅ အောင်မြင်ပါသည် - {name} ({code})")
    except:
        await update.message.reply_text("❌ Code ရှိပြီးသားဖြစ်နေသည်။")
    conn.close()
    await admin_dashboard(update, context)
    return ConversationHandler.END

# --- Ads Flow ---
async def ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("📸 ကြော်ညာပုံ (သို့) Video ပို့ပေးပါ (Caption ပါတစ်ခါတည်းထည့်ပါ)")
    return AD_MEDIA

async def ads_media_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo: context.user_data["ad_m"] = ("photo", msg.photo[-1].file_id, msg.caption or "")
    elif msg.video: context.user_data["ad_m"] = ("video", msg.video.file_id, msg.caption or "")
    else: return AD_MEDIA
    await msg.reply_text("📅 ဘယ်နှစ်ရက် တင်မလဲ? (နံပါတ်သာ)")
    return AD_DAYS

async def ads_days_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_d"] = update.message.text
    await update.message.reply_text("⏱️ ဘယ်နှနာရီခြား တစ်ခါတင်မလဲ? (နံပါတ်သာ)")
    return AD_INTERVAL

async def ads_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days, hrs = int(context.user_data["ad_d"]), int(update.message.text)
        m_type, fid, cap = context.user_data["ad_m"]
        now = datetime.now()
        conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
        cur.execute("INSERT INTO ads(media_type,file_id,caption,total_days,interval_hours,next_post,end_at,active) VALUES(?,?,?,?,?,?,?,1)",
                    (m_type, fid, cap, days, hrs, now.isoformat(), (now + timedelta(days=days)).isoformat()))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ ကြော်ညာ Schedule လုပ်ပြီးပါပြီ။")
    except:
        await update.message.reply_text("❌ မှားယွင်းမှုရှိသည်။ နံပါတ်ပဲ ရိုက်ပါ။")
    await admin_dashboard(update, context)
    return ConversationHandler.END

# --- Stats & Approval ---
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    now = datetime.now()
    today_str = now.date().isoformat()
    current_month_str = now.strftime("%Y-%m")
    
    # 1. Today Income
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (today_str,))
    today_inc = cur.fetchone()[0] or 0
    
    # 2. Monthly Income
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND strftime('%Y-%m', created_at)=?", (current_month_str,))
    month_inc = cur.fetchone()[0] or 0

    # 3. Total Income
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total_inc = cur.fetchone()[0] or 0
    
    # 4. VIP & User Stats
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vips = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    rejected_count = cur.fetchone()[0] or 0

    # 5. Last 7 Days Breakdown
    daily_stats = ""
    # Loop for last 7 days (including today)
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d") # for query
        d_disp = d.strftime("%m-%d")   # for display
        
        cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (d_str,))
        day_amt = cur.fetchone()[0] or 0
        daily_stats += f"{d_disp} : {day_amt} MMK\n"
        
    conn.close()
    
    txt = (
        f"💰 **ဝင်ငွေ အကျဉ်းချုပ်**\n\n"
        f"ယနေ့ ဝင်ငွေ : {today_inc} MMK\n"
        f"ယခုလ ဝင်ငွေ : {month_inc} MMK\n"
        f"စုစုပေါင်း ဝင်ငွေ : {total_inc} MMK\n\n"
        f"👥 **VIP အခြေအနေ**\n\n"
        f"VIP စုစုပေါင်း : {vips} ယောက်\n"
        f"Rejected (ငွေလွဲမအောင်မြင် / ပယ်ချထား) : {rejected_count} ယောက်\n\n"
        f"📅 **နေ့ရက်အလိုက် ဝင်ငွေ (နောက်ဆုံး ၇ ရက်)**\n\n"
        f"{daily_stats}"
    )
    
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]]
    await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    action, uid = query.data.split("_")[1], int(query.data.split("_")[2])
    
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    if action == "ok":
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (uid, (datetime.now()+timedelta(days=30)).isoformat()))
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (uid,))
        # Referral count update
        cur.execute("SELECT ref_code FROM payments WHERE user_id=? AND status='APPROVED' ORDER BY id DESC LIMIT 1", (uid,))
        ref = cur.fetchone()
        if ref and ref[0]:
            cur.execute("UPDATE inviters SET total_count=total_count+1, monthly_count=monthly_count+1 WHERE code=?", (ref[0],))
        conn.commit()
        try:
            link = await context.bot.create_chat_invite_link(chat_id=VIP_CHANNEL_ID, member_limit=1)
            await context.bot.send_message(uid, f"✅ အတည်ပြုပြီးပါပြီ။\nLink: {link.invite_link}")
        except: pass
    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (uid,))
        conn.commit()
        try: await context.bot.send_message(uid, "❌ သင်၏ငွေလွှဲမှု ငြင်းပယ်ခံရပါသည်။")
        except: pass
    conn.close()
    await query.edit_message_caption(query.message.caption + f"\n\nDone: {action.upper()}")

# ============================================================
# MAIN
# ============================================================

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # -----------------------------------------------------------
    # FIX: Removed 'group=' from ConversationHandler constructors
    # -----------------------------------------------------------

    # 1. User VIP Flow
    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_ref), 
                CallbackQueryHandler(process_ref, pattern="^skip_ref$")
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    # 2. Admin Ads Flow
    ads_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ads_start, pattern="^ads$")],
        states={
            AD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, ads_media_rec)],
            AD_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_days_rec)],
            AD_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_final)]
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")]
    )

    # 3. Admin Inviter Flow
    inviter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_inviter_start, pattern="^add_inviter$")],
        states={
            INVITER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, inviter_code_rec)],
            INVITER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, inviter_name_rec)]
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")]
    )

    # -----------------------------------------------------------
    # HANDLERS (Groups are assigned here instead)
    # -----------------------------------------------------------
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard))
    
    # Add handlers with specific groups to prevent blocking
    app.add_handler(user_conv, group=1)
    app.add_handler(ads_conv, group=2)
    app.add_handler(inviter_conv, group=3)
    
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^choose_payment$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(show_stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(admin_payment_action, pattern="^admin_"))

    print("Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
