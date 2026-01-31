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
# သင်ပေးထားသော API Key ကို ဤနေရာတွင် ထည့်သွင်းထားသည်
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
    # Transactions Table (For Stats)
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT, 
        movie_id INTEGER,
        date DATE,
        status TEXT 
    )''')
    # Visitor Log
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
# AI RECEIPT CHECKER (GEMINI)
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    import base64
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
    
    prompt = f"""
    Analyze this Burmese bank receipt (KPay/WavePay/CB/AYA/KBZ). 
    1. Is this a real transaction receipt? (Yes/No)
    2. What is the transaction amount in MMK?
    3. Return ONLY a JSON object: {{"is_valid": boolean, "amount": number, "is_scam": boolean}}
    The expected amount is {expected_amount} MMK.
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
# HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, today))
    db_query("INSERT OR IGNORE INTO visitors (user_id, date) VALUES (?,?)", (user.id, today))

    welcome_text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "🔥 **Channel အသစ်ဖွင့်ပွဲ အထူးလျှော့ဈေး!!**\n"
        f"ယခုဝယ်ယူပါက VIP Member ကြေး - ~~30000~~ **{VIP_PRICE} MMK** သာ\n\n"
        "✅ VIP များ ဇာတ်ကားအားလုံးကို အကန့်အသတ်မရှိ ကြည့်နိုင်ပါမည်။\n"
        "✅ တစ်ကားချင်းဝယ်ယူပါကလည်း Lifetime ကြည့်ရှုနိုင်ပါသည်။"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် ({VIP_PRICE} Ks)", callback_data="join_vip")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့သွားရန်", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")]
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split("_")[-1])
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    keyboard = []
    for m in movies:
        keyboard.append([InlineKeyboardButton(f"{m[1]} - {m[2]} Ks (~~3000~~)", callback_data=f"view_{m[0]}")])
    
    nav = [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
    if len(movies) == 6: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"movie_menu_{page+1}"))
    keyboard.append(nav)
    
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း (PROMO PRICE)**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def view_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    m_id = int(query.data.split("_")[-1])
    movie = db_query("SELECT * FROM movies WHERE id=?", (m_id,), fetchone=True)
    user_id = query.from_user.id
    
    # Check access logic
    is_vip = db_query("SELECT is_vip, vip_expiry FROM users WHERE user_id=? AND is_vip=1", (user_id,), fetchone=True)
    has_bought = db_query("SELECT * FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip or has_bought:
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}\n\n✅ ကြည့်ရှုနိုင်ပါပြီ။", protect_content=True)
    else:
        text = f"🎬 **{movie[2]}**\n💰 ဈေးနှုန်း: ~~3000~~ **{movie[3]} MMK**"
        keyboard = [
            [InlineKeyboardButton(f"💳 {movie[3]} Ks ဖြင့် ဝယ်ယူမည်", callback_data=f"pay_single_{m_id}")],
            [InlineKeyboardButton(f"👑 VIP ဝင်မည် ({VIP_PRICE} Ks)", callback_data="join_vip")],
            [InlineKeyboardButton("🔙 Back", callback_data="movie_menu_1")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==========================================
# PAYMENT FLOW
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
        "⚠️ **အရေးကြီးသတိပေးချက်**\n"
        "• ငွေပမာဏကို တစ်ခါတည်း အပြည့်အဝလွဲရပါမည်။\n"
        "• ခွဲလွဲခြင်း (သို့) ပမာဏမပြည့်ပါက **ပြန်အမ်းမည်မဟုတ်သလို ဖွင့်ပေးမည်လည်းမဟုတ်ပါ။**\n"
        "• ပြေစာအတုတင်ပါက Bot မှ အမြဲတမ်း Ban ပါမည်။\n\n"
        "ငွေလွဲပြီးပါက **ပြေစာ Screenshot** ကို ပို့ပေးပါ။"
    )
    await query.message.reply_text(pay_text, parse_mode=ParseMode.MARKDOWN)
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပြေစာပုံကိုသာ ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    photo = await update.message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    expected = context.user_data['expected_amount']
    
    msg = await update.message.reply_text("🔍 AI စနစ်ဖြင့် ပြေစာအား စစ်ဆေးနေပါသည်...")
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
        
        await msg.edit_text("✅ ငွေလက်ခံရရှိမှု အတည်ပြုပြီးပါပြီ။ အသုံးပြုနိုင်ပါပြီ။")
    else:
        status = 'scam' if result.get('is_scam') else 'failed'
        db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, 0, 'scam', today, status))
        
        error_msg = "❌ ငွေလွဲမှု မအောင်မြင်ပါ။ "
        if result.get('amount', 0) < expected and not result.get('is_scam'):
            error_msg += f"ငွေပမာဏ {result.get('amount')} သာရှိပြီး လိုအပ်သည်ထက် နည်းနေပါသည်။"
        else:
            error_msg += "ပြေစာသည် မှန်ကန်မှုမရှိခြင်း (သို့) Scam ဖြစ်နိုင်ပါသည်။"
            db_query("UPDATE users SET is_scammer=1 WHERE user_id=?", (user.id,))
        
        await msg.edit_text(error_msg)
        
        # Admin Alert
        alert = (
            f"⚠️ **Scam Alert!**\n"
            f"User: {user.full_name} (@{user.username})\n"
            f"ID: `{user.id}`\n"
            f"Expected: {expected} Ks\n"
            f"AI Detected: {result.get('amount')} Ks"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert)

    return ConversationHandler.END

# ==========================================
# ADMIN STATS COMMAND
# ==========================================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    now = datetime.now()
    month_name = now.strftime("%B")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    
    # Queries
    total_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    vip_today = db_query("SELECT COUNT(*) FROM transactions WHERE type='vip' AND date=? AND status='success'", (today,), fetchone=True)[0]
    single_today = db_query("SELECT m.title, COUNT(*) FROM transactions t JOIN movies m ON t.movie_id = m.id WHERE t.type='single' AND t.date=? AND t.status='success' GROUP BY m.id", (today,))
    
    scams_today = db_query("SELECT COUNT(*) FROM transactions WHERE status='scam' AND date=?", (today,), fetchone=True)[0]
    total_scams = db_query("SELECT COUNT(*) FROM users WHERE is_scammer=1", fetchone=True)[0]
    
    visitors_today = db_query("SELECT COUNT(*) FROM visitors WHERE date=?", (today,), fetchone=True)[0]
    total_visitors = db_query("SELECT COUNT(DISTINCT user_id) FROM visitors", fetchone=True)[0]
    
    rev_today = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND status='success'", (today,), fetchone=True)[0] or 0
    rev_month = db_query("SELECT SUM(amount) FROM transactions WHERE date >= ? AND status='success'", (month_start,), fetchone=True)[0] or 0

    msg = (
        f"📊 **Zan Movie Bot Admin Panel ({month_name})**\n"
        f"📅 ယနေ့ရက်စွဲ: {today}\n\n"
        f"💰 **ဝင်ငွေစာရင်း:**\n- ယနေ့ဝင်ငွေ: {rev_today} MMK\n- ယခုလစုစုပေါင်း: {rev_month} MMK\n\n"
        f"👑 **VIP စာရင်း:**\n- ယနေ့ VIP အသစ်: {vip_today}\n- စုစုပေါင်း VIP: {total_vip}\n\n"
        f"🎬 **ယနေ့ တစ်ကားချင်းဝယ်ယူမှု:**\n"
    )
    for row in single_today:
        msg += f"- {row[0]}: {row[1]} ကား\n"
    
    msg += (
        f"\n👥 **လူဝင်ရောက်မှု:**\n- ယနေ့လာကြည့်သူ: {visitors_today}\n- စုစုပေါင်း: {total_visitors}\n\n"
        f"🚫 **Scam ဖမ်းမိမှု:**\n- ယနေ့ Scam: {scams_today}\n- စုစုပေါင်း Scammer: {total_scams}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# ==========================================
# CHANNEL AUTO SYNC
# ==========================================
async def channel_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if msg.video and msg.caption:
        price_tag = re.search(r"#(\d+)MMK", msg.caption)
        if price_tag:
            price = int(price_tag.group(1))
            title = msg.caption.split('\n')[0]
            db_query("INSERT INTO movies (file_id, title, price, added_date) VALUES (?,?,?,?)", 
                     (msg.video.file_id, title, price, datetime.now().strftime("%Y-%m-%d")))

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    pay_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_payment, pattern="^(join_vip|pay_single_)")],
        states={UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, confirm_receipt)]},
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", admin_stats))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))
    app.add_handler(pay_handler)
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & filters.VIDEO, channel_listener))
    
    app.run_polling()

if __name__ == "__main__":
    main()
