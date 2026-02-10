# ============================================================
# Zan Movie Channel Bot – FULL FINAL VERSION
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

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8515688348:AAG9tp1ZJ03MVmxdNe26ZO1x9SFrDA3-FYY"

ADMIN_ID = 6445257462
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
VIP_CHANNEL_ID = -1003863175003

VIP_PRICE = 10000
DEFAULT_PHONE = "09960202983"
DEFAULT_NAME = "Sai Zaw Ye Lwin"

DB_NAME = "movie_bot.db"

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ZanMovieBot")

# ============================================================
# DATABASE INIT
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        is_vip INTEGER DEFAULT 0,
        vip_expiry TEXT
    )
    """)

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inviters (
        code TEXT PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT,
        file_id TEXT,
        caption TEXT,
        next_post TEXT,
        end_at TEXT,
        interval_hours INTEGER,
        active INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ============================================================
# STATES
# ============================================================

WAITING_SLIP, WAITING_NAME, WAITING_REF_CHOICE, WAITING_REF = range(1, 5)

async def ref_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data  # ref_yes / ref_no

    # ❌ Referral မရှိ
    if choice == "ref_no":
        await query.message.edit_text(
            "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ。\n"
            "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
        )
        return ConversationHandler.END

    # ✅ Referral ရှိ
    elif choice == "ref_yes":
        await query.message.edit_text(
            "🔑 ဖိတ်ခေါ် ကုဒ် (၅ လုံး) ပို့ပေးပါ"
        )
        return WAITING_REF

# ============================================================
# START
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
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({VIP_PRICE} MMK)", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=MAIN_CHANNEL_URL)]
    ]

    if update.effective_user.id == ADMIN_ID:
        kb.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin_dashboard")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ============================================================
# VIP WARNING
# ============================================================

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

# ============================================================
# PAYMENT METHODS
# ============================================================

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

# ============================================================
# PAYMENT INFO
# ============================================================

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.split("_")[1]
    context.user_data["method"] = method

    text = (
        f"💳 {method} Pay\n\n"
        f"💰 Amount: {VIP_PRICE} MMK\n"
        f"📱 Phone: {DEFAULT_PHONE}\n"
        f"👤 Name: {DEFAULT_NAME}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )

    await q.message.edit_text(text)
    return WAITING_SLIP

# ============================================================
# RECEIVE SLIP
# ============================================================

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Screenshot ပုံသာ ပို့ပါ")
        return WAITING_SLIP

    context.user_data["slip"] = update.message.photo[-1].file_id
    await update.message.reply_text("👤 ငွေလွဲအကောင့်အမည် ပို့ပေးပါ")
    return WAITING_NAME

# ============================================================
# RECEIVE NAME + REF BUTTON
# ============================================================

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text.strip()

    kb = [
        [InlineKeyboardButton("ရှိပါတယ်", callback_data="ref_yes")],
        [InlineKeyboardButton("မရှိပါ", callback_data="ref_no")]
    ]

    await update.message.reply_text(
        "📨 ဖိတ်ခေါ် ကုဒ် ရှိပါသလား?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    return ASK_REF

# ============================================================
# ASK REF
# ============================================================

async def ask_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "ref_no":
        await notify_admin(context, q.from_user.id, None)
        await q.message.edit_text(
            "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
            "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
        )
        return ConversationHandler.END

    await q.message.edit_text("🔑 ဖိတ်ခေါ် ကုဒ် (5 လုံး) ပို့ပေးပါ")
    return WAITING_REF

# ============================================================
# RECEIVE REF
# ============================================================

async def receive_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT code FROM inviters WHERE code=?", (code,))
    ok = cur.fetchone()
    conn.close()

    if not ok:
        kb = [[
            InlineKeyboardButton("↩ ပြန်မေး", callback_data="ask_ref_again")
        ]]
        await update.message.reply_text(
            "❌ ကုဒ်မှားနေပါတယ်\nပြန်စမ်းကြည့်ပါ 👇",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return WAITING_REF_CHOICE



    await notify_admin(context, update.effective_user.id, code)

    await update.message.reply_text(
        "✅ ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin စစ်ဆေးပြီးပါက Bot မှတဆင့် အကြောင်းကြားပါမည်။"
    )
    return ConversationHandler.END

# ============================================================
# NOTIFY ADMIN
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

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=slip,
        caption=f"🧾 VIP Request\nUser: {user_id}\nName: {name}\nMethod: {method}\nRef: {ref_code}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ============================================================
# ADMIN APPROVE / REJECT
# ============================================================

async def admin_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, action, uid = q.data.split("_")
    uid = int(uid)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

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

        # 2️⃣ 🔐 single-user invite link (member_limit = 1)
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
                "🎉 VIP အတည်ပြုပြီးပါပြီ\n\n"
                "အောက်ကခလုတ်ကိုနှိပ်ပြီး VIP Channel သို့ဝင်ပါ 👇"
            ),
            reply_markup=kb
        )

    else:
        # ❌ Reject
        cur.execute(
            "UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'",
            (uid,)
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=uid,
            text="❌ ငွေပေးချေမှု မအောင်မြင်ပါ"
        )

    conn.close()

    # 3️⃣ Update admin message
    try:
        await q.edit_message_caption(
            q.message.caption + f"\n\nDONE: {action.upper()}"
        )
    except:
        pass


# ============================================================
# ADMIN DASHBOARD
# ============================================================

async def tharngal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("📊 ဝင်ငွေ / စာရင်း", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာပို့", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="admin_pay_edit")],
        [InlineKeyboardButton("🧩 ဖိတ်ခေါ် ကုဒ်", callback_data="admin_ref")],
    ]

    await update.message.reply_text(
        "🛠 ADMIN DASHBOARD",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ============================================================
# 📊 STATS / REVENUE
# ============================================================

import calendar
from datetime import datetime

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    now = datetime.now()
    year = now.year
    month = now.month

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # approved payments grouped by day
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

    cal = calendar.monthcalendar(year, month)

    text = f"📅 **{calendar.month_name[month]} {year} ဝင်ငွေစာရင်း**\n\n"
    text += "Mo Tu We Th Fr Sa Su\n"

    for week in cal:
        for day in week:
            if day == 0:
                text += "   "
            else:
                amt = income_by_day.get(day, 0)
                if amt > 0:
                    text += f"{day:02d}* "
                else:
                    text += f"{day:02d}  "
        text += "\n"

    text += "\n📌 * = ဝင်ငွေရှိ\n\n"
    text += "💰 **နေ့စဉ်အသေးစိတ်**\n"

    for d in sorted(income_by_day):
        text += f"• {d:02d} ရက် → {income_by_day[d]} MMK\n"

    kb = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    
# ============================================================
# USER CONVERSATION HANDLER
# ============================================================

user_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(vip_warning, pattern="^vip_buy$")
    ],
    states={
        WAITING_SLIP: [
            MessageHandler(filters.PHOTO, receive_slip)
        ],
        WAITING_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
        ],
        WAITING_REF_CHOICE: [
            CallbackQueryHandler(ref_choice, pattern="^(ref_yes|ref_no)$")
        ],
        WAITING_REF: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ref)
        ],
    },
    fallbacks=[
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^back_home$")
    ]
)

# ============================================================
# 🧩 REFERRAL MENU
# ============================================================

async def admin_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "🧩 ဖိတ်ခေါ် ကုဒ် စနစ်\n\n"
        "➕ ဖိတ်ခေါ် (Agent) အသစ်ထည့်နိုင်\n"
        "📋 သိမ်းထားတဲ့ နာမည် + ကုဒ် ကြည့်နိုင်\n"
        "✏️ နာမည် / ကုဒ် ပြင်နိုင်\n"
        "🗑️ ဖျတ်နိုင်\n"
    )

    kb = [
        [InlineKeyboardButton("➕ ဖိတ်ခေါ်အသစ်", callback_data="ref_add")],
        [InlineKeyboardButton("📋 ဖိတ်ခေါ်စာရင်း", callback_data="ref_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ]

    await q.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ============================================================
# 📢 ADS MENU
# ============================================================

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

# ============================================================
# 💳 PAYMENT EDIT
# ============================================================

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
# 🔙 BACK TO DASHBOARD
# ============================================================

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("📊 ဝင်ငွေ / စာရင်း", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာပို့", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ရန်", callback_data="admin_pay_edit")],
        [InlineKeyboardButton("🧩 ဖိတ်ခေါ် ကုဒ်", callback_data="admin_ref")],
    ]

    await q.message.edit_text(
        "🛠 ADMIN DASHBOARD",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ============================================================
# HANDLER REGISTER (ADMIN ONLY)
# ============================================================

def register_admin_handlers(app):
    app.add_handler(CommandHandler("tharngal", tharngal))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_ads, pattern="^admin_ads$"))
    app.add_handler(CallbackQueryHandler(admin_pay_edit, pattern="^admin_pay_edit$"))
    app.add_handler(CallbackQueryHandler(admin_ref, pattern="^admin_ref$"))
    app.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))


# ============================================================
# MAIN
# ============================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(user_conv)

    # ======================
    # USER SIDE (မဖြစ်မနေလို)
    # ======================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(user_conv)   # <-- ဒီလိုင်း အရမ်းအရေးကြီး

    # ======================
    # ADMIN SIDE
    # ======================
    register_admin_handlers(app)

    print("Bot Started...")
    app.run_polling()


if __name__ == "__main__":
    main()
