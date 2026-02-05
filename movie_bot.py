# Zan Movie Channel Bot – FULL FINAL VERSION
# Architect: System Architect & Senior Python Developer
# Version: 3.0 (Custom Dashboard, Dynamic Payments, Video Ads)

import logging
import sqlite3
import hashlib
import asyncio
import re
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
        slip_hash TEXT,
        account_name TEXT,
        status TEXT,
        amount INTEGER DEFAULT 30000,
        created_at TEXT
    )
    """)

    # Payment Settings Table (Dynamic Payment Info)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_settings (
        method TEXT PRIMARY KEY,
        qr_id TEXT,
        phone TEXT,
        account_name TEXT
    )
    """)
    
    # Initialize default payment methods if not exist
    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))

    conn.commit()
    conn.close()

init_db()

# ================= STATES =================
# User Flow States
WAITING_SLIP, WAITING_NAME = range(2)
# Admin Ad Flow States
WAITING_AD_CONTENT, WAITING_AD_TIME = range(2, 4)
# Admin Payment Setting States
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(4, 7)

# ================= HELPERS =================
def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

def parse_time_input(text):
    """Parse inputs like '1h', '30m', '1d' into seconds"""
    text = text.lower().strip()
    if text == "မဖျက်ပါ": return 0
    
    multipliers = {'d': 86400, 'h': 3600, 'm': 60}
    match = re.match(r"(\d+)\s*([dhm])", text)
    if match:
        val, unit = match.groups()
        return int(val) * multipliers[unit]
    return None

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot (SS) မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )
    keyboard = [
        [InlineKeyboardButton("👑 VIP ဝင်ရန်", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]
    if update.callback_query:
        try: await target.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except: await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= VIP FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = ("⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n⛔️ ခွဲလွဲပါက VIP မအတည်ပြုပါ\n\n⛔️ Screenshot / Screen Record / Download / Forward မရ\n\nသိရှိနားလည်ပါက ဆက်လုပ်ပါ")
    kb = [[InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],[InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],[InlineKeyboardButton("Wave Pay", callback_data="pay_Wave")],[InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],[InlineKeyboardButton("CB Pay", callback_data="pay_CB")],[InlineKeyboardButton("Back", callback_data="back_home")]]
    await query.message.edit_text("ငွေပေးချေမှုနည်းလမ်းရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    # Fetch dynamic info from DB
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT qr_id, phone, account_name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()

    qr_id, phone, name = row if row else (None, "N/A", "N/A")
    
    text = (f"ငွေလွဲရန် ({VIP_PRICE} MMK)\n\n💳 {method} Pay\n📱 ဖုန်း: {phone}\n👤 အမည်: {name}\n\n‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\nခွဲလွဲ / မှားလွဲပါက\nငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n⚠️ ပြေစာ Screenshot ပို့ပါ")
    
    if qr_id:
        await query.message.reply_photo(photo=qr_id, caption=text)
        await query.message.delete() # Clean up old text message
    else:
        await query.message.edit_text(text)
        
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။")
        return WAITING_SLIP
    context.user_data["slip_file"] = update.message.photo[-1].file_id
    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည်ကို ပို့ပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    user_id = update.effective_user.id
    method = context.user_data.get("method", "Unknown")
    file_id = context.user_data.get("slip_file")
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, status, created_at) VALUES (?,?,?,?,?)", (user_id, method, account_name, "PENDING", datetime.now().isoformat()))
    conn.commit(); conn.close()
    
    await update.message.reply_text("ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\nAdmin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။")
    
    kb = [[InlineKeyboardButton("✅ အတည်ပြုသည်", callback_data=f"approve_{user_id}")],[InlineKeyboardButton("❌ ငြင်းပယ်သည်", callback_data=f"reject_{user_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=f"📌 New VIP Request\nUser ID: {user_id}\nMethod: {method}\nName: {account_name}", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ================= ADMIN ACTIONS =================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, user_id = query.data.split("_")
    user_id = int(user_id)
    conn = get_db(); cur = conn.cursor()
    if action == "approve":
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, expiry))
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "✅ VIP အတည်ပြုပြီးပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 VIP Channel ဝင်ရန်", url=VIP_CHANNEL_URL)]]))
        await query.edit_message_caption(caption=query.message.caption + "\n\n✅ Approved")
    elif action == "reject":
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "❌ ငွေလွဲမှု မအောင်မြင်ပါ။")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ Rejected")
    conn.close()

# ================= ADMIN DASHBOARD MAIN MENU =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    text = "🛠 <b>Admin Control Panel</b>\n\nလိုအပ်သော ခလုတ်ကို ရွေးချယ်ပါ။"
    kb = [
        [InlineKeyboardButton("📋 စာရင်း", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာ", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment", callback_data="admin_pay_menu")],
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN STATS (📋 စာရင်း) =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_db(); cur = conn.cursor()
    now = datetime.now()
    today, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{today}%",))
    t_inc = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{month}%",))
    m_inc = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    all_inc = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vips = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    rejs = cur.fetchone()[0]
    
    cal_text = "📅 <b>နေ့စဉ်ဝင်ငွေ (၇ ရက်)</b>\n"
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        display_d = (now - timedelta(days=i)).strftime("%m-%d")
        cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{d}%",))
        amt = cur.fetchone()[0] * VIP_PRICE
        icon = "💰" if amt > 0 else "⚪️"
        cal_text += f"{icon} {display_d}: {amt} MMK\n"
    conn.close()
    
    text = (f"📊 <b>Admin Dashboard</b>\n\n💵 ယနေ့: {t_inc} MMK\n🗓 ယခုလ: {m_inc} MMK\n💰 စုစုပေါင်း: {all_inc} MMK\n\n👥 VIP: {vips} ယောက်\n❌ Reject: {rejs}\n\n{cal_text}")
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


# ================= ADMIN ADS FLOW (📢 ကြော်ညာ) =================
async def admin_ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📢 Main Channel သို့ ပို့လိုသော ကြော်ညာ (စာသား / ပုံ / ဗီဒီယို) ကို ပို့ပေးပါ။")
    return WAITING_AD_CONTENT

async def receive_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    # Store content
    context.user_data['ad_photo'] = msg.photo[-1].file_id if msg.photo else None
    context.user_data['ad_video'] = msg.video.file_id if msg.video else None
    context.user_data['ad_text'] = msg.caption if (msg.photo or msg.video) else msg.text
    
    kb = [
        [InlineKeyboardButton("၁ နာရီ", callback_data="adtime_3600"), InlineKeyboardButton("၆ နာရီ", callback_data="adtime_21600")],
        [InlineKeyboardButton("၁ ရက်", callback_data="adtime_86400"), InlineKeyboardButton("၃ ရက်", callback_data="adtime_259200")],
        [InlineKeyboardButton("မဖျက်ပါ", callback_data="adtime_0")]
    ]
    await msg.reply_text(
        "⏰ ကြော်ညာကို အလိုအလျောက် ပြန်ဖျက်မည့်အချိန် ရွေးပါ\n\n"
        "သို့မဟုတ် စိတ်ကြိုက်အချိန် ရိုက်ထည့်ပါ\n"
        "(Example: 2h, 30m, 1d 5h)",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return WAITING_AD_TIME

async def finalize_ad_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Determine input source (Button click or Text input)
    delete_seconds = 0
    
    if update.callback_query:
        await update.callback_query.answer()
        delete_seconds = int(update.callback_query.data.split("_")[1])
        msg_obj = update.callback_query.message
    else:
        # Text input custom time
        raw_text = update.message.text
        parsed = parse_time_input(raw_text)
        msg_obj = update.message
        if parsed is None:
            await update.message.reply_text("❌ အချိန်ပုံစံ မှားယွင်းနေသည်။ (Example: 1h, 30m, 1d)")
            return WAITING_AD_TIME
        delete_seconds = parsed

    # Get stored content
    photo = context.user_data.get('ad_photo')
    video = context.user_data.get('ad_video')
    text = context.user_data.get('ad_text')
    
    try:
        sent_msg = None
        if photo:
            sent_msg = await context.bot.send_photo(chat_id=MAIN_CHANNEL_ID, photo=photo, caption=text)
        elif video:
            sent_msg = await context.bot.send_video(chat_id=MAIN_CHANNEL_ID, video=video, caption=text)
        else:
            sent_msg = await context.bot.send_message(chat_id=MAIN_CHANNEL_ID, text=text)
            
        success_msg = "✅ ကြော်ညာကို Main Channel ထံ ပို့လိုက်ပါပြီ။"
        if delete_seconds > 0:
            human_time = str(timedelta(seconds=delete_seconds))
            success_msg += f"\n(⏳ {human_time} ကြာလျှင် အော်တိုဖျက်ပါမည်)"
            
            async def auto_delete(seconds, msg_id):
                await asyncio.sleep(seconds)
                try:
                    await context.bot.delete_message(chat_id=MAIN_CHANNEL_ID, message_id=msg_id)
                except: pass
            
            asyncio.create_task(auto_delete(delete_seconds, sent_msg.message_id))
        
        # Reply to admin
        if update.callback_query:
            await msg_obj.edit_text(success_msg)
        else:
            await msg_obj.reply_text(success_msg)
            
    except Exception as e:
        err_text = f"❌ Error: {e}"
        if update.callback_query: await msg_obj.edit_text(err_text)
        else: await msg_obj.reply_text(err_text)
    
    return ConversationHandler.END


# ================= ADMIN PAYMENT SETTINGS (💳 Payment) =================
async def admin_pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "💳 ပြင်ဆင်လိုသော Payment ကို ရွေးချယ်ပါ:"
    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="editpay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="editpay_Wave")],
        [InlineKeyboardButton("AYA Pay", callback_data="editpay_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="editpay_CB")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")],
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def edit_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1]
    context.user_data['edit_pay_method'] = method
    await query.message.edit_text(f"📝 {method} အတွက် **QR Code** ပုံကို ပို့ပေးပါ။")
    return PAY_SET_QR

async def receive_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ QR Code ပုံ ပို့ပေးပါ။")
        return PAY_SET_QR
    context.user_data['edit_pay_qr'] = update.message.photo[-1].file_id
    method = context.user_data['edit_pay_method']
    await update.message.reply_text(f"📱 {method} **ဖုန်းနံပါတ်** ကို ပို့ပေးပါ။")
    return PAY_SET_PHONE

async def receive_pay_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['edit_pay_phone'] = update.message.text
    method = context.user_data['edit_pay_method']
    await update.message.reply_text(f"👤 {method} **အကောင့်နာမည်** ကို ပို့ပေးပါ။")
    return PAY_SET_NAME

async def receive_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    method = context.user_data['edit_pay_method']
    qr_id = context.user_data['edit_pay_qr']
    phone = context.user_data['edit_pay_phone']
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE payment_settings SET qr_id=?, phone=?, account_name=? WHERE method=?", (qr_id, phone, name, method))
    conn.commit(); conn.close()
    
    await update.message.reply_text(f"✅ {method} အချက်အလက်များကို သိမ်းဆည်းလိုက်ပါပြီ။")
    return ConversationHandler.END


# ================= CALLBACK DISPATCHER =================
async def admin_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "back_admin_home":
        await admin_dashboard_menu(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_ads":
        # Handled by ConversationHandler entry point
        pass 
    elif data == "admin_pay_menu":
        await admin_pay_menu(update, context)

# ================= MAIN =================
async def vip_expiry_checker(app: Application):
    while True:
        try:
            conn = get_db(); cur = conn.cursor(); now = datetime.now().isoformat()
            cur.execute("SELECT user_id FROM users WHERE is_vip=1 AND vip_expiry < ?", (now,))
            for (uid,) in cur.fetchall():
                cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (uid,))
                conn.commit()
                await app.bot.send_message(uid, "⛔️ VIP သက်တမ်းကုန်သွားပါပြီ။")
            conn.close()
        except: pass
        await asyncio.sleep(3600)

async def post_init(app: Application):
    app.create_task(vip_expiry_checker(app))

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # 1. User VIP Flow
    user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_slip)],
        states={WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]},
        fallbacks=[CommandHandler("start", start)],
    )
    
    # 2. Admin Ads Flow
    ad_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")],
        states={
            WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_ad_content)],
            WAITING_AD_TIME: [
                CallbackQueryHandler(finalize_ad_broadcast, pattern="^adtime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_ad_broadcast)
            ],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)],
    )

    # 3. Admin Payment Settings Flow
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_payment_start, pattern="^editpay_")],
        states={
            PAY_SET_QR: [MessageHandler(filters.PHOTO, receive_pay_qr)],
            PAY_SET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_phone)],
            PAY_SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)],
    )

    application.add_handler(user_conv)
    application.add_handler(ad_conv)
    application.add_handler(pay_conv)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    
    application.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    application.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    application.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    application.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    
    # General Admin Navigation
    application.add_handler(CallbackQueryHandler(admin_dispatch, pattern="^(back_admin_home|admin_stats|admin_pay_menu)$"))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
