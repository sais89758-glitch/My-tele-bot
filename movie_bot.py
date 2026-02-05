# Zan Movie Channel Bot – FINAL FIXED VERSION
# Features: 
# 1. Fixed "methods Pay" bug (Renamed callback to avoid conflict)
# 2. New Ad System (Days Duration + Hourly Interval Loop)
# 3. New Admin Dashboard (7 Days Income History + Exact Stats)
# 4. QR Image Fetching Fix

import logging
import sqlite3
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
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    # Payments Table
    cur.execute("CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, account_name TEXT, status TEXT, created_at TEXT)")
    # Payment Settings Table
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr_id TEXT, phone TEXT, account_name TEXT)")
    
    # Default Payment Data Check
    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

# ================= STATES =================
WAITING_SLIP, WAITING_NAME = range(2)  # User VIP Flow
WAITING_AD_CONTENT, WAITING_AD_DURATION, WAITING_AD_INTERVAL = range(2, 5)  # New Admin Ad Flow
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(5, 8)  # Admin Payment Edit Flow

# ================= START & HOME =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
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
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= USER VIP PURCHASE FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )
    kb = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="show_payment_options")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton(f"{m} Pay", callback_data=f"pay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("Back", callback_data="back_home")])
    await query.message.edit_text("ငွေပေးချေမှုနည်းလမ်းရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT qr_id, phone, account_name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()

    qr_id, phone, name = row if row else (None, "N/A", "N/A")

    caption_text = (
        f"ငွေလွဲရန် ({VIP_PRICE} MMK)\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {phone}\n"
        f"👤 အမည်: {name}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )
    
    try:
        await query.message.delete()
    except:
        pass

    # Admin သတ်မှတ်ထားသော QR ပုံရှိလျှင် ပုံနှင့်ပို့မည်၊ မရှိလျှင် စာသားသာပို့မည်
    if qr_id:
        try:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_id, caption=caption_text)
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text + "\n\n(QR ပုံပို့ရာတွင် အမှားအယွင်းရှိနေပါသည်)")
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text)
        
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
    username = update.effective_user.username or "No Username"
    method = context.user_data.get("method")
    file_id = context.user_data.get("slip_file")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, status, created_at) VALUES (?,?,?,?,?)", 
        (user_id, method, account_name, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    reply_text = (
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )
    await update.message.reply_text(reply_text)
    
    admin_text = (
        f"New VIP Request 🔔\n\n"
        f"👤 ID: `{user_id}`\n"
        f"📛 User: @{username}\n"
        f"💳 Method: {method}\n"
        f"📝 Name: {account_name}"
    )
    
    kb = [
        [InlineKeyboardButton("✅ လက်ခံရရှိပြီး (Approve)", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ ငွေမရောက်ပါ / အချက်အလက်မှားယွင်းသည်", callback_data=f"reject_{user_id}")]
    ]
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID, 
        photo=file_id, 
        caption=admin_text, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return ConversationHandler.END

# ================= ADMIN DASHBOARD =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    kb = [
        [InlineKeyboardButton("📋 စာရင်းကြည့်ရန်", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ဆင်ရန်", callback_data="admin_pay_menu")],
    ]
    text = "🛠 <b>Admin Dashboard</b>\nဘာလုပ်ချင်ပါသလဲ ရွေးချယ်ပါ။"
    
    if update.callback_query: 
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: 
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN ADS FLOW =================
async def admin_ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("📢 Channel သို့ ပို့မည့် ကြော်ညာ (စာ/ပုံ/ဗီဒီယို) ပို့ပေးပါ။")
    return WAITING_AD_CONTENT

async def receive_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    context.user_data['ad_photo'] = msg.photo[-1].file_id if msg.photo else None
    context.user_data['ad_video'] = msg.video.file_id if msg.video else None
    context.user_data['ad_text'] = msg.caption if (msg.photo or msg.video) else msg.text
    
    await msg.reply_text(
        "🗓 ဒီကြော်ညာကို ဘယ်နှရက်ထားမှာလဲ? (ရက်အရေအတွက်ပဲ ရိုက်ထည့်ပါ)\n\n"
        "ဥပမာ - ၁ ရက်ထားမယ်ဆိုရင် `1` လို့ရိုက်ထည့်ပါ။"
    )
    return WAITING_AD_DURATION

async def receive_ad_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပါ။ (ဥပမာ: 1)")
        return WAITING_AD_DURATION
    
    context.user_data['ad_days'] = int(text)
    await update.message.reply_text(
        "⏰ ဘယ်နှနာရီခြား တစ်ခါတင်မှာလဲ? (နာရီပဲ ရိုက်ထည့်ပါ)\n\n"
        "ဥပမာ - ၁ နာရီခြားတစ်ခါတင်မယ်ဆိုရင် `1` လို့ရိုက်ထည့်ပါ။"
    )
    return WAITING_AD_INTERVAL

async def receive_ad_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပါ။")
        return WAITING_AD_INTERVAL
    
    interval_hours = int(text)
    days = context.user_data['ad_days']
    photo = context.user_data.get('ad_photo')
    video = context.user_data.get('ad_video')
    ad_text = context.user_data.get('ad_text')
    
    total_duration_sec = days * 24 * 3600
    interval_sec = interval_hours * 3600
    
    await update.message.reply_text(f"✅ ကြော်ညာစတင်ပါပြီ။\n🗓 ကြာချိန်: {days} ရက်\n⏰ ကြားကာလ: {interval_hours} နာရီတစ်ခါ")
    asyncio.create_task(run_ad_campaign(context, photo, video, ad_text, total_duration_sec, interval_sec))
    return ConversationHandler.END

async def run_ad_campaign(context, photo, video, text, duration, interval):
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=duration)
    while datetime.now() < end_time:
        try:
            if photo: await context.bot.send_photo(MAIN_CHANNEL_ID, photo, caption=text)
            elif video: await context.bot.send_video(MAIN_CHANNEL_ID, video, caption=text)
            else: await context.bot.send_message(MAIN_CHANNEL_ID, text)
        except Exception as e: logger.error(f"Ad Error: {e}")
        await asyncio.sleep(interval)

# ================= ADMIN PAYMENT SETTINGS FLOW =================
async def admin_pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(f"{m} Pay", callback_data=f"editpay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")])
    await update.callback_query.message.edit_text("ပြင်ဆင်လိုသော Payment ရွေးပါ:", reply_markup=InlineKeyboardMarkup(kb))

async def edit_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = update.callback_query.data.split("_")[1]
    context.user_data['edit_method'] = method
    await update.callback_query.message.edit_text(f"[{method}] အတွက် QR ပုံ အသစ်ပို့ပေးပါ။")
    return PAY_SET_QR

async def receive_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("QR ပုံ ပို့ပေးပါ။")
        return PAY_SET_QR
    context.user_data['edit_qr'] = update.message.photo[-1].file_id
    await update.message.reply_text("ဖုန်းနံပါတ် အသစ်ပို့ပေးပါ။")
    return PAY_SET_PHONE

async def receive_pay_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['edit_phone'] = update.message.text
    await update.message.reply_text("အကောင့်နာမည် အသစ်ပို့ပေးပါ။")
    return PAY_SET_NAME

async def receive_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    method = context.user_data['edit_method']
    qr_id = context.user_data['edit_qr']
    phone = context.user_data['edit_phone']
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE payment_settings SET qr_id=?, phone=?, account_name=? WHERE method=?", (qr_id, phone, name, method))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ {method} အချက်အလက်များ သိမ်းပြီးပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="back_admin_home")]]))
    return ConversationHandler.END

# ================= ADMIN STATS =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db(); cur = conn.cursor()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    total_income = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND date(created_at) = ?", (today_str,))
    today_income = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND strftime('%Y-%m', created_at) = ?", (month_str,))
    month_income = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vip_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    reject_count = cur.fetchone()[0]
    
    days_stats = ""
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        q_date = d.strftime("%Y-%m-%d")
        cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND date(created_at) = ?", (q_date,))
        d_income = cur.fetchone()[0] * VIP_PRICE
        icon = "💰" if d_income > 0 else "⚪️"
        days_stats += f"{icon} {d.strftime('%m-%d')}: {d_income} MMK\n"
    conn.close()
    
    text = (
        "📊 <b>Admin Dashboard</b>\n\n"
        f"💵 ယနေ့: {today_income} MMK\n"
        f"🗓 ယခုလ: {month_income} MMK\n"
        f"💰 စုစုပေါင်း: {total_income} MMK\n\n"
        f"👥 VIP: {vip_count} ယောက်\n"
        f"❌ Reject: {reject_count}\n\n"
        f"📆 <b>နေ့စဉ်ဝင်ငွေ (၇ ရက်)</b>\n{days_stats}"
    )
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action, user_id = update.callback_query.data.split("_")
    user_id = int(user_id)
    conn = get_db(); cur = conn.cursor()
    if action == "approve":
        exp = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, exp))
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        await context.bot.send_message(user_id, "✅ သင့် VIP အကောင့်ကို အတည်ပြုလိုက်ပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 VIP Channel Join ရန်", url=VIP_CHANNEL_URL)]]))
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n✅ Approved")
    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        await context.bot.send_message(user_id, "❌ ငွေလွဲမှု အဆင်မပြေပါ သို့မဟုတ် အချက်အလက်မှားယွင်းနေပါသည်။")
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n❌ Rejected")
    conn.commit(); conn.close()

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)], WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^back_home$")]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")],
        states={WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_ad_content)], WAITING_AD_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ad_duration)], WAITING_AD_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ad_interval)]},
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_payment_start, pattern="^editpay_")],
        states={PAY_SET_QR: [MessageHandler(filters.PHOTO, receive_pay_qr)], PAY_SET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_phone)], PAY_SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_name)]},
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    ))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^show_payment_options$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard_menu, pattern="^back_admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pay_menu, pattern="^admin_pay_menu$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__": main()
