import logging
import sqlite3
import json
import requests
import os
import base64
import asyncio
import threading
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
CHANNEL_ID: Final = "@ZanchannelMM" 
DB_NAME: Final = "movie_database.db"
GEMINI_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk" 

# Pricing
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
# DATABASE INITIALIZATION
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, joined_date DATE, last_active DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATETIME, channel_post_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount INTEGER, movie_id INTEGER, date DATE, is_scam INTEGER DEFAULT 0)''')
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
# UI & CHART HELPERS
# ==========================================
def generate_line_graph(daily_data):
    if not daily_data: return "No data available."
    max_val = max([d[1] for d in daily_data]) if any(d[1] > 0 for d in daily_data) else 1
    graph = "📈 **နေ့စဉ်ဝင်ငွေပြဇယား (MMK)**\n"
    for date, amt in daily_data:
        bar_len = int((amt/max_val)*10)
        bar = "▇" * bar_len if amt > 0 else ""
        graph += f"`{date[-5:]}: {amt:>6} MMK` {bar}\n"
    return graph

def get_start_info():
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "**လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:**\n"
        "⛔️ SS ရိုက်ခြင်း၊ Record ဖမ်းခြင်း၊ Save လုပ်ခြင်း လုံးဝမရပါ။\n"
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

# ==========================================
# AUTO JOBS
# ==========================================
async def auto_delete_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=context.job.data)
    except: pass

async def back_to_start_auto(context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = context.job.chat_id
        msg_id = context.job.data
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        text, markup = get_start_info()
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    except: pass

# ==========================================
# ADMIN: STATISTICS (လချုပ် အော်တို Reset ပါဝင်သည်)
# ==========================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    this_month_start = now.strftime("%Y-%m")
    
    # စာရင်းများတွက်ချက်ခြင်း
    new_users_today = db_query("SELECT COUNT(*) FROM users WHERE joined_date=?", (today,), fetchone=True)[0]
    vip_new_today = db_query("SELECT COUNT(*) FROM transactions WHERE type='vip' AND date=?", (today,), fetchone=True)[0]
    single_new_today = db_query("SELECT COUNT(DISTINCT user_id) FROM transactions WHERE type='single' AND date=?", (today,), fetchone=True)[0]
    scams_today = db_query("SELECT COUNT(*) FROM transactions WHERE is_scam=1 AND date=?", (today,), fetchone=True)[0]
    
    total_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip > 0", fetchone=True)[0]
    total_single = db_query("SELECT COUNT(DISTINCT user_id) FROM transactions WHERE type='single'", fetchone=True)[0]
    
    # ဝင်ငွေ (လချုပ် - ဒီလအတွက်သာပြပါမည်၊ လကုန်ရင် နောက်လအတွက် အော်တို update ဖြစ်သည်)
    monthly_rev = db_query("SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_scam=0", (f"{this_month_start}%",), fetchone=True)[0] or 0
    
    # နေ့စဉ်ပြဇယား (နောက်ဆုံး ၇ ရက်)
    daily_stats = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        amt = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND is_scam=0", (day,), fetchone=True)[0] or 0
        daily_stats.append((day, amt))
    
    graph_text = generate_line_graph(daily_stats)
    
    text = (
        f"📊 **Zan Admin Dashboard ({now.strftime('%B %Y')})**\n\n"
        f"📅 **ယနေ့စာရင်း ({today}):**\n"
        f"• လူသစ်: {new_users_today} ဦး | VIP သစ်: {vip_new_today} ဦး\n"
        f"• ကားဝယ်သူ: {single_new_today} ဦး | Scam: {scams_today} ခု\n\n"
        f"📈 **စုစုပေါင်းစာရင်း:**\n"
        f"• VIP စုစုပေါင်း: {total_vip} ဦး\n"
        f"• တစ်ကားချင်းဝယ်သူစုစုပေါင်း: {total_single} ဦး\n\n"
        f"💰 **ယခုလဝင်ငွေ ({now.strftime('%b')}): {monthly_rev} MMK**\n"
        f"_(လကုန်ပါက နောက်လအတွက် စာရင်းအသစ် အလိုအလျောက်စပါမည်)_\n\n"
        f"{graph_text}"
    )
    
    kb = [[InlineKeyboardButton("➕ ဇာတ်ကားသစ်တင်ရန်", callback_data="admin_add_movie")],
          [InlineKeyboardButton("🏠 Home", callback_data="start_back")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# ==========================================
# ADMIN: MOVIE UPLOAD (Format သစ်)
# ==========================================
async def admin_add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    await query.message.reply_text(
        "🎬 **ဇာတ်ကား Video ကို ပို့ပေးပါ။**\n\n"
        "Caption တွင် အောက်ပါအတိုင်းရေးပါ -\n"
        "`#ဈေးနှုန်း` \n"
        "`ဇာတ်ကားအမည်` \n\n"
        "**ဥပမာ:**\n"
        "`#2000` \n"
        "`မြန်မာကားသစ်ကြီး`"
    )
    return ADD_MOVIE_STATE

async def admin_save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    
    if not update.message.video or not update.message.caption:
        await update.message.reply_text("❌ Video နှင့် Caption (#ဈေးနှုန်း နှင့် အမည်) တွဲပို့ပါ။")
        return ADD_MOVIE_STATE

    status = await update.message.reply_text("⏳ Processing...")
    try:
        lines = update.message.caption.strip().split("\n")
        if len(lines) < 2:
            raise ValueError("Format incorrect")
            
        # ပထမစာကြောင်းက #ဈေးနှုန်း၊ ဒုတိယစာကြောင်းက အမည်
        price_str = lines[0].strip().replace("#", "").replace("Ks", "").replace("MMK", "")
        price = int(price_str)
        title = lines[1].strip()
        file_id = update.message.video.file_id
        
        # 1. Channel Post
        post_text = f"🎬 **ဇာတ်ကားအသစ် တင်လိုက်ပါပြီ**\n\n📝 အမည်: **{title}**\n💰 ဈေးနှုန်း: **{price} MMK**\n\n👇 ကြည့်ရှုရန် Bot သို့ သွားပါ\n@{(await context.bot.get_me()).username}"
        channel_msg = await context.bot.send_video(chat_id=CHANNEL_ID, video=file_id, caption=post_text, parse_mode=ParseMode.MARKDOWN)
        
        # 2. DB Insert
        db_query("INSERT INTO movies (file_id, title, price, added_date, channel_post_id) VALUES (?,?,?,?,?)", 
                 (file_id, title, price, datetime.now(), channel_msg.message_id))
        
        # 3. Schedule Delete
        context.job_queue.run_once(auto_delete_post, AUTO_DELETE_HOURS * 3600, data=channel_msg.message_id)
        
        await status.edit_text(f"✅ **{title}** ကို Channel နှင့် Menu တွင် Update လုပ်ပြီးပါပြီ။")
    except Exception as e:
        logger.error(f"Save error: {e}")
        await status.edit_text("❌ ပုံစံမှားနေပါသည်။ \n\n`#2000` (ပထမစာကြောင်း)\n`ကားအမည်` (ဒုတိယစာကြောင်း) \n\nဟု ရေးပေးပါ။")
    
    return ConversationHandler.END

# ==========================================
# USER & MOVIE MENU
# ==========================================
async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    if not movies:
        return await query.message.edit_text("🎬 **လက်ရှိတွင် ဇာတ်ကားများ မရှိသေးပါ**", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]))
        
    kb = [[InlineKeyboardButton(f"🎬 {m[1]} ({m[2]} Ks)", callback_data=f"view_{m[0]}")] for m in movies]
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ ရှေ့သို့", callback_data=f"movie_menu_{page-1}"))
    if db_query("SELECT 1 FROM movies LIMIT 1 OFFSET ?", (page*6,)): nav.append(InlineKeyboardButton("နောက်သို့ ➡️", callback_data=f"movie_menu_{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("🏠 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date, last_active) VALUES (?,?,?,?,?)", 
             (user.id, user.username, user.full_name, today, today))
    
    text, markup = get_start_info()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).defaults(Defaults(protect_content=True)).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_movie_start, pattern="^admin_add_movie")],
        states={ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, admin_save_movie)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^start_back$")],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", admin_panel))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))

    print("Zan Movie Bot is active...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
