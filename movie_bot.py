import logging
import sqlite3
import json
import requests
import os
import base64
import asyncio
import threading
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
from typing import Final

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
    Defaults
)
from telegram.constants import ParseMode

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN: Final = "8515688348:AAHg86mbsY60QAa8U-17xmQXM38o_ggDEM4" 
ADMIN_ID: Final = 6445257462              
CHANNEL_URL: Final = "https://t.me/ZanchannelMM" 
DB_NAME: Final = "movie_database.db"
GEMINI_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk" 

# Pricing
PRICE_BASIC: Final = 10000
PRICE_PRO: Final = 30000

# Conversation States
UPLOAD_RECEIPT = 1
SETTING_PAY_INFO = 2
ADD_MOVIE_STATE = 3

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# RENDER HEALTH CHECK SERVER
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# DATABASE
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, vip_expiry DATE, joined_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, movie_id INTEGER, PRIMARY KEY (user_id, movie_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, type TEXT, date DATE, status TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS visitors (user_id INTEGER, date DATE, PRIMARY KEY (user_id, date))''')
        
        payments = [('kpay', 'None', 'None', ''), ('wave', 'None', 'None', ''), ('ayapay', 'None', 'None', ''), ('cbpay', 'None', 'None', '')]
        c.executemany("INSERT OR IGNORE INTO payment_settings VALUES (?,?,?,?)", payments)
        conn.commit()
        conn.close()

def db_query(query, args=(), fetchone=False, commit=True):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME, check_same_thread=False)
            c = conn.cursor()
            c.execute(query, args)
            if commit: conn.commit()
            data = c.fetchone() if fetchone else c.fetchall()
            conn.close()
            return data
        except Exception as e:
            logger.error(f"DB Error: {e}")
            return None

# ==========================================
# FUNCTIONS
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
    prompt = f"Extract amount from this Burmese receipt. Return ONLY JSON: {{\"is_valid\": bool, \"amount\": num}}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/png", "data": base64_image}}]}]}
    try:
        r = requests.post(url, json=payload, timeout=25)
        return json.loads(r.json()['candidates'][0]['content']['parts'][0]['text'])
    except: return {"is_valid": False, "amount": 0}

async def broadcast_new_movie(context: ContextTypes.DEFAULT_TYPE, title: str, movie_id: int):
    users = db_query("SELECT user_id FROM users")
    text = f"🔔 **ဇာတ်ကားသစ်တင်လိုက်ပါပြီ!**\n\n🎬 အမည်: **{title}**"
    kb = [[InlineKeyboardButton("📺 ကြည့်ရှုမည်", callback_data=f"view_{movie_id}")]]
    for (uid,) in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.05)
        except: continue

# ==========================================
# HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", (user.id, user.username, user.full_name, today))
    db_query("INSERT OR IGNORE INTO visitors (user_id, date) VALUES (?,?)", (user.id, today))

    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "**လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:**\n"
        "⛔️ ဇာတ်ကားများကို **SS ရိုက်ခြင်း**၊ **Video Record ဖမ်းခြင်း**၊ **ဖုန်းထဲသို့ Save လုပ်ခြင်း** နှင့် Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ ဝယ်ယူထားသောကားများကို Bot အတွင်း ရာသက်ပန် ပြန်ကြည့်နိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        f"1️⃣ Basic VIP ({PRICE_BASIC} Ks) - 1 Month\n"
        f"2️⃣ Pro VIP ({PRICE_PRO} Ks) - Lifetime\n"
    )
    kb = [[InlineKeyboardButton("👑 Basic VIP", callback_data="buy_vip_basic"), InlineKeyboardButton("👑 Pro VIP", callback_data="buy_vip_pro")],
          [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
          [InlineKeyboardButton("📢 Channel", url=CHANNEL_URL)]]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    if not movies: return await query.answer("ဇာတ်ကားမရှိသေးပါ။", show_alert=True)
    
    kb = [[InlineKeyboardButton(f"{m[1]} ({m[2]} Ks)", callback_data=f"view_{m[0]}")] for m in movies]
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"movie_menu_{page-1}"))
    if db_query("SELECT 1 FROM movies LIMIT 1 OFFSET ?", (page*6,)): nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"movie_menu_{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("🏠 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def view_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    m_id = int(query.data.split("_")[-1])
    movie = db_query("SELECT * FROM movies WHERE id=?", (m_id,), fetchone=True)
    user_id = query.from_user.id
    
    is_vip = db_query("SELECT is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)[0]
    has_purchased = db_query("SELECT 1 FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip >= 1 or has_purchased:
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}", protect_content=True)
    else:
        text = f"🎬 **{movie[2]} (Preview)**\n\n၃ မိနစ်စာ နမူနာသာ ဖြစ်ပါသည်။"
        kb = [[InlineKeyboardButton(f"💸 ဝယ်မည် ({movie[3]} Ks)", callback_data=f"buy_single_{m_id}")],
              [InlineKeyboardButton("👑 VIP ဝင်မည်", callback_data="buy_vip_basic")]]
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=text, duration=180, protect_content=True, reply_markup=InlineKeyboardMarkup(kb))

# ==========================================
# ADMIN MOVIE ADD
# ==========================================
async def start_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("🎬 Video ပို့ပါ။ Caption တွင် `Title | Price` ရေးပါ။")
    return ADD_MOVIE_STATE

async def handle_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video: return ADD_MOVIE_STATE
    try:
        title, price = [x.strip() for x in update.message.caption.split("|")]
        fid = update.message.video.file_id
        db_query("INSERT INTO movies (file_id, title, price, added_date) VALUES (?,?,?,?)", (fid, title, int(price), datetime.now().strftime("%Y-%m-%d")))
        m_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
        await update.message.reply_text(f"✅ {title} ထည့်ပြီးပါပြီ။ User များထံ စာပို့နေသည်။")
        asyncio.create_task(broadcast_new_movie(context, title, m_id))
    except:
        await update.message.reply_text("❌ ပုံစံမှားနေသည်။ `Title | Price` ဟု Caption ရေးပါ။")
        return ADD_MOVIE_STATE
    return ConversationHandler.END

# ==========================================
# PAYMENT HANDLING
# ==========================================
async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    d = query.data.split("_")
    if d[1] == "vip":
        context.user_data['buy_type'], context.user_data['expected_amount'] = f"vip_{d[2]}", (PRICE_BASIC if d[2]=='basic' else PRICE_PRO)
    else:
        movie = db_query("SELECT price FROM movies WHERE id=?", (int(d[2]),), fetchone=True)
        context.user_data['buy_type'], context.user_data['expected_amount'] = f"single_{d[2]}", movie[0]
    
    kb = [[InlineKeyboardButton("KPay", callback_data="pay_kpay"), InlineKeyboardButton("Wave", callback_data="pay_wave")], [InlineKeyboardButton("Cancel", callback_data="start_back")]]
    await query.message.reply_text("💳 ငွေပေးချေမည့်နည်းလမ်း ရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def show_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.split("_")[-1]
    pay = db_query("SELECT phone, name, qr_file_id FROM payment_settings WHERE pay_type=?", (method,), fetchone=True)
    text = f"💸 **{method.upper()}**\n💰 Amount: {context.user_data['expected_amount']} Ks\n📞 `{pay[0]}`\n👤 {pay[1]}\n\nပြေစာ ပို့ပေးပါ။"
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_pay")]]
    if pay[2]: await context.bot.send_photo(chat_id=query.from_user.id, photo=pay[2], caption=text, reply_markup=InlineKeyboardMarkup(kb))
    else: await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: return UPLOAD_RECEIPT
    f = await update.message.photo[-1].get_file()
    res = await verify_receipt_with_ai(await f.download_as_bytearray(), context.user_data['expected_amount'])
    if res.get('is_valid'):
        uid, btype = update.effective_user.id, context.user_data['buy_type']
        if btype.startswith("vip"):
            db_query("UPDATE users SET is_vip=? WHERE user_id=?", (1 if "basic" in btype else 2, uid))
        else:
            db_query("INSERT OR IGNORE INTO purchases VALUES (?,?)", (uid, int(btype.split("_")[1])))
        await update.message.reply_text("✅ ဝယ်ယူမှု အောင်မြင်ပါသည်။")
    else: await update.message.reply_text("❌ ပြေစာ မမှန်ပါ။")
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).defaults(Defaults(protect_content=True)).build()

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add_movie", start_add_movie)],
        states={ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, handle_movie_upload)]},
        fallbacks=[CommandHandler("start", start)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(show_pay_info, pattern="^pay_")],
        states={UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, confirm_receipt), CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^cancel_pay$")]},
        fallbacks=[CommandHandler("start", start)]
    ))
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(start_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
