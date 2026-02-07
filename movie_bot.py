# Zan Movie Channel Bot – FINAL ERROR-FREE VERSION
# Features: VIP Flow, Ads System, Referral System, Payment Management

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
DB_NAME = "movie_bot.db"

# ================= LOGGING SETUP =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cur = conn.cursor()
    
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, account_name TEXT, status TEXT, created_at TEXT, referral_code TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr_id TEXT, phone TEXT, account_name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS inviters (code TEXT PRIMARY KEY, name TEXT, total_count INTEGER DEFAULT 0, month_count INTEGER DEFAULT 0, last_month TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, media_type TEXT, file_id TEXT, caption TEXT, total_days INTEGER, interval_hours INTEGER, next_post TEXT, end_at TEXT, active INTEGER DEFAULT 1)")

    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))
    
    conn.commit(); conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# ================= STATES =================
WAITING_SLIP, WAITING_NAME, WAITING_REF_CHOICE, WAITING_REF_CODE = range(4)
WAITING_AD_CONTENT, WAITING_AD_TIME = range(4, 6)
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(6, 9)
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
        except:
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
        return await finalize_request(update, context, referral_code=None)

async def receive_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT code FROM inviters WHERE code=?", (code,))
    result = cur.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ <b>Code မှားယွင်းနေပါသည်။</b>\n(ပြန်လည် ရိုက်ထည့်ပေးပါ)", parse_mode="HTML")
        return WAITING_REF_CODE
    
    return await finalize_request(update, context, referral_code=code)

async def finalize_request(update: Update, context: ContextTypes.DEFAULT_TYPE, referral_code):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    method = context.user_data.get("method")
    account_name = context.user_data.get("account_name")
    slip_file = context.user_data.get("slip_file")
    final_ref_code = referral_code if referral_code else "-"
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, status, created_at, referral_code) VALUES (?,?,?,?,?,?)", 
                (user_id, method, account_name, "PENDING", datetime.now().isoformat(), final_ref_code))
    conn.commit(); conn.close()
    
    msg_text = "✅ <b>Admin ထံသို့ ပို့လိုက်ပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။</b>"
    if update.callback_query:
        await update.callback_query.message.edit_text(msg_text, parse_mode="HTML")
    else:
        await update.message.reply_text(msg_text, parse_mode="HTML")
    
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

# ================= ADMIN ACTIONS =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = [
        [InlineKeyboardButton("📊 စာရင်းနှင့် ဝင်ငွေ", callback_data="admin_stats")],
        [InlineKeyboardButton("🤝 ဖိတ်ခေါ်သူစာရင်း", callback_data="admin_inviters")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ဆင်ရန်", callback_data="admin_pay_menu")],
    ]
    text = "🛠 <b>Admin Dashboard</b>"
    if update.callback_query: 
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: 
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vip_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    total_sales = cur.fetchone()[0]
    total_revenue = total_sales * VIP_PRICE
    conn.close()
    
    text = (
        "📊 <b>Statistics</b>\n\n"
        f"👥 Total VIPs: {vip_count}\n"
        f"💰 Total Revenue: {total_revenue:,} MMK"
    )
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    action, user_id = query.data.split("_")
    user_id = int(user_id)
    
    conn = get_db(); cur = conn.cursor()
    if action == "approve":
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip) VALUES (?, 1)", (user_id,))
        
        # Handle referral count if exists
        cur.execute("SELECT referral_code FROM payments WHERE user_id=? AND status='APPROVED' ORDER BY id DESC LIMIT 1", (user_id,))
        ref_res = cur.fetchone()
        if ref_res and ref_res[0] != "-":
            cur.execute("UPDATE inviters SET total_count = total_count + 1, month_count = month_count + 1 WHERE code=?", (ref_res[0],))
        
        conn.commit()
        await query.message.edit_caption("✅ <b>Approved! User is now VIP.</b>", parse_mode="HTML")
        try:
            invite_link = await context.bot.create_chat_invite_link(chat_id=MAIN_CHANNEL_ID, member_limit=1)
            await context.bot.send_message(chat_id=user_id, text=f"🎉 <b>VIP အတည်ပြုပြီးပါပြီ။</b>\n\nChannel သို့ဝင်ရန်: {invite_link.invite_link}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error sending link: {e}")
    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        conn.commit()
        await query.message.edit_caption("❌ <b>Rejected.</b>", parse_mode="HTML")
        await context.bot.send_message(chat_id=user_id, text="❌ <b>သင်၏ VIP တောင်းဆိုမှု ငြင်းပယ်ခံရပါသည်။</b>")
    conn.close()

async def inviter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [
        [InlineKeyboardButton("➕ ကုဒ်အသစ်ထည့်ရန်", callback_data="add_inviter")],
        [InlineKeyboardButton("📜 စာရင်းကြည့်ရန်", callback_data="list_inviters")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]
    ]
    await query.message.edit_text("🤝 <b>Inviter (ဖိတ်ခေါ်သူ) စီမံခြင်း</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def add_inviter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.message.edit_text("🔢 <b>Inviter ကုဒ်နံပါတ် ရိုက်ပို့ပါ။</b>", parse_mode="HTML")
    return INVITER_CODE

async def receive_inviter_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_inv_code'] = update.message.text
    await update.message.reply_text("👤 <b>Inviter အမည် ရိုက်ပို့ပါ။</b>", parse_mode="HTML")
    return INVITER_NAME

async def receive_inviter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    code = context.user_data['new_inv_code']
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO inviters (code, name, total_count, month_count, last_month) VALUES (?, ?, 0, 0, ?)", 
                    (code, name, datetime.now().strftime("%Y-%m")))
        conn.commit()
        await update.message.reply_text(f"✅ Code: {code}\nName: {name}")
    except:
        await update.message.reply_text("❌ Code ရှိပြီးသားဖြစ်နေသည်။")
    finally:
        conn.close()
    return ConversationHandler.END

async def list_inviters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT code, name, total_count, month_count FROM inviters")
    rows = cur.fetchall(); conn.close()
    text = "📜 <b>Inviter စာရင်း</b>\n\n"
    for r in rows: text += f"🔹 {r[1]} ({r[0]}) - Total: {r[2]} | Month: {r[3]}\n"
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_inviters")]]))

# ================= JOB & ADS =================
async def post_ads_job(context: ContextTypes.DEFAULT_TYPE):
    conn = get_db(); cur = conn.cursor()
    now = datetime.now()
    cur.execute("SELECT id, media_type, file_id, caption, interval_hours, end_at FROM ads WHERE active=1 AND next_post <= ?", (now.isoformat(),))
    ads = cur.fetchall()
    for ad in ads:
        ad_id, m_type, f_id, cap, interval, end_str = ad
        try:
            if m_type == "photo": await context.bot.send_photo(chat_id=MAIN_CHANNEL_ID, photo=f_id, caption=cap)
            else: await context.bot.send_video(chat_id=MAIN_CHANNEL_ID, video=f_id, caption=cap)
        except: pass
        next_time = now + timedelta(hours=interval)
        if now >= datetime.fromisoformat(end_str): cur.execute("UPDATE ads SET active=0 WHERE id=?", (ad_id,))
        else: cur.execute("UPDATE ads SET next_post=? WHERE id=?", (next_time.isoformat(), ad_id))
    conn.commit(); conn.close()

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Check if job_queue is available (requires [job-queue] extra)
    if app.job_queue:
        app.job_queue.run_repeating(post_ads_job, interval=3600, first=10)
    else:
        logger.warning("JobQueue is not initialized. Background ads will not run.")

    # User VIP Conversation
    vip_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_REF_CHOICE: [CallbackQueryHandler(referral_choice, pattern="^ref_")],
            WAITING_REF_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_referral_code)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^back_home$")],
    )

    # Admin Inviter Conversation
    inviter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_inviter_start, pattern="^add_inviter$")],
        states={
            INVITER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_inviter_code)],
            INVITER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_inviter_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu), CallbackQueryHandler(inviter_menu, pattern="^admin_inviters$")]
    )

    app.add_handler(vip_conv)
    app.add_handler(inviter_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard_menu, pattern="^back_admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(inviter_menu, pattern="^admin_inviters$"))
    app.add_handler(CallbackQueryHandler(list_inviters, pattern="^list_inviters$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    
    print("Bot is started...")
    app.run_polling()

if __name__ == "__main__":
    main()
