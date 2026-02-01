import logging
import sqlite3
import json
import requests
import os
import base64
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
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
ADD_MOVIE_STATE = 2

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# HEALTH CHECK SERVER (For Render)
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
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, joined_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, movie_id INTEGER, PRIMARY KEY (user_id, movie_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
        
        payments = [('kpay', '09960202983', 'Sai Zaw Ye Lwin', ''), ('wave', '09960202983', 'Sai Zaw Ye Lwin', ''), ('ayapay', 'None', 'None', ''), ('cbpay', 'None', 'None', '')]
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
# UI HELPER
# ==========================================
def get_start_info():
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "**လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:**\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Video Record ဖမ်းခြင်း၊ ဖုန်းထဲသို့ Save လုပ်ခြင်း နှင့် Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ တစ်ကားချင်း ဝယ်ယူထားသော ဇာတ်ကားများကို ဤ Channel အတွင်း ရာသက်ပန် ပြန်လည်ကြည့်ရှုနိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        "1️⃣ **Basic VIP (10000 Ks) - 1 Month Access**\n"
        " - တစ်လအတွင်း တင်သမျှကားများကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n"
        " - တစ်လပြည့်ပြီးနောက် တင်သော ကားအသစ်များကို ကြည့်ရှုခွင့်ရမည်မဟုတ်ပါ။\n\n"
        "2️⃣ **Pro VIP (30000 Ks) - Lifetime Access**\n"
        " - Channel တွင် တင်သမျှ ကားအဟောင်း/အသစ် အားလုံးကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n\n"
        "💡 **ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။**"
    )
    kb = [
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="buy_vip_basic")],
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=CHANNEL_URL)],
        [InlineKeyboardButton("Back", callback_data="start_back")]
    ]
    return text, InlineKeyboardMarkup(kb)

# ==========================================
# AUTO BACK HANDLER
# ==========================================
async def back_to_start_auto(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        text, markup = get_start_info()
        # Photo message ဖြစ်ဖြစ် Text message ဖြစ်ဖြစ် Start menu အဖြစ် ပြန်ပြောင်းပေးမည်
        try:
            # Photo caption ကို အရင်ပြင်ရန် ကြိုးစားသည်
            await context.bot.edit_message_caption(
                chat_id=job.chat_id,
                message_id=job.data,
                caption=text,
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            # Photo မဟုတ်ပါက Text ကို ပြင်သည်
            await context.bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=job.data,
                text=text,
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Failed to auto back to start: {e}")

# ==========================================
# AI RECEIPT VERIFICATION
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

# ==========================================
# BOT HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", (user.id, user.username, user.full_name, today))

    text, markup = get_start_info()
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    d = query.data.split("_")
    
    if d[1] == "vip":
        context.user_data['buy_type'] = f"vip_{d[2]}"
        context.user_data['expected_amount'] = PRICE_BASIC if d[2] == 'basic' else PRICE_PRO
    else:
        m_id = int(d[2])
        movie = db_query("SELECT price FROM movies WHERE id=?", (m_id,), fetchone=True)
        context.user_data['buy_type'] = f"single_{m_id}"
        context.user_data['expected_amount'] = movie[0]
    
    kb = [
        [InlineKeyboardButton("🟦 KBZPay", callback_data="pay_kpay"), InlineKeyboardButton("🟧 WavePay", callback_data="pay_wave")],
        [InlineKeyboardButton("🟥 AYA Pay", callback_data="pay_ayapay"), InlineKeyboardButton("🟦 CB Pay", callback_data="pay_cbpay")],
        [InlineKeyboardButton("Back", callback_data="start_back")]
    ]
    await query.message.edit_text("💳 **ငွေပေးချေမည့်နည်းလမ်းကို ရွေးချယ်ပေးပါ**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def show_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.split("_")[-1]
    pay = db_query("SELECT phone, name, qr_file_id FROM payment_settings WHERE pay_type=?", (method,), fetchone=True)
    expected = context.user_data['expected_amount']
    
    text = (f"💸 **{method.upper()} ဖြင့် ငွေပေးချေခြင်း**\n\n"
            f"💰 ကျသင့်ငွေ: **{expected} MMK**\n"
            f"📞 Phone: `{pay[0]}`\n"
            f"👤 Name: **{pay[1]}**\n\n"
            "⚠️ **အရေးကြီးသတိပေးချက်**\n"
            f"ငွေပေးချေရာတွင် ကျသင့်ငွေ **{expected} ကျပ်** ကို တစ်ကြိမ်တည်း အပြည့်လွှဲရပါမည်။ "
            "ခွဲလွှဲပါက ငွေပြန်အမ်းမည်မဟုတ်သလို ဇာတ်ကားလည်း ကြည့်ရှုခွင့်ရမည်မဟုတ်ပါ။\n\n"
            "⏳ **၃ မိနစ်အတွင်း** ပြေစာ ပို့ပေးရပါမည်။ ၃ မိနစ်ပြည့်ပါက Start Menu သို့ အလိုအလျောက် ပြန်သွားပါမည်။")
    
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_pay")]]
    
    if pay[2]:
        msg = await context.bot.send_photo(chat_id=query.from_user.id, photo=pay[2], caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
    else:
        msg = await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
    
    # ၃ မိနစ် (စက္ကန့် ၁၈၀) ပြည့်လျှင် Start Menu သို့ ပြန်သွားရန် Job သတ်မှတ်ခြင်း
    context.job_queue.run_once(back_to_start_auto, 180, chat_id=query.from_user.id, data=msg.message_id)
    
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: return UPLOAD_RECEIPT
    f = await update.message.photo[-1].get_file()
    expected = context.user_data['expected_amount']
    
    load = await update.message.reply_text("🔍 ပြေစာအား AI ဖြင့် စစ်ဆေးနေသည်...")
    res = await verify_receipt_with_ai(await f.download_as_bytearray(), expected)
    
    if res.get('is_valid'):
        uid, btype = update.effective_user.id, context.user_data['buy_type']
        if btype.startswith("vip"):
            db_query("UPDATE users SET is_vip=? WHERE user_id=?", (1 if "basic" in btype else 2, uid))
        else:
            db_query("INSERT OR IGNORE INTO purchases VALUES (?,?)", (uid, int(btype.split("_")[1])))
        await load.edit_text("✅ ဝယ်ယူမှု အောင်မြင်ပါသည်။ ဇာတ်ကားများကို စတင်ကြည့်ရှုနိုင်ပါပြီ။")
    else: 
        await load.edit_text("❌ ပြေစာ မမှန်ကန်ပါ။ (သို့မဟုတ်) ငွေပမာဏ မပြည့်မီပါ။ ကျေးဇူးပြု၍ ပြန်လည်စစ်ဆေးပေးပါ။")
    
    return ConversationHandler.END

# ==========================================
# MOVIE MENU & VIEWING
# ==========================================
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
    
    user_info = db_query("SELECT is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    is_vip = user_info[0] if user_info else 0
    has_purchased = db_query("SELECT 1 FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip >= 1 or has_purchased:
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}", protect_content=True)
    else:
        text = f"🎬 **{movie[2]} (Preview)**\n\n၃ မိနစ်စာ နမူနာသာ ဖြစ်ပါသည်။ အပြည့်အစုံကြည့်ရန် ဝယ်ယူပါ။"
        kb = [[InlineKeyboardButton(f"💸 ဝယ်မည် ({movie[3]} Ks)", callback_data=f"buy_single_{m_id}")],
              [InlineKeyboardButton("👑 VIP ဝင်မည်", callback_data="buy_vip_basic")]]
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=text, duration=180, protect_content=True, reply_markup=InlineKeyboardMarkup(kb))

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).defaults(Defaults(protect_content=True)).build()

    pay_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_pay_info, pattern="^pay_")],
        states={
            UPLOAD_RECEIPT: [
                MessageHandler(filters.PHOTO, confirm_receipt), 
                CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^cancel_pay$")
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(pay_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(start_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
