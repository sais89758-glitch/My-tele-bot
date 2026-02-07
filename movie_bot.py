# ============================================================
# Zan Movie Channel Bot – COMPLETE VERSION WITH REFERRAL SYSTEM
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

# မိမိ Bot Token
BOT_TOKEN = "8515688348:AAHkgGjz06M0BXBIqSuQzl2m_OFuUbakHAI"

# Admin Telegram ID
ADMIN_ID = 6445257462

MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
# ကြော်ညာ Post တင်ရန်အတွက် Channel Username (Bot သည် Admin ဖြစ်ရမည်)
CHANNEL_USERNAME = "@ZanchannelMM" 

# VIP Channel ID (Bot သည် Channel တွင် Add Members လုပ်ပိုင်ခွင့်ရှိသော Admin ဖြစ်ရမည်)
VIP_CHANNEL_ID = -1003863175003

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

    # Payments History Table (Updated with ref_code)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method TEXT,
        account_name TEXT,
        amount INTEGER,
        status TEXT,
        created_at TEXT,
        ref_code TEXT
    )
    """)
    
    # Existing Table Update Check: Add ref_code column if not exists
    try:
        cur.execute("ALTER TABLE payments ADD COLUMN ref_code TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists

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

    # Inviters (Referral) Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inviters (
        code TEXT PRIMARY KEY,
        name TEXT,
        total_count INTEGER DEFAULT 0,
        monthly_count INTEGER DEFAULT 0,
        last_month TEXT
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
WAITING_REF = 3  # New state for Referral Code

# Admin Side States (Ads)
AD_MEDIA = 10
AD_DAYS = 11
AD_INTERVAL = 12

# Admin Side States (Add Inviter)
INVITER_CODE = 30
INVITER_NAME = 31

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
    name = update.message.text
    context.user_data["pay_name"] = name
    
    # Referral Code မေးခြင်း
    keyboard = [[InlineKeyboardButton("မရှိပါ (Skip)", callback_data="skip_ref")]]
    await update.message.reply_text(
        "👤 Agent/Referral Code ရှိပါက ရိုက်ထည့်ပေးပါ။\n(မရှိပါက Skip ကိုနှိပ်ပါ)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_REF

async def skip_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await finalize_payment(update, context, ref_code=None)

async def receive_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref_code = update.message.text.strip()
    
    # Code စစ်ဆေးခြင်း
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name FROM inviters WHERE code=?", (ref_code,))
    result = cur.fetchone()
    conn.close()

    if result:
        await update.message.reply_text(f"✅ Agent code '{ref_code}' ({result[0]}) ကို အသုံးပြုထားသည်။")
        return await finalize_payment(update, context, ref_code=ref_code)
    else:
        keyboard = [[InlineKeyboardButton("မရှိပါ (Skip)", callback_data="skip_ref")]]
        await update.message.reply_text(
            "❌ Code မှားယွင်းနေပါသည်။ ပြန်ရိုက်ပါ သို့မဟုတ် Skip လုပ်ပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_REF

async def finalize_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code):
    user = update.effective_user
    method = context.user_data.get("method", "Unknown")
    slip = context.user_data.get("slip")
    name = context.user_data.get("pay_name")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, amount, status, created_at, ref_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user.id, method, name, DEFAULT_PRICE, "PENDING", datetime.now().isoformat(), ref_code)
    )
    conn.commit()
    conn.close()

    # Message ပို့ခြင်း (Callback သို့မဟုတ် Message ကနေလာနိုင်လို့ check ရသည်)
    if update.callback_query:
        await update.callback_query.message.edit_text("✅ Admin ထံသို့ ပို့ပြီးပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။")
    else:
        await update.message.reply_text("✅ Admin ထံသို့ ပို့ပြီးပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။")

    # Admin ထံ ပို့မည့်ခလုတ်များ
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ လက်ခံမည်", callback_data=f"admin_ok_{user.id}")],
        [InlineKeyboardButton("❌ ငြင်းပယ်မည်", callback_data=f"admin_fail_{user.id}")]
    ])

    ref_text = f"\n🔖 Ref Code: `{ref_code}`" if ref_code else ""

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
                f"Amount: {DEFAULT_PRICE}{ref_text}"
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
        [InlineKeyboardButton("📊 ဝင်ငွေစာရင်း (Stats)", callback_data="stats")],
        [InlineKeyboardButton("➕ Agent အသစ်ထည့်ရန်", callback_data="add_inviter")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="pay_menu")],
        [InlineKeyboardButton("Back to Home", callback_data="back_home")],
    ]

    text = "🛠 **Admin Dashboard**\nလုပ်ဆောင်လိုရာ ရွေးချယ်ပါ။"
    if query:
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def tharngal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await admin_dashboard(update, context)

# --- ADD INVITER FLOW ---
async def add_inviter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("🔤 Agent အတွက် Code သတ်မှတ်ပေးပါ (ဥပမာ: AGENT01)")
    return INVITER_CODE

async def save_inviter_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_inv_code"] = update.message.text.strip()
    await update.message.reply_text("👤 Agent နာမည် ရိုက်ထည့်ပါ")
    return INVITER_NAME

async def save_inviter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data["new_inv_code"]
    name = update.message.text.strip()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO inviters (code, name, total_count, monthly_count, last_month) VALUES (?, ?, 0, 0, ?)", 
                    (code, name, datetime.now().strftime("%Y-%m")))
        conn.commit()
        await update.message.reply_text(f"✅ Agent {name} ({code}) ကို ထည့်သွင်းပြီးပါပြီ။", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_dashboard")]]))
    except sqlite3.IntegrityError:
        await update.message.reply_text(f"❌ Code '{code}' က ရှိပြီးသား ဖြစ်နေသည်။",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_dashboard")]]))
    conn.close()
    return ConversationHandler.END

# --- PAYMENT APPROVAL WITH REFERRAL LOGIC ---
async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")[1:]
    user_id = int(user_id)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if action == "ok":
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, expiry))
        
        # 1. Update Payment Status
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        
        # 2. Handle Referral Logic (Update Count)
        cur.execute("SELECT ref_code FROM payments WHERE user_id=? AND status='APPROVED' ORDER BY id DESC LIMIT 1", (user_id,))
        res = cur.fetchone()
        
        if res and res[0]:
            ref_code = res[0]
            current_month = datetime.now().strftime("%Y-%m")
            
            # Get current stats for inviter
            cur.execute("SELECT monthly_count, last_month FROM inviters WHERE code=?", (ref_code,))
            inv_data = cur.fetchone()
            
            if inv_data:
                m_count, last_m = inv_data
                
                # Check for month reset
                if last_m != current_month:
                    m_count = 0 # Reset count for new month
                
                # Increment counts
                cur.execute("""
                    UPDATE inviters 
                    SET total_count = total_count + 1, 
                        monthly_count = ?, 
                        last_month = ? 
                    WHERE code=?
                """, (m_count + 1, current_month, ref_code))
                log.info(f"Referral counted for {ref_code}")

        conn.commit()

        try:
            # One-Time Invite Link ထုတ်ခြင်း (member_limit=1)
            invite = await context.bot.create_chat_invite_link(
                chat_id=VIP_CHANNEL_ID,
                member_limit=1,
                name=f"User {user_id}"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ ငွေပေးချေမှု အောင်မြင်ပါသည်။ VIP Member ဖြစ်ပါပြီ။\n\n⚠️ အောက်ပါ Link သည် တစ်ကြိမ်သာ အသုံးပြုနိုင်ပြီး (One Time Use) တစ်ယောက်ဝင်ပြီးပါက ပျက်သွားပါမည်။",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("VIP Channel ဝင်ရန်", url=invite.invite_link)]])
            )
            await query.edit_message_caption(query.message.caption + "\n\n✅ APPROVED")
        except Exception as e:
            log.error(f"Invite Link Error: {e}")
            await query.edit_message_caption(query.message.caption + f"\n\n✅ APPROVED BUT LINK ERROR: {e}")
            await context.bot.send_message(chat_id=user_id, text="✅ Payment Approved. (Invite Link Error - Please contact Admin)")

    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        conn.commit()

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ ငွေပေးချေမှု မအောင်မြင်ပါ။ (ငွေမဝင်ခြင်း သို့မဟုတ် အချက်အလက်မှားယွင်းခြင်း)"
            )
            await query.edit_message_caption(query.message.caption + "\n\n❌ REJECTED")
        except:
            pass
    conn.close()

# --- NEW STATS DASHBOARD ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    now = datetime.now()
    today_date = now.date().isoformat()
    this_month = now.strftime("%Y-%m")

    # 1. ဝင်ငွေ အကျဉ်းချုပ် တွက်ချက်ခြင်း
    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (today_date,))
    today_income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{this_month}%",))
    month_income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED'")
    total_income = cur.fetchone()[0] or 0

    # 2. VIP အခြေအနေ တွက်ချက်ခြင်း
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    total_vips = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    rejected_count = cur.fetchone()[0] or 0

    # 3. နေ့ရက်အလိုက် ဝင်ငွေ (နောက်ဆုံး ၇ ရက်စာ)
    daily_stats = ""
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        cur.execute("SELECT SUM(amount) FROM payments WHERE status='APPROVED' AND date(created_at)=?", (d.isoformat(),))
        d_income = cur.fetchone()[0] or 0
        daily_stats += f"📅 {d.strftime('%m-%d')} : {d_income} MMK\n"

    conn.close()

    # သင်အလိုရှိသော ပုံစံအတိုင်း စာသားပြင်ဆင်ခြင်း
    text = (
        "📊 **Admin Dashboard (အုပ်ချုပ်သူ မျက်နှာပြင်)**\n\n"
        "💰 **ဝင်ငွေ အကျဉ်းချုပ်**\n\n"
        f"💵 ယနေ့ ဝင်ငွေ : {today_income} MMK\n"
        f"📅 ယခုလ ဝင်ငွေ : {month_income} MMK\n"
        f"💎 စုစုပေါင်း ဝင်ငွေ : {total_income} MMK\n\n"
        "👥 **ယနေ့ VIP အခြေအနေ**\n"
        f"✅ VIP စုစုပေါင်း : {total_vips} ယောက်\n"
        f"❌ Rejected (ပယ်ချထား) : {rejected_count} ယောက်\n\n"
        "📅 **နေ့ရက်အလိုက် ဝင်ငွေ စာရင်း (လစဉ်)**\n\n"
        f"{daily_stats}\n"
        "🛠 **လုပ်ဆောင်ချက်များ (ACTIONS)**"
    )

    # ခလုတ်များ (Actions) ပြင်ဆင်ခြင်း
    kb = [
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="ads")],
        [InlineKeyboardButton("➕ Agent အသစ်ထည့်ရန်", callback_data="add_inviter")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="pay_menu")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
    ]

    await query.message.edit_text(
        text, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

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
    # JobQueue ကိုပါ ထည့်သွင်းတည်ဆောက်ခြင်း
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Ads Job Scheduler
    if app.job_queue:
        app.job_queue.run_repeating(post_ads_job, interval=60, first=10)

    # Handlers
    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)], 
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_referral),
                CallbackQueryHandler(skip_referral, pattern="^skip_ref$")
            ]
        },
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
    
    inviter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_inviter_start, pattern="^add_inviter$")],
        states={
            INVITER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_inviter_code)],
            INVITER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_inviter_name)]
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", tharngal_command))
    app.add_handler(user_conv)
    app.add_handler(ads_conv)
    app.add_handler(pay_edit_conv)
    app.add_handler(inviter_conv)
    
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^choose_payment$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(admin_payment_action, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(pay_menu, pattern="^pay_menu$"))

    print("Bot is running... (Press Ctrl+C to stop)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
