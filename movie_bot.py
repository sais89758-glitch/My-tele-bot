# ============================================================
# Zan Movie Channel Bot – FULL FIXED VERSION
# ============================================================

import logging
import sqlite3
import random
import string
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

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8515688348:AAHgjWNZuQVgTNQmyCwHJPngiW2it9Jckts"

ADMIN_ID = 6445257462
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
VIP_CHANNEL_ID = -1003863175003
CHANNEL_USERNAME = "@ZanchannelMM" # For Ads posting

VIP_PRICE = 10000
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

    # Payments Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method TEXT,
        account_name TEXT,
        ref_code TEXT,
        amount INTEGER,
        status TEXT,
        created_at TEXT
    )
    """)

    # Inviters (Ref Code) Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inviters (
        code TEXT PRIMARY KEY,
        agent_name TEXT,
        created_at TEXT
    )
    """)

    # Ads Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        next_post TEXT,
        end_at TEXT,
        interval_hours INTEGER,
        active INTEGER,
        total_days INTEGER
    )
    """)
    
    # Payment Settings Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_settings (
        method TEXT PRIMARY KEY,
        phone TEXT,
        name TEXT
    )
    """)

    conn.commit()
    conn.close()

# ============================================================
# STATES
# ============================================================

# User VIP States
VIP_CHOICE, PAYMENT_METHOD_SELECT, WAITING_SLIP, WAITING_NAME, WAITING_REF_CHOICE, WAITING_REF = range(1, 7)

# Admin Ads States
AD_MEDIA, AD_DAYS, AD_INTERVAL = range(7, 10)

# Admin Payment Edit States
PAY_CHOICE, PAY_PHONE, PAY_NAME_EDIT = range(10, 13)

# Admin Ref States
REF_NAME_INPUT = 13

# ============================================================
# SHARED FUNCTIONS
# ============================================================

def get_payment_details(method):
    """Fetch phone and name from DB, fallback to default"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT phone, name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()
    
    phone = row[0] if row and row[0] else DEFAULT_PHONE
    name = row[1] if row and row[1] else DEFAULT_NAME
    return phone, name

# ============================================================
# USER FLOW: START & VIP
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔ Screenshot (SS) မရ\n"
        "⛔ Screen Record မရ\n"
        "⛔ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )

    kb = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် (ပရိုမိုးရှင်း {VIP_PRICE} MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)]
    ]

    if update.effective_user.id == ADMIN_ID:
        kb.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin_dashboard")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        # If called from callback, answer first to stop loading animation
        try:
            await update.callback_query.answer()
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
        except:
            pass # Message might be too old
    
    return ConversationHandler.END

async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔ channel နှင့် bot ကိုထွက်မိ၊ဖျတ်မိပါက link ပြန်မပေးပါ\n"
        "⛔ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔ တစ်ကြိမ်ထဲ အပြည့်လွဲရပါမည်\n\n"
        "ဆက်လက်လုပ်ဆောင်မလား?"
    )

    kb = [
        [InlineKeyboardButton("ဆက်လုပ်မည်", callback_data="choose_payment")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]

    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return VIP_CHOICE

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ"),
         InlineKeyboardButton("Wave Pay", callback_data="pay_WAVE")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA"),
         InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")]
    ]

    await q.message.edit_text("ငွေပေးချေမှုနည်းလမ်း ရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))
    return PAYMENT_METHOD_SELECT

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.split("_")[1]
    context.user_data["method"] = method
    
    # Fetch dynamic info from DB
    phone, name = get_payment_details(method)

    text = (
        f"💳 {method} Pay\n\n"
        f"💰 Amount: {VIP_PRICE} MMK (ပရိုမိုးရှင်း)\n"
        f"📱 Phone: `{phone}`\n"
        f"👤 Name: {name}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ငွေလွှဲပြေစာ (Screenshot) ပို့ပေးပါ"
    )

    await q.message.edit_text(text, parse_mode="Markdown")
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle Photo or Document(image)
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith('image'):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ Screenshot ပုံသာ ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = file_id
    await update.message.reply_text("👤 သင့်ငွေလွှဲအကောင့်အမည် (Kpay Name) ရေးပို့ပေးပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text.strip()

    kb = [
        [InlineKeyboardButton("ရှိပါတယ်", callback_data="ref_yes")],
        [InlineKeyboardButton("မရှိပါ", callback_data="ref_no")]
    ]

    await update.message.reply_text(
        "📨 ဖိတ်ခေါ် ကုဒ် (Referral Code) ရှိပါသလား?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    return WAITING_REF_CHOICE

async def ref_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data  # ref_yes / ref_no

    if choice == "ref_no":
        # ⚠️ CRITICAL FIX: Notify admin even if no ref code
        await notify_admin(context, update.effective_user.id, "None")
        
        await query.message.edit_text(
            "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
            "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် Link ပို့ပေးပါမည်။"
        )
        return ConversationHandler.END

    elif choice == "ref_yes":
        await query.message.edit_text(
            "🔑 ဖိတ်ခေါ် ကုဒ် (၅ လုံး) ပို့ပေးပါ"
        )
        return WAITING_REF

async def receive_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT code FROM inviters WHERE code=?", (code,))
    ok = cur.fetchone()
    conn.close()

    if not ok:
        kb = [[
            InlineKeyboardButton("ကုဒ်ပြန်ရိုက်မည်", callback_data="ref_yes"),
            InlineKeyboardButton("မရှိပါ / ကျော်မည်", callback_data="ref_no")
        ]]
        await update.message.reply_text(
            "❌ ကုဒ်မှားနေပါတယ်\nပြန်စမ်းကြည့်ပါ သို့မဟုတ် ကျော်သွားပါ 👇",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return WAITING_REF_CHOICE

    # Valid Code
    await notify_admin(context, update.effective_user.id, code)

    await update.message.reply_text(
        "✅ ကုဒ်မှန်ကန်ပါသည်။\n"
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
    )
    return ConversationHandler.END

# ============================================================
# NOTIFY ADMIN & ACTIONS
# ============================================================

async def notify_admin(context, user_id, ref_code):
    slip = context.user_data.get("slip")
    name = context.user_data.get("account_name")
    method = context.user_data.get("method")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, ref_code, amount, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, method, name, ref_code, VIP_PRICE, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    kb = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"admin_ok_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admin_fail_{user_id}")
    ]]

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=slip,
            caption=f"🧾 **VIP Request**\n\n👤 User ID: `{user_id}`\n💳 Method: {method}\n👤 Acc Name: {name}\n🔑 Ref: {ref_code}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    except Exception as e:
        log.error(f"Failed to send admin notification: {e}")

async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data_parts = q.data.split("_")
    if len(data_parts) < 3:
        return

    _, action, uid = data_parts
    uid = int(uid)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Check if already processed
    cur.execute("SELECT status FROM payments WHERE user_id=? AND status='PENDING'", (uid,))
    pending = cur.fetchone()

    if not pending:
        await q.message.reply_text("⚠️ This request is already processed.")
        conn.close()
        return

    if action == "ok":
        # 1️⃣ VIP expiry (30 days)
        expiry = datetime.now() + timedelta(days=30)

        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?,?,?)",
            (uid, 1, expiry.isoformat())
        )
        cur.execute(
            "UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'",
            (uid,)
        )
        conn.commit()

        # 2️⃣ Create Invite Link
        try:
            invite = await context.bot.create_chat_invite_link(
                chat_id=VIP_CHANNEL_ID,
                member_limit=1,
                expire_date=int(expiry.timestamp())
            )
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 VIP Channel သို့ဝင်ရန်", url=invite.invite_link)]
            ])

            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 **VIP အောင်မြင်ပါသည်**\n\n"
                    "အောက်ကခလုတ်ကိုနှိပ်ပြီး VIP Channel သို့ဝင်ပါ 👇"
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
            # Update Admin Message
            new_caption = q.message.caption + "\n\n✅ STATUS: APPROVED"
            await q.message.edit_caption(caption=new_caption)

        except Exception as e:
            log.error(f"Invite Link Error: {e}")
            await context.bot.send_message(chat_id=uid, text="VIP Approved but Error creating link. Please contact Admin directly.")
            await q.message.reply_text(f"Error creating link: {e}")

    else:
        # ❌ Reject
        cur.execute(
            "UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'",
            (uid,)
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=uid,
            text="❌ သင့်ငွေပေးချေမှု မအောင်မြင်ပါ (Rejected)။ အသေးစိတ်သိရှိလိုပါက Admin ကို ဆက်သွယ်ပါ။"
        )
        # Update Admin Message
        new_caption = q.message.caption + "\n\n❌ STATUS: REJECTED"
        await q.message.edit_caption(caption=new_caption)

    conn.close()

# ============================================================
# ADMIN DASHBOARD & SUB-MENUS
# ============================================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check Admin
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("📊 ဝင်ငွေ / စာရင်း", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာပို့", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="admin_pay_edit")],
        [InlineKeyboardButton("🧩 ဖိတ်ခေါ် ကုဒ် (Ref)", callback_data="admin_ref_menu")],
    ]
    
    text = "🛠 **ADMIN DASHBOARD**\nလုပ်ဆောင်ချက် တစ်ခုရွေးချယ်ပါ"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    
    return ConversationHandler.END

# --- REVENUE STATS ---
import calendar
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    now = datetime.now()
    year = now.year
    month = now.month

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            strftime('%d', created_at) AS day,
            SUM(amount)
        FROM payments
        WHERE status='APPROVED'
          AND strftime('%Y', created_at)=?
          AND strftime('%m', created_at)=?
        GROUP BY day
    """, (str(year), f"{month:02d}"))

    rows = cur.fetchall()
    conn.close()

    income_by_day = {int(d): amt for d, amt in rows}
    total_income = sum(income_by_day.values())

    text = f"📅 **{calendar.month_name[month]} {year} ဝင်ငွေစာရင်း**\n"
    text += f"💵 Total: {total_income} MMK\n\n"

    for d in sorted(income_by_day):
        text += f"• {d:02d} ရက် → {income_by_day[d]} MMK\n"

    if not rows:
        text += "No income yet this month."

    kb = [[InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]]
    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- ADS SYSTEM ---
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

    await msg.reply_text("📅 ဘယ်နှစ်ရက်တင်မလဲ? (နံပါတ်သာရိုက်ပါ, ဥပမာ - 7)")
    return AD_DAYS

async def ads_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["days"] = int(update.message.text)
    except:
        await update.message.reply_text("နံပါတ်သာ ရိုက်ထည့်ပါ")
        return AD_DAYS
        
    await update.message.reply_text("⏱️ ဘယ်နှနာရီခြားတစ်ခါ တင်မလဲ? (နံပါတ်သာရိုက်ပါ, ဥပမာ - 4)")
    return AD_INTERVAL

async def ads_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = int(update.message.text)
    except:
        await update.message.reply_text("နံပါတ်သာ ရိုက်ထည့်ပါ")
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

    await update.message.reply_text(f"✅ ကြော်ညာ schedule ပြီးပါပြီ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_dashboard")]]))
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
        except Exception as e:
            log.error(f"Ads Error: {e}")
            pass
            
        next_time = now + timedelta(hours=interval)
        if now >= datetime.fromisoformat(end_str): cur.execute("UPDATE ads SET active=0 WHERE id=?", (ad_id,))
        else: cur.execute("UPDATE ads SET next_post=? WHERE id=?", (next_time.isoformat(), ad_id))
    conn.commit()
    conn.close()

# --- PAYMENT EDIT SYSTEM ---
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
    return PAY_CHOICE

async def pay_phone_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["edit_method"] = query.data.split("_")[1]
    await query.message.edit_text(f"📱 {context.user_data['edit_method']} ဖုန်းနံပါတ် အသစ်ရိုက်ထည့်ပါ (မပြင်လိုလျှင် /skip)")
    return PAY_PHONE

async def pay_phone_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["new_phone"] = text if text != "/skip" else None
    await update.message.reply_text("👤 အကောင့်နာမည် အသစ်ရိုက်ထည့်ပါ (မပြင်လိုလျှင် /skip)")
    return PAY_NAME_EDIT

async def pay_name_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text if update.message.text != "/skip" else None
    method = context.user_data["edit_method"]
    new_phone = context.user_data.get("new_phone")
    
    conn = sqlite3.connect(DB_NAME) 
    cur = conn.cursor()
    
    # Ensure row exists
    cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, name) VALUES (?, ?, ?)", (method, DEFAULT_PHONE, DEFAULT_NAME))
    
    if new_phone: cur.execute("UPDATE payment_settings SET phone=? WHERE method=?", (new_phone, method))
    if new_name: cur.execute("UPDATE payment_settings SET name=? WHERE method=?", (new_name, method))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ {method} အချက်အလက်များကို ပြင်ဆင်ပြီးပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_dashboard")]]))
    return ConversationHandler.END

# --- REF (REFERRAL) SYSTEM ---
async def admin_ref_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [
        [InlineKeyboardButton("➕ ကုဒ်အသစ်ဖန်တီး", callback_data="ref_create")],
        [InlineKeyboardButton("📋 ကုဒ်အားလုံးကြည့်", callback_data="ref_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
    ]
    await q.message.edit_text("🧩 Referral (ဖိတ်ခေါ်) စနစ်", reply_markup=InlineKeyboardMarkup(kb))

async def ref_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text("👤 Agent (ကိုယ်စားလှယ်) နာမည် ရိုက်ထည့်ပေးပါ:")
    return REF_NAME_INPUT

async def ref_save_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_name = update.message.text
    # Generate random 5 digit code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO inviters (code, agent_name, created_at) VALUES (?, ?, ?)", 
                (code, agent_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Agent အသစ် ဖန်တီးပြီးပါပြီ\n\n👤 Name: {agent_name}\n🔑 Code: `{code}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="admin_ref_menu")]])
    )
    return ConversationHandler.END

async def ref_list_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT agent_name, code FROM inviters")
    rows = cur.fetchall()
    conn.close()
    
    text = "📋 **Active Agents**\n\n"
    for name, code in rows:
        text += f"👤 {name} - `{code}`\n"
        
    if not rows:
        text += "No agents found."
        
    kb = [[InlineKeyboardButton("Back", callback_data="admin_ref_menu")]]
    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ============================================================
# CONVERSATION HANDLERS CONFIG
# ============================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    init_db()

    # --- User Conversation ---
    user_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(vip_warning, pattern="^vip_buy$")
        ],
        states={
            VIP_CHOICE: [
                CallbackQueryHandler(payment_methods, pattern="^choose_payment$"),
                CallbackQueryHandler(start, pattern="^back_home$")
            ],
            PAYMENT_METHOD_SELECT: [
                CallbackQueryHandler(payment_info, pattern="^pay_"),
                CallbackQueryHandler(start, pattern="^back_home$")
            ],
            WAITING_SLIP: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_slip)
            ],
            WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ],
            WAITING_REF_CHOICE: [
                CallbackQueryHandler(ref_choice, pattern="^(ref_yes|ref_no)$")
            ],
            WAITING_REF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ref),
                CallbackQueryHandler(ref_choice, pattern="^(ref_yes|ref_no)$") # Handle back/skip inside state
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^back_home$"),
        ]
    )

    # --- Admin Ads Conversation ---
    ads_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ads_start, pattern="^admin_ads$")],
        states={
            AD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, ads_media)],
            AD_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_days)],
            AD_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ads_interval)],
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")]
    )
    
    # --- Admin Payment Edit Conversation ---
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_menu, pattern="^admin_pay_edit$")],
        states={
            PAY_CHOICE: [CallbackQueryHandler(pay_phone_ask, pattern="^edit_")],
            PAY_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_phone_save)],
            PAY_NAME_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_name_save)],
        },
        fallbacks=[CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$")]
    )

    # --- Admin Ref Conversation ---
    ref_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ref_create_start, pattern="^ref_create$")],
        states={
            REF_NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ref_save_agent)],
        },
        fallbacks=[CallbackQueryHandler(admin_ref_menu, pattern="^admin_ref_menu$")]
    )

    # --- Handlers Registration ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard)) # Secret admin command
    
    app.add_handler(user_conv)
    app.add_handler(ads_conv)
    app.add_handler(pay_conv)
    app.add_handler(ref_conv)
    
    # Admin Menu Navigation
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^admin_dashboard$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_payment_action, pattern="^admin_(ok|fail)_"))
    
    # Ref Menu Handlers
    app.add_handler(CallbackQueryHandler(admin_ref_menu, pattern="^admin_ref_menu$"))
    app.add_handler(CallbackQueryHandler(ref_list_view, pattern="^ref_list$"))

    # Ads Job
    if app.job_queue:
        app.job_queue.run_repeating(post_ads_job, interval=3600, first=10)

    print("✅ Bot Started Successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
