import logging
import sqlite3
import re
import asyncio
import json
import requests
from datetime import datetime, timedelta
from typing import Final

# Telegram Bot Library
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram.constants import ParseMode

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN: Final = "8515688348:AAE0a7XcOIfRF9DJfrbdLNFsnJxPJFem18o" 
ADMIN_ID: Final = 6445257462               
CHANNEL_ID: Final = "@ZanchannelMM" 
DB_NAME: Final = "movie_database.db"
# Gemini API Key (Provided by user)
GEMINI_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk" 

# VIP Pricing
VIP_PRICE: Final = 10000

# Conversation State
UPLOAD_RECEIPT = 1

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ==========================================
# DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_vip BOOLEAN DEFAULT 0,
        vip_expiry DATE,
        joined_date DATE,
        is_scammer BOOLEAN DEFAULT 0
    )''')
    # Movies Table
    c.execute('''CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT,
        title TEXT,
        price INTEGER,
        added_date DATE
    )''')
    # Purchases Table (Lifetime Access)
    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
        user_id INTEGER,
        movie_id INTEGER,
        PRIMARY KEY (user_id, movie_id)
    )''')
    # Transactions Table (For Stats & Tracking)
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT, -- 'vip' or 'single'
        movie_id INTEGER,
        date DATE,
        status TEXT -- 'success' or 'scam' or 'failed'
    )''')
    # Visitor Log (For non-buyers count)
    c.execute('''CREATE TABLE IF NOT EXISTS visitors (
        user_id INTEGER,
        date DATE,
        PRIMARY KEY (user_id, date)
    )''')
    conn.commit()
    conn.close()

def db_query(query, args=(), fetchone=False, commit=True):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, args)
    if commit: conn.commit()
    data = c.fetchone() if fetchone else c.fetchall()
    conn.close()
    return data

# ==========================================
# AI RECEIPT CHECKER (GEMINI 1.5 FLASH)
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    import base64
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
    
    prompt = f"""
    Analyze this Burmese bank receipt (KPay/WavePay/CB/AYA/KBZ). 
    1. Check if this is a valid transaction receipt (not a scam or random photo).
    2. Extract the transaction amount in MMK.
    3. Return ONLY a JSON object: {{"is_valid": boolean, "amount": number, "is_scam": boolean}}
    Expected amount is {expected_amount} MMK.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": base64_image}}
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=25)
        result = response.json()
        text_res = result['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_res)
    except Exception as e:
        logging.error(f"AI Verification Error: {e}")
        return {"is_valid": False, "amount": 0, "is_scam": False}

# ==========================================
# USER HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, today))
    db_query("INSERT OR IGNORE INTO visitors (user_id, date) VALUES (?,?)", (user.id, today))

    welcome_text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "🔥 **အထူးပရိုမိုးရှင်း လျှော့ဈေး!!**\n"
        f"VIP Member - ~~30000~~ **{VIP_PRICE} MMK** (တစ်လစာ)\n\n"
        "✅ VIP များ ဇာတ်ကားအားလုံးကို Free ကြည့်နိုင်ပါမည်။\n"
        "✅ တစ်ကားချင်းဝယ်ယူပါကလည်း Lifetime သိမ်းထားနိုင်ပါသည်။"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({VIP_PRICE} Ks)", callback_data="join_vip")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")]
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page_str = query.data.split("_")[-1]
    page = int(page_str) if page_str.isdigit() else 1
    
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    if not movies:
        await query.answer("ဇာတ်ကားများ မရှိသေးပါ။")
        return

    keyboard = []
    for m in movies:
        keyboard.append([InlineKeyboardButton(f"{m[1]} - {m[2]} Ks", callback_data=f"view_{m[0]}")])
    
    nav = [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
    if len(movies) == 6: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"movie_menu_{page+1}"))
    keyboard.append(nav)
    
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def view_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    m_id = int(query.data.split("_")[-1])
    movie = db_query("SELECT * FROM movies WHERE id=?", (m_id,), fetchone=True)
    user_id = query.from_user.id
    
    is_vip = db_query("SELECT is_vip FROM users WHERE user_id=? AND is_vip=1", (user_id,), fetchone=True)
    has_bought = db_query("SELECT * FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip or has_bought:
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}\n\n✅ စိတ်ကြိုက်ကြည့်ရှုနိုင်ပါပြီ။", protect_content=True)
    else:
        text = f"🎬 **{movie[2]}**\n💰 ဈေးနှုန်း: **{movie[3]} MMK**"
        keyboard = [
            [InlineKeyboardButton(f"💳 {movie[3]} Ks ဖြင့် ဝယ်မည်", callback_data=f"pay_single_{m_id}")],
            [InlineKeyboardButton(f"👑 VIP ဝင်မည် ({VIP_PRICE} Ks)", callback_data="join_vip")],
            [InlineKeyboardButton("🔙 Back", callback_data="movie_menu_1")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==========================================
# PAYMENT & AUTO VERIFICATION
# ==========================================
async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    context.user_data['p_type'] = 'vip' if 'join_vip' in data else 'single'
    if 'pay_single_' in data: context.user_data['m_id'] = int(data.split("_")[-1])
    
    expected = VIP_PRICE if context.user_data['p_type'] == 'vip' else db_query("SELECT price FROM movies WHERE id=?", (context.user_data['m_id'],), fetchone=True)[0]
    context.user_data['expected_amount'] = expected

    pay_text = (
        f"💳 **ငွေပေးချေမှု ({expected} Ks)**\n\n"
        "KPay/Wave: 09123456789 (U Mg Mg)\n\n"
        "⚠️ **သတိပေးချက် (ဖတ်ပေးပါ)**\n"
        "• ငွေပမာဏကို တစ်ခါတည်း အပြည့်အဝလွဲရပါမည်။\n"
        "• **ခွဲလွဲခြင်း (သို့) ပမာဏမပြည့်ပါက ပြန်အမ်းမည်မဟုတ်သလို ဖွင့်ပေးမည်လည်းမဟုတ်ပါ။**\n"
        "• ပြေစာပုံမဟုတ်ဘဲ တခြားပုံတင်ခြင်း (သို့) ပြေစာအတုတင်ခြင်းများ (Scam) ရှိပါက Bot မှ အမြဲတမ်း Ban ပါမည်။\n\n"
        "ငွေလွဲပြီးပါက **ပြေစာ Screenshot** ကို ပို့ပေးပါ။"
    )
    await query.message.reply_text(pay_text, parse_mode=ParseMode.MARKDOWN)
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပြေစာ Screenshot ပုံကိုသာ ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    photo = await update.message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    expected = context.user_data['expected_amount']
    
    loading_msg = await update.message.reply_text("🔍 AI စနစ်ဖြင့် ပြေစာအား စစ်ဆေးနေပါသည်...")
    result = await verify_receipt_with_ai(photo_bytes, expected)
    today = datetime.now().strftime("%Y-%m-%d")

    if result.get('is_valid') and result.get('amount', 0) >= expected:
        if context.user_data['p_type'] == 'vip':
            expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            db_query("UPDATE users SET is_vip=1, vip_expiry=? WHERE user_id=?", (expiry, user.id))
            db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, expected, 'vip', today, 'success'))
        else:
            m_id = context.user_data['m_id']
            db_query("INSERT OR IGNORE INTO purchases (user_id, movie_id) VALUES (?,?)", (user.id, m_id))
            db_query("INSERT INTO transactions (user_id, amount, type, movie_id, date, status) VALUES (?,?,?,?,?,?)", (user.id, expected, 'single', m_id, today, 'success'))
        
        await loading_msg.edit_text("✅ ငွေလက်ခံရရှိမှု အတည်ပြုပြီးပါပြီ။ စိတ်ကြိုက်ကြည့်ရှုနိုင်ပါပြီ။")
    else:
        is_scam = result.get('is_scam', False)
        status = 'scam' if is_scam else 'failed'
        db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, 0, 'scam', today, status))
        
        fail_text = "❌ ငွေလွဲမှု မအောင်မြင်ပါ။ "
        if result.get('amount', 0) < expected and not is_scam:
            fail_text += f"ငွေပမာဏ {result.get('amount')} သာရှိပြီး လိုအပ်သည်ထက် နည်းနေပါသည်။"
        else:
            fail_text += "ပြေစာသည် မှန်ကန်မှုမရှိခြင်း (သို့) ပုံစံမမှန်ခြင်း (Scam) ဖြစ်နိုင်ပါသည်။"
            db_query("UPDATE users SET is_scammer=1 WHERE user_id=?", (user.id,))
        
        await loading_msg.edit_text(fail_text)
        
        alert_text = (
            f"⚠️ **Scam Alert!**\n"
            f"User: {user.full_name} (@{user.username})\n"
            f"ID: `{user.id}`\n"
            f"Detected Amount: {result.get('amount')} MMK\n"
            f"Status: {status.upper()}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert_text)

    return ConversationHandler.END

# ==========================================
# ADMIN COMMANDS & STATS
# ==========================================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    now = datetime.now()
    month_name = now.strftime("%B")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    
    total_vip_members = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    vip_joined_today = db_query("SELECT COUNT(*) FROM transactions WHERE type='vip' AND date=? AND status='success'", (today,), fetchone=True)[0]
    
    movie_sales_today = db_query("""
        SELECT m.title, COUNT(*) 
        FROM transactions t 
        JOIN movies m ON t.movie_id = m.id 
        WHERE t.type='single' AND t.date=? AND t.status='success' 
        GROUP BY m.id
    """, (today,))
    
    scams_today = db_query("SELECT COUNT(*) FROM transactions WHERE status='scam' AND date=?", (today,), fetchone=True)[0]
    total_banned = db_query("SELECT COUNT(*) FROM users WHERE is_scammer=1", fetchone=True)[0]
    
    visitors_today = db_query("SELECT COUNT(*) FROM visitors WHERE date=?", (today,), fetchone=True)[0]
    total_visitors = db_query("SELECT COUNT(DISTINCT user_id) FROM visitors", fetchone=True)[0]
    
    rev_today = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND status='success'", (today,), fetchone=True)[0] or 0
    rev_month = db_query("SELECT SUM(amount) FROM transactions WHERE date >= ? AND status='success'", (month_start,), fetchone=True)[0] or 0

    report = (
        f"📊 **Admin Report - {month_name}**\n"
        f"📅 Today: {today}\n\n"
        f"💰 **Revenue (MMK):**\n- ယနေ့ဝင်ငွေ: {rev_today} Ks\n- ယခုလစုစုပေါင်း: {rev_month} Ks\n\n"
        f"👑 **VIP Membership:**\n- ယနေ့ဝင်သူ: {vip_joined_today}\n- စုစုပေါင်း VIP: {total_vip_members}\n\n"
        f"🎬 **ဇာတ်ကားဝယ်ယူမှု (ယနေ့):**\n"
    )
    for movie in movie_sales_today:
        report += f"- {movie[0]}: {movie[1]} ယောက်\n"
    
    report += (
        f"\n👥 **Traffic:**\n- ယနေ့ Visitor: {visitors_today}\n- စုစုပေါင်း Visitor: {total_visitors}\n\n"
        f"🚫 **Security:**\n- ယနေ့ Scam မိသူ: {scams_today}\n- စုစုပေါင်း Ban ထားသူ: {total_banned}"
    )
    await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)

# ==========================================
# CHANNEL SYNC
# ==========================================
async def channel_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if msg and msg.video and msg.caption:
        price_match = re.search(r"#(\d+)MMK", msg.caption)
        if price_match:
            price = int(price_match.group(1))
            title = msg.caption.split('\n')[0].strip()
            db_query("INSERT INTO movies (file_id, title, price, added_date) VALUES (?,?,?,?)", 
                     (msg.video.file_id, title, price, datetime.now().strftime("%Y-%m-%d")))

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    
    # Render Fix: Use a more direct application building approach
    # Avoids internal Updater attribute issues in certain environments
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Manual check: Application needs to handle specific setup
    pay_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_payment, pattern="^(join_vip|pay_single_)")],
        states={UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, confirm_receipt)]},
        fallbacks=[CommandHandler("start", start)]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("saizawyelwin", admin_stats))
    application.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    application.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    application.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))
    application.add_handler(pay_handler)
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL & filters.VIDEO, channel_listener))
    
    # Start the bot
    print("Bot started...")
    application.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
