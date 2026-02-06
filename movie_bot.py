# Zan Movie Channel Bot – FINAL ADVANCED VERSION
# Features: VIP Flow, Ads System, Referral System (New), Payment Management

import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ================= CONFIGURATION =================
BOT_TOKEN = "8515688348:AAH45NOcsGPPD9UMyc43u8zDLLnlKS8eGs0" 
ADMIN_ID = 6445257462
VIP_PRICE = 30000

# Links & IDs
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
MAIN_CHANNEL_ID = "@ZanchannelMM" 
VIP_CHANNEL_URL = "https://t.me/+bDFiZZ9gwRRjY2M1"

# ================= LOGGING SETUP =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("movie_bot.db", check_same_thread=False)
    cur = conn.cursor()
    
    # 1. Users Table
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    
    # 2. Payments Table (Added referral_code)
    cur.execute("CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, account_name TEXT, status TEXT, created_at TEXT, referral_code TEXT)")
    
    # Check if referral_code column exists, if not add it (Migration)
    try:
        cur.execute("ALTER TABLE payments ADD COLUMN referral_code TEXT")
    except:
        pass

    # 3. Payment Settings Table
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr_id TEXT, phone TEXT, account_name TEXT)")
    
    # 4. Inviters Table (New)
    # code, name, total_users, current_month_users, last_updated_month
    cur.execute("CREATE TABLE IF NOT EXISTS inviters (code TEXT PRIMARY KEY, name TEXT, total_count INTEGER DEFAULT 0, month_count INTEGER DEFAULT 0, last_month TEXT)")

    # Default Payment Data
    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))
    
    conn.commit(); conn.close()

init_db()

def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

# ================= STATES =================
# User VIP Flow
WAITING_SLIP, WAITING_NAME, WAITING_REF_CHOICE, WAITING_REF_CODE = range(4)
# Admin Ads Flow
WAITING_AD_CONTENT, WAITING_AD_TIME = range(4, 6)
# Admin Payment Edit Flow
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(6, 9)
# Admin Inviter Flow
INVITER_CODE, INVITER_NAME = range(9, 11)

# ================= START & HOME =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 <b>Zan Movie Channel Bot</b>\n\n"
        "⛔️ Screenshot (SS) မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် - {VIP_PRICE} MMK", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= USER VIP PURCHASE FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    text = (
        "⚠️ <b>ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ</b>\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )
    kb = [
        [InlineKeyboardButton("✅ ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="back_home")]
    ]
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [[InlineKeyboardButton(f"💳 {m} Pay", callback_data=f"pay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
    await query.message.edit_text("<b>ငွေပေးချေမှုနည်းလမ်းရွေးပါ</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT qr_id, phone, account_name FROM payment_settings WHERE method=?", (method,))
    res = cur.fetchone()
    conn.close()
    
    qr_id, phone, name = res if res else (None, "N/A", "N/A")

    text = (
        f"<b>ငွေလွဲရန် ({VIP_PRICE} MMK)</b>\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {phone}\n"
        f"👤 အမည်: {name}\n\n"
        "‼️ <b>တစ်ကြိမ်ထဲ အပြည့်လွဲပါ</b>\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ <b>ပြေစာ Screenshot ပို့ပါ</b>"
    )
    
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="pay_methods")]]
    
    if qr_id:
        try:
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_id, caption=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            logger.error(f"Photo sending failed: {e}")
            await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ <b>ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။</b>", parse_mode="HTML")
        return WAITING_SLIP
    context.user_data["slip_file"] = update.message.photo[-1].file_id
    await update.message.reply_text("👤 <b>ငွေလွဲသူအကောင့်နာမည်ကို ရိုက်ပို့ပေးပါ။</b>", parse_mode="HTML")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text
    
    # NEW STEP: Ask for Referral Code
    kb = [
        [InlineKeyboardButton("✅ ရှိသည်", callback_data="ref_yes")],
        [InlineKeyboardButton("❌ မရှိပါ", callback_data="ref_no")]
    ]
    await update.message.reply_text("🤝 <b>ဖိတ်ခေါ်ကုဒ် (Referral Code) ရှိပါသလား?</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_REF_CHOICE

async def referral_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "ref_yes":
        await query.message.edit_text("🔢 <b>ကုဒ်နံပါတ် (ဥပမာ - 25413) ကို ရိုက်ပို့ပေးပါ။</b>", parse_mode="HTML")
        return WAITING_REF_CODE
    else:
        # No code, proceed to finish
        return await finalize_request(update, context, referral_code=None)

async def receive_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    return await finalize_request(update, context, referral_code=code)

async def finalize_request(update: Update, context: ContextTypes.DEFAULT_TYPE, referral_code):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    
    # Retrieve stored data
    method = context.user_data.get("method")
    account_name = context.user_data.get("account_name")
    slip_file = context.user_data.get("slip_file")
    
    final_ref_code = referral_code if referral_code else "-"
    
    # Save to DB
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, status, created_at, referral_code) VALUES (?,?,?,?,?,?)", 
                (user_id, method, account_name, "PENDING", datetime.now().isoformat(), final_ref_code))
    conn.commit(); conn.close()
    
    # Notify User
    msg_text = "✅ <b>Admin ထံသို့ ပို့လိုက်ပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။</b>"
    if update.callback_query:
        await update.callback_query.message.edit_text(msg_text, parse_mode="HTML")
    else:
        await update.message.reply_text(msg_text, parse_mode="HTML")
    
    # Notify Admin
    admin_text = (
        f"🔔 <b>New VIP Request</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📛 User: @{username}\n"
        f"💳 Method: {method}\n"
        f"📝 Name: {account_name}\n"
        f"🤝 Code: {final_ref_code}" 
    )
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=slip_file, caption=admin_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ================= ADMIN DASHBOARD =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = [
        [InlineKeyboardButton("📊 စာရင်းနှင့် ဝင်ငွေ", callback_data="admin_stats")],
        [InlineKeyboardButton("🤝 ဖိတ်ခေါ်သူစာရင်း", callback_data="admin_inviters")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ဆင်ရန်", callback_data="admin_pay_menu")],
    ]
    text = "🛠 <b>Admin Dashboard</b>\n\nလုပ်ဆောင်လိုသည့် Menu ကို ရွေးချယ်ပါ။"
    if update.callback_query: 
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: 
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN INVITER FLOW =================

async def referral_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "ref_yes":
        await query.message.edit_text("🔢 <b>ကုဒ်နံပါတ် (ဥပမာ - 25413) ကို ရိုက်ပို့ပေးပါ။</b>", parse_mode="HTML")
        return WAITING_REF_CODE
    else:
        # ကုဒ်မရှိပါက '-' ဖြင့် ဆက်သွားမည်
        return await finalize_request(update, context, referral_code=None)

async def receive_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    
    # Database ထဲတွင် Admin ထည့်ထားသော ကုဒ် ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT code FROM inviters WHERE code=?", (code,))
    result = cur.fetchone()
    conn.close()
    
    if not result:
        # Admin မထည့်ထားသော ကုဒ်ဖြစ်ပါက Error ပြပြီး ပြန်တောင်းမည်
        await update.message.reply_text("❌ <b>Code မှားယွင်းနေပါသည်။</b>\n(ပြန်လည် ရိုက်ထည့်ပေးပါ)", parse_mode="HTML")
        return WAITING_REF_CODE  # အဆင့်မကျော်ဘဲ ကုဒ်ပြန်တောင်းသည့် အဆင့်တွင် ရပ်နေမည်
    
    # ကုဒ်မှန်ကန်ပါက ရှေ့ဆက်မည်
    return await finalize_request(update, context, referral_code=code)

async def finalize_request(update: Update, context: ContextTypes.DEFAULT_TYPE, referral_code):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    
    # Retrieve stored data
    method = context.user_data.get("method")
    account_name = context.user_data.get("account_name")
    slip_file = context.user_data.get("slip_file")
    
    final_ref_code = referral_code if referral_code else "-"
    
    # Save to DB
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, status, created_at, referral_code) VALUES (?,?,?,?,?,?)", 
                (user_id, method, account_name, "PENDING", datetime.now().isoformat(), final_ref_code))
    conn.commit(); conn.close()
    
    # Notify User
    msg_text = "✅ <b>Admin ထံသို့ ပို့လိုက်ပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။</b>"
    if update.callback_query:
        await update.callback_query.message.edit_text(msg_text, parse_mode="HTML")
    else:
        await update.message.reply_text(msg_text, parse_mode="HTML")
    
    # Notify Admin
    admin_text = (
        f"🔔 <b>New VIP Request</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📛 User: @{username}\n"
        f"💳 Method: {method}\n"
        f"📝 Name: {account_name}\n"
        f"🤝 Code: {final_ref_code}" 
    )
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=slip_file, caption=admin_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ================= ADMIN ADS FLOW =================
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


# ================= ADMIN PAYMENT SETTINGS FLOW =================
async def admin_pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    kb = [[InlineKeyboardButton(f"{m} Pay", callback_data=f"editpay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")])
    await update.callback_query.message.edit_text("ပြင်ဆင်လိုသော Payment ရွေးပါ:", reply_markup=InlineKeyboardMarkup(kb))

async def edit_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    method = update.callback_query.data.split("_")[1]
    context.user_data['edit_method'] = method
    await update.callback_query.message.edit_text(f"💳 [{method} Pay] အတွက် QR ပုံ အသစ်ပို့ပေးပါ။")
    return PAY_SET_QR

async def receive_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ QR ပုံ (Image) သာ ပို့ပေးပါ။")
        return PAY_SET_QR
    context.user_data['edit_qr'] = update.message.photo[-1].file_id
    await update.message.reply_text("📱 ဖုန်းနံပါတ် အသစ်ပို့ပေးပါ။")
    return PAY_SET_PHONE

async def receive_pay_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['edit_phone'] = update.message.text
    await update.message.reply_text("👤 အကောင့်နာမည် အသစ်ပို့ပေးပါ။")
    return PAY_SET_NAME

async def receive_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    method = context.user_data['edit_method']
    qr_id = context.user_data['edit_qr']
    phone = context.user_data['edit_phone']
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE payment_settings SET qr_id=?, phone=?, account_name=? WHERE method=?", (qr_id, phone, name, method))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ <b>{method} Pay အတွက် အချက်အလက်များ ပြင်ဆင်ပြီးပါပြီ။</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("OK", callback_data="back_admin_home")]]))
    return ConversationHandler.END

# ================= STATS & ACTIONS =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    conn = get_db(); cur = conn.cursor()
    
    # Dates
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")
    
    # Helper to calculate income
    def get_income(query_part, params=()):
        cur.execute(f"SELECT COUNT(*) FROM payments WHERE status='APPROVED' {query_part}", params)
        return cur.fetchone()[0] * VIP_PRICE

    # 1. Income Stats
    today_income = get_income("AND date(created_at) = ?", (today_str,))
    month_income = get_income("AND strftime('%Y-%m', created_at) = ?", (month_str,))
    total_income = get_income("")
    
    # 2. VIP & Reject Stats
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vip_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    reject_count = cur.fetchone()[0]
    
    # 3. Last 7 Days Daily Stats
    days_stats_text = ""
    # Loop last 6 days + today = 7 days
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        display_date = d.strftime("%m-%d")
        
        daily_inc = get_income("AND date(created_at) = ?", (d_str,))
        days_stats_text += f"{display_date} : {daily_inc} MMK\n"

    conn.close()
    
    text = (
        "📊 <b>Admin Dashboard (အုပ်ချုပ်သူ မျက်နှာပြင်)</b>\n\n"
        "💰 <b>ဝင်ငွေ အကျဉ်းချုပ်</b>\n\n"
        f"ယနေ့ ဝင်ငွေ : {today_income} MMK\n"
        f"ယခုလ ဝင်ငွေ : {month_income} MMK\n"
        f"စုစုပေါင်း ဝင်ငွေ : {total_income} MMK\n\n"
        "👥 <b>ယနေ့VIP အခြေအနေ</b>\n"
        f"VIP စုစုပေါင်း : {vip_count} ယောက်\n"
        f"Rejected (ငွေလွဲမအောင်မြင် / ပယ်ချထား) : {reject_count} ယောက်\n\n"
        "📅 <b>နေ့ရက်အလိုက် ဝင်ငွေ စာရင်း (လစဉ်)</b>\n\n"
        f"{days_stats_text}"
    )
    
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    action, user_id = update.callback_query.data.split("_")
    user_id = int(user_id)
    conn = get_db(); cur = conn.cursor()
    
    if action == "approve":
        # 1. Update User VIP Status
        exp = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, exp))
        
        # 2. Get Referral Code from Payment
        cur.execute("SELECT referral_code FROM payments WHERE user_id=? AND status='PENDING' ORDER BY id DESC LIMIT 1", (user_id,))
        res = cur.fetchone()
        
        if res and res[0] and res[0] != "-":
            ref_code = res[0]
            current_month_str = datetime.now().strftime("%Y-%m")
            
            # Check inviter and reset month if needed
            cur.execute("SELECT month_count, last_month FROM inviters WHERE code=?", (ref_code,))
            inv_res = cur.fetchone()
            
            if inv_res:
                m_count, last_m = inv_res
                # If new month, reset month_count
                if last_m != current_month_str:
                    cur.execute("UPDATE inviters SET total_count=total_count+1, month_count=1, last_month=? WHERE code=?", (current_month_str, ref_code))
                else:
                    cur.execute("UPDATE inviters SET total_count=total_count+1, month_count=month_count+1 WHERE code=?", (ref_code,))

        # 3. Update Payment Status
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        
        await context.bot.send_message(user_id, "✅ <b>သင့် VIP အကောင့်ကို အတည်ပြုလိုက်ပါပြီ။</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 VIP Channel Join ရန်", url=VIP_CHANNEL_URL)]]))
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n✅ Approved")
    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        await context.bot.send_message(user_id, "❌ <b>ငွေလွဲမှု မအောင်မြင်ပါ သို့မဟုတ် အချက်အလက်မှားယွင်းနေပါသည်။</b>", parse_mode="HTML")
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n❌ Rejected")
        
    conn.commit(); conn.close()

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User Flow (Updated with Referral)
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF_CHOICE: [CallbackQueryHandler(referral_choice, pattern="^ref_")],
            WAITING_REF_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_referral_code)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(payment_methods, pattern="^pay_methods$")]
    ))
    
    # Admin Ads Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")],
        states={
            WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_ad_content)],
            WAITING_AD_TIME: [CallbackQueryHandler(finalize_ad_broadcast, pattern="^adtime_")],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    ))

    # Admin Pay Edit Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_payment_start, pattern="^editpay_")],
        states={
            PAY_SET_QR: [MessageHandler(filters.PHOTO, receive_pay_qr)],
            PAY_SET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_phone)],
            PAY_SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu), CallbackQueryHandler(admin_pay_menu, pattern="^admin_pay_menu$")]
    ))

    # Admin Inviter Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_inviter_start, pattern="^add_inviter$")],
        states={
            INVITER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_inviter_code)],
            INVITER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_inviter_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu), CallbackQueryHandler(inviter_menu, pattern="^admin_inviters$")]
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard_menu, pattern="^back_admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pay_menu, pattern="^admin_pay_menu$"))
    app.add_handler(CallbackQueryHandler(inviter_menu, pattern="^admin_inviters$"))
    app.add_handler(CallbackQueryHandler(list_inviters, pattern="^list_inviters$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    print("Bot is started...")
    app.run_polling()

if __name__ == "__main__":
    main()
