# Zan Movie Channel Bot – FULL FINAL VERSION
# Architect: System Architect & Senior Python Developer
# Version: 2.8 (Admin Custom Auto-Delete Ad Features)

import logging
import sqlite3
import hashlib
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
PAY_PHONE = "09960202983"
PAY_NAME = "Sai Zaw Ye Lwin"

# Links & IDs
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
MAIN_CHANNEL_ID = "@ZanchannelMM" 
VIP_CHANNEL_URL = "https://t.me/c/3863175003/1"

# ================= LOGGING SETUP =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("movie_bot.db", check_same_thread=False)
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
        slip_hash TEXT,
        account_name TEXT,
        status TEXT,
        amount INTEGER DEFAULT 30000,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= STATES =================
WAITING_SLIP, WAITING_NAME = range(2)
WAITING_AD_CONTENT, WAITING_AD_TIME = range(3, 5)

# ================= HELPERS =================
def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

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
    text = (f"ငွေလွဲရန် ({VIP_PRICE} MMK)\n\n💳 {method} Pay\n📱 ဖုန်း: {PAY_PHONE}\n👤 အမည်: {PAY_NAME}\n\n‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\nခွဲလွဲ / မှားလွဲပါက\nငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n⚠️ ပြေစာ Screenshot ပို့ပါ")
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
    
    # Updated Success Message for User
    success_text = (
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )
    await update.message.reply_text(success_text)
    
    # Notify Admin
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

# ================= ADMIN DASHBOARD =================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
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
        cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{d}%",))
        amt = cur.fetchone()[0] * VIP_PRICE
        cal_text += f"{'💰' if amt>0 else '⚪️'} {d[5:]}: {amt} MMK\n"
    conn.close()
    text = (f"📊 <b>Admin Dashboard</b>\n\n💵 ယနေ့: {t_inc} MMK\n📅 ယခုလ: {m_inc} MMK\n💰 စုစုပေါင်း: {all_inc} MMK\n\n👥 VIP: {vips} ယောက်\n❌ Reject: {rejs}\n\n{cal_text}")
    kb = [[InlineKeyboardButton("📋 စာရင်း", callback_data="admin_list"), InlineKeyboardButton("📢 ကြော်ညာ", callback_data="admin_ads")],[InlineKeyboardButton("💳 Payment", callback_data="admin_pay"), InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
    if update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN BROADCAST (CUSTOM DELETE TIME) =================
async def admin_ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📢 Main Channel သို့ ပို့လိုသော ကြော်ညာ (စာသား သို့မဟုတ် ပုံ) ကို ပို့ပေးပါ။")
    return WAITING_AD_CONTENT

async def receive_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    # Store message content for later broadcast
    context.user_data['ad_photo'] = msg.photo[-1].file_id if msg.photo else None
    context.user_data['ad_text'] = msg.caption if msg.photo else msg.text
    
    # Ask for delete time
    kb = [
        [InlineKeyboardButton("၁ နာရီကြာလျှင်ဖျက်", callback_data="adtime_3600"), InlineKeyboardButton("၆ နာရီကြာလျှင်ဖျက်", callback_data="adtime_21600")],
        [InlineKeyboardButton("၁ ရက်ကြာလျှင်ဖျက်", callback_data="adtime_86400"), InlineKeyboardButton("၃ ရက်ကြာလျှင်ဖျက်", callback_data="adtime_259200")],
        [InlineKeyboardButton("မဖျက်ပါ", callback_data="adtime_0")]
    ]
    await msg.reply_text("⏰ ကြော်ညာကို ဘယ်လောက်ကြာရင် အော်တိုဖျက်ပေးရမလဲ ရွေးချယ်ပါ။", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_AD_TIME

async def finalize_ad_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    delete_seconds = int(query.data.split("_")[1])
    photo = context.user_data.get('ad_photo')
    text = context.user_data.get('ad_text')
    
    try:
        if photo:
            sent_msg = await context.bot.send_photo(chat_id=MAIN_CHANNEL_ID, photo=photo, caption=text)
        else:
            sent_msg = await context.bot.send_message(chat_id=MAIN_CHANNEL_ID, text=text)
            
        success_msg = "✅ ကြော်ညာကို Main Channel ထံ ပို့လိုက်ပါပြီ။"
        if delete_seconds > 0:
            success_msg += f"\n(သတ်မှတ်ထားသောအချိန်ပြည့်ပါက Bot က အော်တိုဖျက်ပေးပါမည်)"
            
            # Auto-delete logic
            async def auto_delete(seconds, msg_id):
                await asyncio.sleep(seconds)
                try:
                    await context.bot.delete_message(chat_id=MAIN_CHANNEL_ID, message_id=msg_id)
                    logger.info(f"Auto-deleted message {msg_id}")
                except Exception as e:
                    logger.error(f"Auto-delete failed: {e}")
            
            asyncio.create_task(auto_delete(delete_seconds, sent_msg.message_id))
        
        await query.message.edit_text(success_msg)
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")
    
    return ConversationHandler.END

# ================= CALLBACKS =================
async def admin_btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    if query.data == "admin_ads": return await admin_ads_start(update, context)
    await query.message.reply_text(f"လုပ်ဆောင်ချက် '{query.data}' ကို ပြင်ဆင်နေဆဲဖြစ်သည်။")

# ================= BACKGROUND TASKS =================
async def vip_expiry_checker(app: Application):
    while True:
        try:
            conn = get_db(); cur = conn.cursor(); now = datetime.now().isoformat()
            cur.execute("SELECT user_id FROM users WHERE is_vip=1 AND vip_expiry < ?", (now,))
            expired = cur.fetchall()
            for (uid,) in expired:
                cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (uid,))
                conn.commit()
                await app.bot.send_message(uid, "⛔️ VIP သက်တမ်းကုန်သွားပါပြီ။")
            conn.close()
        except: pass
        await asyncio.sleep(3600)

async def post_init(app: Application):
    app.create_task(vip_expiry_checker(app))

# ================= MAIN =================
def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_slip),
            CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")
        ],
        states={
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, receive_ad_content)],
            WAITING_AD_TIME: [CallbackQueryHandler(finalize_ad_broadcast, pattern="^adtime_")],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tharngal", admin_dashboard))
    application.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    application.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^back_home$"))
    application.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    application.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    application.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    application.add_handler(CallbackQueryHandler(admin_btn_callback, pattern="^admin_"))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
