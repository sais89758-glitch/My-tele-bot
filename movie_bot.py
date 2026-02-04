# Zan Movie Channel Bot – FULL FINAL VERSION (Fixed Token & Asyncio)
# Architect: System Architect & Senior Python Developer
# Version: 2.3 (Added VIP Channel Link on Approval)

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
# UPDATED TOKEN FROM 'NOW CODE.txt' (The working one)
BOT_TOKEN = "8515688348:AAH45NOcsGPPD9UMyc43u8zDLLnlKS8eGs0" 
ADMIN_ID = 6445257462
VIP_PRICE = 30000
PAY_PHONE = "09960202983"
PAY_NAME = "Sai Zaw Ye Lwin"
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"

# ================= LOGGING SETUP =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("movie_bot.db", check_same_thread=False)
    cur = conn.cursor()
    
    # Users Table (VIP Status)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        is_vip INTEGER DEFAULT 0,
        vip_expiry TEXT
    )
    """)
    
    # Payments Table (Transaction History)
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

# Initialize DB immediately
init_db()

# ================= STATES FOR CONVERSATION =================
WAITING_SLIP, WAITING_NAME = range(2)

# ================= HELPER FUNCTIONS =================
def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

async def check_is_admin(update: Update):
    user_id = update.effective_user.id
    return user_id == ADMIN_ID

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

    # Handle both new message and callback edit
    if update.callback_query:
        await target.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= VIP FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n"
        "⛔️ ခွဲလွဲပါက VIP မအတည်ပြုပါ\n\n"
        "⛔️ Screenshot / Screen Record / Download / Forward မရ\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )

    kb = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")],
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kb = [
        [InlineKeyboardButton("KBZ Pay", callback_data="pay_KBZ")],
        [InlineKeyboardButton("Wave Pay", callback_data="pay_Wave")],
        [InlineKeyboardButton("AYA Pay", callback_data="pay_AYA")],
        [InlineKeyboardButton("CB Pay", callback_data="pay_CB")],
        [InlineKeyboardButton("Back", callback_data="back_home")],
    ]
    await query.message.edit_text("ငွေပေးချေမှုနည်းလမ်းရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    text = (
        f"ငွေလွဲရန် ({VIP_PRICE} MMK)\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {PAY_PHONE}\n"
        f"👤 အမည်: {PAY_NAME}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )
    
    await query.message.edit_text(text)
    return WAITING_SLIP

# ================= CONVERSATION HANDLERS =================
async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။")
        return WAITING_SLIP

    photo = update.message.photo[-1]
    file_id = photo.file_id
    slip_hash = hashlib.md5(file_id.encode()).hexdigest()

    context.user_data["slip_hash"] = slip_hash
    context.user_data["slip_file"] = file_id

    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည်ကို ပို့ပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    user_id = update.effective_user.id
    method = context.user_data.get("method", "Unknown")
    slip_hash = context.user_data.get("slip_hash", "NoHash")
    file_id = context.user_data.get("slip_file")

    # Save PENDING payment
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, slip_hash, account_name, status, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, method, slip_hash, account_name, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    # Notify User
    await update.message.reply_text(
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )

    # Notify Admin
    kb = [
        [InlineKeyboardButton("✅ အတည်ပြုသည်", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ ငြင်းပယ်သည်", callback_data=f"reject_{user_id}")],
    ]
    
    caption = (
        f"📌 New VIP Request\n"
        f"User ID: {user_id}\n"
        f"Method: {method}\n"
        f"Name: {account_name}\n"
        f"Amount: {VIP_PRICE}"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb)
    )

    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("လုပ်ဆောင်မှုကို ပယ်ဖျက်လိုက်ပါပြီ။ /start ပြန်နှိပ်ပါ။")
    return ConversationHandler.END

# ================= ADMIN ACTIONS =================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, user_id_str = data.split("_")
    user_id = int(user_id_str)

    conn = get_db()
    cur = conn.cursor()

    if action == "approve":
        # Activate VIP
        expiry_date = (datetime.now() + timedelta(days=30)).isoformat()
        
        # Update User
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, expiry_date))
        
        # Update Payment Status
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        
        conn.commit()
        
        # Updated Approval Message with Channel Link
        vip_text = (
            "✅ VIP အတည်ပြုပြီးပါပြီ။ (30 ရက်)\n"
            "Channel တွင် ဇာတ်ကားများ ကြည့်ရှုနိုင်ပါပြီ။"
        )
        vip_kb = [[InlineKeyboardButton("🍿 VIP Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)]]
        
        await context.bot.send_message(
            user_id, 
            vip_text, 
            reply_markup=InlineKeyboardMarkup(vip_kb)
        )
        
        await query.edit_message_caption(caption=query.message.caption + "\n\n✅ Approved by Admin")
        
    elif action == "reject":
        # Update Payment Status
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        conn.commit()
        
        await context.bot.send_message(user_id, "❌ ငွေမရောက်ပါ သို့မဟုတ် အချက်အလက်မှားယွင်းနေပါသည်။")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ Rejected by Admin")

    conn.close()

# ================= ADMIN DASHBOARD (/tharngal) =================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return # Ignore non-admins

    conn = get_db()
    cur = conn.cursor()
    
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    # 1. Today Income
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{today_str}%",))
    today_count = cur.fetchone()[0]
    today_income = today_count * VIP_PRICE

    # 2. Month Income
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED' AND created_at LIKE ?", (f"{month_str}%",))
    month_count = cur.fetchone()[0]
    month_income = month_count * VIP_PRICE

    # 3. Total Income
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    total_count = cur.fetchone()[0]
    total_income = total_count * VIP_PRICE

    # 4. Active VIPs
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    active_vips = cur.fetchone()[0]

    # 5. Rejected/Scam
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='REJECTED'")
    rejected_count = cur.fetchone()[0]

    # 6. Recent List (Calendar style simplified)
    list_text = "📅 <b>လတ်တလော ဝင်ငွေစာရင်း</b>\n"
    cur.execute("SELECT created_at, account_name FROM payments WHERE status='APPROVED' ORDER BY id DESC LIMIT 5")
    recent = cur.fetchall()
    for date_str, name in recent:
        dt = datetime.fromisoformat(date_str).strftime("%d/%m %H:%M")
        list_text += f"- {dt} : {name}\n"

    conn.close()

    text = (
        "📊 <b>Admin Dashboard</b>\n\n"
        f"📅 ယနေ့ ဝင်ငွေ: {today_income} MMK\n"
        f"🗓 ယခုလ ဝင်ငွေ: {month_income} MMK\n"
        f"💰 စုစုပေါင်း: {total_income} MMK\n"
        f"👥 Active VIP: {active_vips} ယောက်\n"
        f"❌ Scam/Reject: {rejected_count}\n\n"
        f"{list_text}"
    )

    kb = [[InlineKeyboardButton("🔙 Back to Home", callback_data="back_home")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= BACKGROUND TASK: EXPIRY CHECKER =================
async def vip_expiry_checker(app: Application):
    """Checks for expired VIPs every hour using asyncio loop"""
    while True:
        try:
            conn = get_db()
            cur = conn.cursor()
            
            now = datetime.now().isoformat()
            # Find expired users
            cur.execute("SELECT user_id FROM users WHERE is_vip=1 AND vip_expiry < ?", (now,))
            expired_users = cur.fetchall()

            for (uid,) in expired_users:
                try:
                    # Update DB
                    cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (uid,))
                    conn.commit()
                    # Notify User
                    await app.bot.send_message(uid, "⛔️ VIP သက်တမ်းကုန်သွားပါပြီ။ သက်တမ်းတိုးရန် /start နှိပ်ပါ။")
                    logger.info(f"Expired VIP for user {uid}")
                except Exception as e:
                    logger.error(f"Failed to expire user {uid}: {e}")
            
            conn.close()
        except Exception as e:
            logger.error(f"Error in vip_expiry_checker: {e}")
        
        # Wait for 1 hour
        await asyncio.sleep(3600)

async def post_init(app: Application):
    """Start background tasks"""
    app.create_task(vip_expiry_checker(app))

# ================= MAIN APP LOOP =================
def main():
    # Builder setup with post_init to start background tasks
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # 1. Conversation Handler (Must be before basic handlers)
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, receive_slip)],
        states={
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel_conv)],
    )
    application.add_handler(conv_handler)

    # 2. Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tharngal", admin_dashboard))

    # 3. Callback Handlers
    application.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    application.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    application.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    application.add_handler(CallbackQueryHandler(payment_info, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    # Start Polling
    logger.info("Bot is starting...")
    # drop_pending_updates=True ensures the bot starts fresh and ignores old piled up messages
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
