import logging
import sqlite3
import threading
import re
import os
import io
import time
import asyncio
from datetime import datetime
from typing import Final
from http.server import BaseHTTPRequestHandler, HTTPServer

# Telegram Bot Library
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
    ConversationHandler
)
from telegram.constants import ParseMode

# Optional: Graph library (If you use the dashboard feature)
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN: Final = "8515688348:AAEFbdCJ6HHR6p4cCgzvUvcRDr7i7u-sL6U" 
ADMIN_ID: Final = 6445257462              
CHANNEL_ID: Final = "@ZanchannelMM"       
DB_NAME: Final = "movie_database_pro.db"

# States
ADD_MOVIE_STATE = 1
WAIT_RECEIPT = 2

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# RENDER HEALTH CHECK SERVER
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args): return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"🌍 Health check server on port {port}")
    httpd.serve_forever()

# ==========================================
# DATABASE
# ==========================================
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

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, vip_type TEXT DEFAULT 'NONE', joined_date DATETIME)''')
    db_query('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, channel_msg_id INTEGER)''')
    db_query('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, amount INTEGER, pay_method TEXT, status TEXT DEFAULT 'PENDING', date DATETIME)''')

# ==========================================
# GRAPH GENERATION (FOR ADMIN)
# ==========================================
def create_sales_graph():
    now = datetime.now()
    start_date = now.replace(day=1, hour=0, minute=0, second=0)
    data = db_query("SELECT strftime('%d', date) as day, SUM(amount) FROM transactions WHERE status='SUCCESS' AND date >= ? GROUP BY day", (start_date,))
    days = [int(row[0]) for row in data] if data else [now.day]
    amounts = [row[1] for row in data] if data else [0]
    plt.figure(figsize=(8, 4))
    plt.plot(days, amounts, marker='o', color='#2ecc71')
    plt.title(f"Revenue - {now.strftime('%B %Y')}")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# ==========================================
# USER FLOW (SCREENSHOT MATCHED)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", (user.id, user.username, user.full_name, datetime.now()))

    if args and args[0].startswith("buy_"):
        try:
            movie_id = int(args[0].split("_")[1])
            movie = db_query("SELECT title, price FROM movies WHERE id=?", (movie_id,), fetchone=True)
            if movie:
                await show_payment_options(update, movie[0], movie[1])
                return
        except: pass

    # Screenshot မူလပုံစံအတိုင်း စာသားများ
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Video Record ဖမ်းခြင်း၊ ဖုန်းထဲသို့ Save လုပ်ခြင်း နှင့် Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ တစ်ကားချင်း ဝယ်ယူထားသော ဇာတ်ကားများကို ဤ Channel အတွင်း ရာသက်ပန် ပြန်ကြည့်နိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        "1️⃣ Basic VIP (10000 Ks) - 1 Month Access\n"
        "   - တစ်လအတွင်း တင်သမျှကားများကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n"
        "2️⃣ Pro VIP (30000 Ks) - Lifetime Access\n"
        "   - Channel တွင် တင်သမျှ ကားဟောင်း/ကားသစ် အားလုံးကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n\n"
        "💡 ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။"
    )
    
    kb = [
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="pay_select_BasicVIP_10000")],
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="pay_select_ProVIP_30000")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမိန်း", callback_data="movie_list")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url="https://t.me/ZanchannelMM")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_start")]
    ]
    
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def show_payment_options(update: Update, item_name, amount):
    user_id = update.effective_user.id
    db_query("INSERT INTO transactions (user_id, item_name, amount, date) VALUES (?,?,?,?)", (user_id, item_name, amount, datetime.now()))
    tx_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
    
    text = f"💳 **ငွေပေးချေရန် ရွေးချယ်ပါ**\n\n📝 ဝယ်ယူမည့်အရာ: **{item_name}**\n💰 ကျသင့်ငွေ: **{amount} MMK**"
    kb = [
        [InlineKeyboardButton("KBZPay", callback_data=f"pay_KBZ_{tx_id}"), InlineKeyboardButton("WavePay", callback_data=f"pay_Wave_{tx_id}")],
        [InlineKeyboardButton("AYA Pay", callback_data=f"pay_AYA_{tx_id}"), InlineKeyboardButton("CB Pay", callback_data=f"pay_CB_{tx_id}")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="refresh_start")]
    ]
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, method, tx_id = query.data.split("_")
    context.user_data['current_tx_id'] = tx_id
    context.user_data['pay_method'] = method
    
    # Screenshot မူလပုံစံအတိုင်း
    text = (
        f"✅ **{method} ဖြင့် ငွေလွှဲရန်**\n"
        f"ဖုန်းနံပါတ်: `09960202983` (Sai Zaw Ye Lwin)\n\n"
        f"❗️ ငွေလွှဲပြီးပါက **Screenshot (ပြေစာ)** ပို့ပေးပါ။"
    )
    await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    return WAIT_RECEIPT

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ပြေစာဓာတ်ပုံ ပို့ပေးပါ။")
        return WAIT_RECEIPT
    
    tx_id = context.user_data.get('current_tx_id')
    method = context.user_data.get('pay_method')
    user = update.effective_user
    
    caption = f"📩 **New Payment**\n👤 {user.full_name}\n💳 {method}\n🆔 TxID: {tx_id}"
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{tx_id}_{user.id}"), 
           InlineKeyboardButton("❌ Scam", callback_data=f"scam_{tx_id}_{user.id}")]]
    
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ ပြေစာပို့လိုက်ပါပြီ။ Admin စစ်ဆေးပြီးပါက ကားကြည့်ခွင့် ရပါမည်။")
    return ConversationHandler.END

# ==========================================
# ADMIN DECISION
# ==========================================
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, tx_id, user_id = query.data.split("_")
    
    if action == "approve":
        tx = db_query("SELECT item_name FROM transactions WHERE id=?", (tx_id,), fetchone=True)
        if tx:
            item = tx[0]
            db_query("UPDATE transactions SET status='SUCCESS' WHERE id=?", (tx_id,))
            if "VIP" in item:
                db_query("UPDATE users SET vip_type=? WHERE user_id=?", (item, user_id))
            await context.bot.send_message(user_id, f"🎉 **{item}** ဝယ်ယူမှု အောင်မြင်ပါသည်။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n✅ APPROVED")
    else:
        await context.bot.send_message(user_id, "❌ သင်၏ပြေစာ မမှန်ကန်ပါ။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n❌ REJECTED")

# ==========================================
# ADMIN DASHBOARD
# ==========================================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    today = datetime.now().strftime("%Y-%m-%d")
    rev = db_query("SELECT SUM(amount) FROM transactions WHERE status='SUCCESS' AND date LIKE ?", (f"{today}%",), fetchone=True)[0] or 0
    text = f"📊 **Dashboard**\nToday Rev: {rev:,} MMK"
    graph = create_sales_graph()
    kb = [[InlineKeyboardButton("➕ ဇာတ်ကားတင်ရန်", callback_data="admin_upload_start")]]
    await update.message.reply_photo(photo=graph, caption=text, reply_markup=InlineKeyboardMarkup(kb))

# ==========================================
# MOVIE UPLOAD
# ==========================================
async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.video or not msg.caption: return ADD_MOVIE_STATE
    try:
        lines = msg.caption.split("\n")
        price = int(re.search(r'#(\d+)', lines[0]).group(1))
        title = lines[1]
        db_query("INSERT INTO movies (file_id, title, price) VALUES (?,?,?)", (msg.video.file_id, title, price))
        movie_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
        bot_user = (await context.bot.get_me()).username
        kb = [[InlineKeyboardButton("💳 ဝယ်ယူရန်", url=f"https://t.me/{bot_user}?start=buy_{movie_id}")]]
        await context.bot.send_video(chat_id=CHANNEL_ID, video=msg.video.file_id, caption=f"🎬 {title}\n💰 {price} MMK", reply_markup=InlineKeyboardMarkup(kb))
        await msg.reply_text("✅ တင်ပြီးပါပြီ။")
    except: await msg.reply_text("❌ Format အမှား")
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: (u.callback_query.answer(), u.callback_query.message.reply_text("ဗီဒီယိုပို့ပါ"))[1], pattern="^admin_upload_start$")],
        states={ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, save_movie)]},
        fallbacks=[CommandHandler("start", start)]
    )

    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_handler, pattern="^pay_(KBZ|Wave|AYA|CB)_")],
        states={WAIT_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("saizawyelwin", admin_dashboard))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(approve|scam)_"))
    app.add_handler(upload_conv)
    app.add_handler(pay_conv)
    app.add_handler(CallbackQueryHandler(start, pattern="^(refresh_start|pay_select_)"))
    app.add_handler(CommandHandler("start", start))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
