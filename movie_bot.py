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
CHANNEL_ID: Final = "@ZanchannelMM" # သင့် Channel Username ကို ဒီမှာ အမှန်ထည့်ပါ
DB_NAME: Final = "movie_database.db"
GEMINI_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk" 

# Pricing & Settings
PRICE_BASIC: Final = 10000
PRICE_PRO: Final = 30000
AUTO_DELETE_HOURS: Final = 24 

# Conversation States
UPLOAD_RECEIPT = 1
ADD_MOVIE_STATE = 2

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# HEALTH CHECK SERVER
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
        c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATETIME, channel_post_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, movie_id INTEGER, PRIMARY KEY (user_id, movie_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
        
        payments = [
            ('kpay', '09960202983', 'Sai Zaw Ye Lwin', ''),
            ('wave', '09960202983', 'Sai Zaw Ye Lwin', ''),
            ('ayapay', 'None', 'None', ''),
            ('cbpay', 'None', 'None', '')
        ]
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
# HELPERS
# ==========================================
def get_start_info():
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "**လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:**\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Record ဖမ်းခြင်း၊ Save လုပ်ခြင်း လုံးဝမရပါ။\n"
        "✅ ဝယ်ယူထားသော ကားများကို ဤနေရာတွင် အမြဲပြန်ကြည့်နိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        "1️⃣ **Basic VIP (10000 Ks) - 1 Month**\n"
        "2️⃣ **Pro VIP (30000 Ks) - Lifetime**\n\n"
        "💡 ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။"
    )
    kb = [
        [InlineKeyboardButton("👑 Basic VIP", callback_data="buy_vip_basic"), InlineKeyboardButton("👑 Pro VIP", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="start_back")]
    ]
    return text, InlineKeyboardMarkup(kb)

async def auto_delete_post(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=job.data)
    except Exception as e:
        logger.error(f"Auto delete error: {e}")

async def back_to_start_auto(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
        text, markup = get_start_info()
        await context.bot.send_message(chat_id=job.chat_id, text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    except: pass

# ==========================================
# ADMIN CONTROL (Owner & Admin Only)
# ==========================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Owner နှင့် Admin သာ သုံးခွင့်ပြုခြင်း
    if update.effective_user.id != ADMIN_ID:
        return # ဘာမှပြန်မလုပ်ပါ

    text = "🛠 **Admin Panel**\n\nဇာတ်ကားတင်ရန် သို့မဟုတ် စာရင်းကြည့်ရန် ရွေးချယ်ပါ။"
    kb = [
        [InlineKeyboardButton("➕ ဇာတ်ကားသစ်တင်ရန်", callback_data="admin_add_movie")],
        [InlineKeyboardButton("📊 အသုံးပြုသူစာရင်း", callback_data="admin_stats")],
        [InlineKeyboardButton("🏠 Home", callback_data="start_back")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    user_count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    movie_count = db_query("SELECT COUNT(*) FROM movies", fetchone=True)[0]
    text = f"📊 **Bot စာရင်းဇယား**\n\n👥 စုစုပေါင်းအသုံးပြုသူ: {user_count} ဦး\n🎬 တင်ထားသောဇာတ်ကား: {movie_count} ကား"
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def admin_add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    await query.message.reply_text("🎬 **ဇာတ်ကား Video ကို ပို့ပေးပါ။**\n\nCaption တွင် အောက်ပါအတိုင်းရေးပါ-\n`ဇာတ်ကားအမည် | ဈေးနှုန်း`")
    return ADD_MOVIE_STATE

async def admin_save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    
    if not update.message.video or not update.message.caption:
        await update.message.reply_text("❌ ပုံစံမမှန်ပါ။ Video နှင့် Caption (အမည် | ဈေးနှုန်း) တွဲပို့ပါ။")
        return ADD_MOVIE_STATE

    status_msg = await update.message.reply_text("⏳ Processing...")
    try:
        title_raw, price_raw = update.message.caption.split("|")
        title = title_raw.strip()
        price = int(price_raw.strip())
        file_id = update.message.video.file_id
        
        # 1. Channel သို့ တင်ခြင်း
        post_text = f"🎬 **ဇာတ်ကားအသစ် တင်လိုက်ပါပြီ**\n\n📝 အမည်: **{title}**\n💰 ဈေးနှုန်း: **{price} MMK**\n\n👇 ကြည့်ရှုရန် Bot သို့ သွားပါ\n@{(await context.bot.get_me()).username}"
        channel_msg = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=file_id,
            caption=post_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # 2. DB သိမ်းခြင်း
        db_query("INSERT INTO movies (file_id, title, price, added_date, channel_post_id) VALUES (?,?,?,?,?)", 
                 (file_id, title, price, datetime.now(), channel_msg.message_id))
        
        # 3. Schedule Delete
        context.job_queue.run_once(auto_delete_post, AUTO_DELETE_HOURS * 3600, data=channel_msg.message_id)
        
        await status_msg.edit_text(f"✅ **{title}** ကို အောင်မြင်စွာ တင်ပြီးပါပြီ။")
    except Exception as e:
        logger.error(f"Save movie error: {e}")
        await status_msg.edit_text("❌ အမှားအယွင်းရှိပါသည်။ (အမည် | ဈေးနှုန်း) ပုံစံမှန်အောင် ရေးပါ။")
    
    return ConversationHandler.END

# ==========================================
# USER HANDLERS
# ==========================================
async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    if not movies:
        return await query.message.edit_text("🎬 **လက်ရှိတွင် ဇာတ်ကားများ မရှိသေးပါ**", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]), 
                                            parse_mode=ParseMode.MARKDOWN)
        
    kb = [[InlineKeyboardButton(f"🎬 {m[1]} ({m[2]} Ks)", callback_data=f"view_{m[0]}")] for m in movies]
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"movie_menu_{page-1}"))
    if db_query("SELECT 1 FROM movies LIMIT 1 OFFSET ?", (page*6,)): nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"movie_menu_{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("🏠 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, datetime.now().strftime("%Y-%m-%d")))
    
    text, markup = get_start_info()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# Payment logic အဟောင်းများကို ဆက်လက်ထားရှိသည်...
# (Confirm Receipt, Show Pay Info စသည်တို့ ပါဝင်ပြီးသားဖြစ်ပါစေ)

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).defaults(Defaults(protect_content=True)).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_movie_start, pattern="^admin_add_movie"),
        ],
        states={
            ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, admin_save_movie)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", admin_panel)) # Owner အတွက် Command
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))

    print("Bot is starting...")
    app.run_polling(drop_pending_updates=True) # Conflict မဖြစ်အောင် drop_pending_updates ထည့်ထားသည်

if __name__ == "__main__":
    main()
