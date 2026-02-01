import logging
import sqlite3
import threading
import re
import os
import io
import time
import asyncio
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
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

# Matplotlib backend for server (no GUI)
matplotlib.use('Agg')

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN: Final = "8515688348:AAEFbdCJ6HHR6p4cCgzvUvcRDr7i7u-sL6U" 
ADMIN_ID: Final = 6445257462              
CHANNEL_ID: Final = "@ZanchannelMM"       
DB_NAME: Final = "movie_database_pro.db"

# Pricing
PRICE_BASIC_VIP: Final = 10000
PRICE_PRO_VIP: Final = 30000

# States for Conversation
ADD_MOVIE_STATE = 1
WAIT_RECEIPT = 2

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# RENDER WEB SERVER (FIXED PORT BINDING)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")
    
    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"🌍 Health check server started on port {port}")
    httpd.serve_forever()

# ==========================================
# DATABASE SYSTEM
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
    db_query('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        full_name TEXT, 
        vip_type TEXT DEFAULT 'NONE', 
        vip_expiry DATE,
        joined_date DATETIME
    )''')
    
    db_query('''CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        file_id TEXT, 
        title TEXT, 
        price INTEGER, 
        channel_msg_id INTEGER
    )''')
    
    db_query('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        item_name TEXT, 
        amount INTEGER, 
        pay_method TEXT,
        status TEXT DEFAULT 'PENDING',
        date DATETIME
    )''')

# ==========================================
# GRAPH GENERATION
# ==========================================
def create_sales_graph():
    now = datetime.now()
    start_date = now.replace(day=1, hour=0, minute=0, second=0)
    
    data = db_query('''
        SELECT strftime('%d', date) as day, SUM(amount) 
        FROM transactions 
        WHERE status='SUCCESS' AND date >= ? 
        GROUP BY day ORDER BY day
    ''', (start_date,))
    
    days = []
    amounts = []
    
    if data:
        for row in data:
            days.append(int(row[0]))
            amounts.append(row[1])
    else:
        days = [int(now.day)]
        amounts = [0]

    plt.figure(figsize=(10, 5))
    plt.plot(days, amounts, marker='o', linestyle='-', color='#2ecc71', linewidth=2)
    plt.title(f"Revenue Graph - {now.strftime('%B %Y')}", fontsize=14, fontweight='bold')
    plt.xlabel('Day of Month')
    plt.ylabel('Amount (MMK)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(range(1, 32, 2))
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# ==========================================
# ADMIN COMMANDS
# ==========================================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return

    today = datetime.now().strftime("%Y-%m-%d")
    
    vip_count = db_query("SELECT COUNT(*) FROM transactions WHERE item_name LIKE '%VIP%' AND status='SUCCESS' AND date LIKE ?", (f"{today}%",), fetchone=True)[0]
    movie_count = db_query("SELECT COUNT(*) FROM transactions WHERE item_name NOT LIKE '%VIP%' AND status='SUCCESS' AND date LIKE ?", (f"{today}%",), fetchone=True)[0]
    window_shoppers = db_query("SELECT COUNT(*) FROM transactions WHERE status='PENDING' AND date LIKE ?", (f"{today}%",), fetchone=True)[0]
    scam_count = db_query("SELECT COUNT(*) FROM transactions WHERE status='SCAM' AND date LIKE ?", (f"{today}%",), fetchone=True)[0]
    today_rev = db_query("SELECT SUM(amount) FROM transactions WHERE status='SUCCESS' AND date LIKE ?", (f"{today}%",), fetchone=True)[0] or 0
    this_month = datetime.now().strftime("%Y-%m")
    month_rev = db_query("SELECT SUM(amount) FROM transactions WHERE status='SUCCESS' AND date LIKE ?", (f"{this_month}%",), fetchone=True)[0] or 0

    report_text = (
        f"📊 **Zan Movie Admin Dashboard**\n"
        f"📅 Date: `{today}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👑 VIP Members Today: `{vip_count}`\n"
        f"🎬 Movie Sales Today: `{movie_count}`\n"
        f"👀 Window Shoppers: `{window_shoppers}`\n"
        f"⚠️ Scammers Detected: `{scam_count}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Today Revenue: `{today_rev:,.0f} MMK`\n"
        f"📅 Month Revenue: `{month_rev:,.0f} MMK`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Status: Online"
    )

    graph_img = create_sales_graph()
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ဇာတ်ကားတင်ရန်", callback_data="admin_upload_start")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_admin")]
    ])

    if update.callback_query:
        await update.callback_query.message.reply_photo(photo=graph_img, caption=report_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await update.message.reply_photo(photo=graph_img, caption=report_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# ==========================================
# MOVIE UPLOAD
# ==========================================
async def start_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🎬 **Video ဖိုင်ကို Caption နှင့်တကွ ပို့ပေးပါ။**\n\nပုံစံ:\n`#3000` (ဈေးနှုန်း)\n`Movie Title` (ကားနာမည်)")
    return ADD_MOVIE_STATE

async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.video or not msg.caption:
        await msg.reply_text("❌ Video နှင့် Caption လိုအပ်သည်။")
        return ADD_MOVIE_STATE

    try:
        lines = msg.caption.strip().split("\n")
        price_match = re.search(r'#(\d+)', lines[0])
        if not price_match: raise ValueError("Price not found")
        
        price = int(price_match.group(1))
        title = lines[1].strip() if len(lines) > 1 else "Unknown Movie"
        
        db_query("INSERT INTO movies (file_id, title, price) VALUES (?,?,?)", (msg.video.file_id, title, price))
        movie_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
        
        bot_username = (await context.bot.get_me()).username
        deep_link = f"https://t.me/{bot_username}?start=buy_{movie_id}"
        
        kb = [[InlineKeyboardButton("💳 ဝယ်ယူရန် (Click Here)", url=deep_link)]]
        
        caption_text = (
            f"🎬 **{title}**\n\n"
            f"💰 ဈေးနှုန်း: **{price} MMK**\n"
            f"⚠️ ၃ မိနစ်စာ နမူနာ ဖြစ်ပါသည်။ အပြည့်အစုံကြည့်ရန် အောက်ပါ ခလုတ်ကို နှိပ်ပါ။"
        )
        
        sent_msg = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=msg.video.file_id,
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN
        )
        
        db_query("UPDATE movies SET channel_msg_id=? WHERE id=?", (sent_msg.message_id, movie_id))
        await msg.reply_text(f"✅ **{title}** ကို Channel တွင် တင်ပြီးပါပြီ။")
        
    except Exception as e:
        await msg.reply_text(f"❌ Error: {e}\nFormat: #Price\nTitle")
        
    return ConversationHandler.END

# ==========================================
# USER FLOW: BUY & PAYMENT
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user
    
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, datetime.now()))

    if args and args[0].startswith("buy_"):
        try:
            movie_id = int(args[0].split("_")[1])
            movie = db_query("SELECT title, price FROM movies WHERE id=?", (movie_id,), fetchone=True)
            if movie:
                await show_payment_options(update, movie[0], movie[1])
                return
        except:
            pass

    text = (
        "👋 မင်္ဂလာပါ **Zan Movie Bot** မှ ကြိုဆိုပါသည်။\n\n"
        "👑 **VIP Plan များ**\n"
        "1️⃣ Basic VIP (1 Month) - 10,000 Ks\n"
        "2️⃣ Pro VIP (Lifetime) - 30,000 Ks\n\n"
        "🎬 တစ်ကားချင်းလည်း ဝယ်ယူကြည့်ရှုနိုင်ပါသည်။"
    )
    kb = [
        [InlineKeyboardButton("👑 Buy Basic VIP", callback_data="pay_select_BasicVIP_10000")],
        [InlineKeyboardButton("👑 Buy Pro VIP", callback_data="pay_select_ProVIP_30000")],
        [InlineKeyboardButton("🆘 Admin ဆက်သွယ်ရန်", url="https://t.me/Saizawyelwin")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def show_payment_options(update: Update, item_name, amount):
    user_id = update.effective_user.id
    db_query("INSERT INTO transactions (user_id, item_name, amount, date) VALUES (?,?,?,?)", 
             (user_id, item_name, amount, datetime.now()))
    
    tx_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
    text = f"💳 **ငွေပေးချေရန် ရွေးချယ်ပါ**\n\n📝 ဝယ်ယူမည့်အရာ: **{item_name}**\n💰 ကျသင့်ငွေ: **{amount} MMK**"
    
    kb = [
        [InlineKeyboardButton("KBZPay", callback_data=f"pay_KBZ_{tx_id}"), InlineKeyboardButton("WavePay", callback_data=f"pay_Wave_{tx_id}")],
        [InlineKeyboardButton("AYA Pay", callback_data=f"pay_AYA_{tx_id}"), InlineKeyboardButton("CB Pay", callback_data=f"pay_CB_{tx_id}")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="cancel_pay")]
    ]
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "cancel_pay":
        await query.message.edit_text("❌ ဝယ်ယူမှုကို ပယ်ဖျက်လိုက်ပါသည်။")
        return

    if data.startswith("pay_select_"):
        _, _, item, price = data.split("_")
        await show_payment_options(update, item, int(price))
        return

    _, method, tx_id = data.split("_")
    context.user_data['current_tx_id'] = tx_id
    context.user_data['pay_method'] = method
    
    payment_info = {
        "KBZ": "09960202983 (Sai Zaw Ye Lwin)",
        "Wave": "09960202983 (Sai Zaw Ye Lwin)",
        "AYA": "09XXXXX (Name)",
        "CB": "00XXXXX (Name)"
    }
    
    text = (
        f"✅ **{method} ဖြင့် ငွေလွှဲရန်**\n"
        f"ဖုန်းနံပါတ်: `{payment_info.get(method, 'N/A')}`\n\n"
        f"❗️ ငွေလွှဲပြီးပါက **Screenshot (ပြေစာ)** ပို့ပေးပါ။"
    )
    await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    return WAIT_RECEIPT

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။")
        return WAIT_RECEIPT
    
    tx_id = context.user_data.get('current_tx_id')
    method = context.user_data.get('pay_method')
    user = update.effective_user
    
    if not tx_id:
        await update.message.reply_text("Session expired. ပြန်လည်စမ်းပါ။")
        return ConversationHandler.END

    caption = (
        f"📩 **New Payment Verification**\n"
        f"👤 User: {user.full_name} (ID: `{user.id}`)\n"
        f"💳 Method: {method}\n"
        f"🆔 TxID: {tx_id}"
    )
    
    kb = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{tx_id}_{user.id}")],
        [InlineKeyboardButton("⚠️ Scam / Fake", callback_data=f"scam_{tx_id}_{user.id}")]
    ]
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )
    
    await update.message.reply_text("✅ ပြေစာ လက်ခံရရှိပါသည်။ Admin စစ်ဆေးပြီးပါက ကားကြည့်ခွင့် ရရှိပါမည်။")
    return ConversationHandler.END

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, tx_id, user_id = query.data.split("_")
    
    if action == "approve":
        tx = db_query("SELECT item_name, amount FROM transactions WHERE id=?", (tx_id,), fetchone=True)
        if tx:
            item_name = tx[0]
            db_query("UPDATE transactions SET status='SUCCESS', pay_method=? WHERE id=?", ("Paid", tx_id))
            try:
                if "VIP" in item_name:
                    db_query("UPDATE users SET vip_type=? WHERE user_id=?", (item_name, user_id))
                    await context.bot.send_message(user_id, f"🎉 ဂုဏ်ယူပါသည်။ **{item_name}** အောင်မြင်ပါသည်။")
                else:
                    movie = db_query("SELECT file_id, title FROM movies WHERE title=?", (item_name,), fetchone=True)
                    if movie:
                        await context.bot.send_video(user_id, video=movie[0], caption=f"🎬 **{movie[1]}**\nကျေးဇူးတင်ပါသည်။")
            except Exception as e:
                logger.error(f"Failed to send to user: {e}")

            await query.message.edit_caption(caption=query.message.caption + "\n\n✅ **APPROVED**")

    elif action == "scam":
        db_query("UPDATE transactions SET status='SCAM' WHERE id=?", (tx_id,))
        try:
            await context.bot.send_message(int(user_id), "❌ သင်၏ ငွေလွှဲပြေစာ မမှန်ကန်ပါ။ (Rejected)")
        except: pass
        await query.message.edit_caption(caption=query.message.caption + "\n\n⚠️ **MARKED AS SCAM**")

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    init_db()
    
    # Render Port Binding
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_upload, pattern="^admin_upload_start$")],
        states={ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, save_movie)]},
        fallbacks=[CommandHandler("start", start)]
    )

    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_handler, pattern="^pay_")],
        states={WAIT_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("saizawyelwin", admin_dashboard))
    app.add_handler(CallbackQueryHandler(admin_dashboard, pattern="^refresh_admin$"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(approve|scam)_"))
    app.add_handler(upload_conv)
    app.add_handler(pay_conv)
    app.add_handler(CallbackQueryHandler(payment_handler, pattern="^pay_select_"))
    app.add_handler(CommandHandler("start", start))
    
    logger.info("🤖 Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
