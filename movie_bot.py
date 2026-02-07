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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎬 Zan Movie Channel Bot\n\n📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    keyboard = [[InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({DEFAULT_PRICE} MMK)", callback_data="vip_buy")]]
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin_dashboard")])
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="choose_payment")], [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]]
    await query.message.edit_text("⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ...\n\nဆက်လက်လုပ်ဆောင်မလား?", reply_markup=InlineKeyboardMarkup(keyboard))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ"), InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA"), InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")]
    ]
    await query.message.edit_text("ငွေပေးချေမှုနည်းလမ်း ရွေးပါ", reply_markup=InlineKeyboardMarkup(keyboard))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1]
    context.user_data["buy_method"] = method
    
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("SELECT phone, name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone(); conn.close()
    
    ph = row[0] if row else DEFAULT_PHONE
    nm = row[1] if row else DEFAULT_NAME
    
    await query.message.edit_text(f"💳 {method} Pay\n📱 ဖုန်း: `{ph}`\n👤 အမည်: {nm}\n\n⚠️ ပြေစာ Screenshot ပို့ပါ", parse_mode="Markdown")
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["buy_slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ ပြေစာရရှိပါသည်။ ငွေလွဲသူအကောင့်နာမည် ပို့ပေးပါ။")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["buy_payname"] = update.message.text
    kb = [[InlineKeyboardButton("မရှိပါ (Skip)", callback_data="skip_ref")]]
    await update.message.reply_text("👤 Agent/Referral Code ရှိပါက ရိုက်ထည့်ပါ (မရှိရင် Skip နှိပ်ပါ)", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_REF

async def process_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = update.message.text.strip() if update.message else None
    
    if ref:
        conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
        cur.execute("SELECT name FROM inviters WHERE code=?", (ref,))
        if not cur.fetchone():
            conn.close()
            await update.message.reply_text("❌ Code မှားနေပါတယ်။ ပြန်ရိုက်ပါ (သို့) Skip နှိပ်ပါ။")
            return WAITING_REF
        conn.close()
    
    # Save & Notify Admin
    uid = update.effective_user.id
    method = context.user_data["buy_method"]
    slip = context.user_data["buy_slip"]
    p_name = context.user_data["buy_payname"]
    
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, amount, status, created_at, ref_code) VALUES (?,?,?,?,?,?,?)",
                (uid, method, p_name, DEFAULT_PRICE, "PENDING", datetime.now().isoformat(), ref))
    conn.commit(); conn.close()
    
    msg = f"🔔 **VIP Request**\nID: `{uid}`\nMethod: {method}\nName: {p_name}\nRef: `{ref}`"
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"admin_ok_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"admin_fail_{uid}")]]
    
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=slip, caption=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    text = "✅ Admin ထံ ပို့ပြီးပါပြီ။ ခေတ္တစောင့်ပေးပါ။"
    if update.callback_query: await update.callback_query.message.edit_text(text)
    else: await update.message.reply_text(text)
    return ConversationHandler.END

# ============================================================
# 2. ADMIN SIDE
# ============================================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("➕ Add Agent", callback_data="add_inviter")],
        [InlineKeyboardButton("📢 Post Ad", callback_data="ads"), InlineKeyboardButton("💳 Edit Pay", callback_data="pay_menu")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="back_home")]
    ]
    msg = "🛠 **Admin Dashboard**"
    if update.callback_query: await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else: await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

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
    now = datetime.now(); today = now.date().isoformat()
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (today,))
    t_inc = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vips = cur.fetchone()[0] or 0
    conn.close()
    
    txt = f"📊 **Stats Overview**\n\n💵 Today: {t_inc} MMK\n👥 Total VIP: {vips} users"
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
    
    # 1. User VIP Flow (Group 1)
    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ref), CallbackQueryHandler(process_ref, pattern="^skip_ref$")]
        },
        fallbacks=[CommandHandler("start", start)],
        group=1
    )

    # 2. Admin Ads Flow (Group 2)
    ads_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ads_start, pattern="^ads$")],
        states={
            AD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, ads_media_rec)],
            AD_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_days_rec)],
            AD_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_final)]
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")],
        group=2
    )

    # 3. Admin Inviter Flow (Group 3)
    inviter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_inviter_start, pattern="^add_inviter$")],
        states={
            INVITER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, inviter_code_rec)],
            INVITER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, inviter_name_rec)]
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")],
        group=3
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard))
    app.add_handler(user_conv)
    app.add_handler(ads_conv)
    app.add_handler(inviter_conv)
    
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
