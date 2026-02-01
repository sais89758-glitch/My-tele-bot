import logging
import sqlite3
import threading
import re
import os
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
    ConversationHandler
)
from telegram.constants import ParseMode

# ==========================================
# CONFIGURATION
# ==========================================
# Render သို့မဟုတ် Server တွင် run ပါက Environment Variable ထဲတွင် 'BOT_TOKEN' ကို ထည့်သွင်းပါ။
# Local တွင် run လိုပါက ဒုတိယ parameter နေရာတွင် Token အသစ်ကို ထည့်သွင်းပါ။
# ယခင် Token မှာ Invalid ဖြစ်နေသဖြင့် အသစ်ပြန်ထည့်ရန် လိုအပ်ပါသည်။
BOT_TOKEN: Final = os.getenv("8515688348:AAEFbdCJ6HHR6p4cCgzvUvcRDr7i7u-sL6U")

ADMIN_ID: Final = 6445257462              
CHANNEL_ID: Final = "@ZanchannelMM" 
DB_NAME: Final = "movie_database.db"

# Pricing Defaults
PRICE_BASIC_VIP: Final = 10000
PRICE_PRO_VIP: Final = 30000

# States for ConversationHandler
ADD_MOVIE_STATE = 2
UPLOAD_RECEIPT_STATE = 1

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

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
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, joined_date DATE, last_active DATE)''')
    db_query('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATETIME, channel_post_id INTEGER)''')
    db_query('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount INTEGER, movie_id INTEGER, date DATE, is_scam INTEGER DEFAULT 0)''')
    db_query('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
    
    payments = [('kpay', '09960202983', 'Sai Zaw Ye Lwin', ''), ('wave', '09960202983', 'Sai Zaw Ye Lwin', ''), ('ayapay', '09960202983', 'Sai Zaw Ye Lwin', ''), ('cbpay', '09960202983', 'Sai Zaw Ye Lwin', '')]
    for p in payments:
        db_query("INSERT OR IGNORE INTO payment_settings VALUES (?,?,?,?)", p)

# ==========================================
# HELPERS & UI
# ==========================================
def get_start_info():
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Video Record ဖမ်းခြင်း၊ ဖုန်းထဲသို့ Save လုပ်ခြင်း နှင့် Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ တစ်ကားချင်း ဝယ်ယူထားသော ဇာတ်ကားများကို ဤ Channel အတွင်း ရာသက်ပန် ပြန်ကြည့်နိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        "1️⃣ **Basic VIP (10000 Ks) - 1 Month Access**\n"
        "   - တစ်လအတွင်း တင်သမျှကားများကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n"
        "2️⃣ **Pro VIP (30000 Ks) - Lifetime Access**\n"
        "   - Channel တွင် တင်သမျှ ကားဟောင်း/အသစ် အားလုံးကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n\n"
        "💡 ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။"
    )
    kb = [
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="buy_vip_basic")],
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားmenu", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="start_back")]
    ]
    return text, InlineKeyboardMarkup(kb)

def generate_line_graph(daily_data):
    if not daily_data: return "No data."
    max_val = max([d[1] for d in daily_data]) if any(d[1] > 0 for d in daily_data) else 1
    graph = "📊 **နေ့စဉ်ဝင်ငွေပြဇယား**\n"
    for date, amt in daily_data:
        bar_len = int((amt/max_val)*10)
        bar = "▇" * bar_len if amt > 0 else ""
        graph += f"`{date[-5:]}: {amt:>6} Ks` {bar}\n"
    return graph

# ==========================================
# ADMIN: MOVIE UPLOAD
# ==========================================
# ဒီ Function ကို အသစ်ထည့်လိုက်ပါတယ် (State အပြောင်းအလဲလုပ်ဖို့)
async def start_add_movie_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        if update.effective_user.id != ADMIN_ID:
            return ConversationHandler.END
        await query.message.reply_text("🎬 **Video ဖိုင်ကို အရင်ပို့ပါ**\n\nပြီးလျှင် Caption တွင်:\n`#1000` (ဈေးနှုန်း)\n`ဇာတ်ကားအမည်`\nဟု ရေးသားပေးပို့ပါ။")
    return ADD_MOVIE_STATE

async def admin_save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    if not update.message.video or not update.message.caption:
        await update.message.reply_text("❌ Video နှင့် Caption ကို ပုံစံတကျ တွဲပို့ပါ။")
        return ADD_MOVIE_STATE

    try:
        lines = update.message.caption.strip().split("\n")
        # ဈေးနှုန်းရှာဖွေခြင်း logic ကို ပိုကောင်းအောင် ပြင်ထားပါတယ်
        price_match = re.search(r'#(\d+)', lines[0])
        
        if not price_match or len(lines) < 2:
            raise ValueError("Format Error")
            
        price = int(price_match.group(1))
        title = lines[1].strip()
        file_id = update.message.video.file_id
        
        # 1. Post to Channel with Buy Button
        bot_username = (await context.bot.get_me()).username
        kb = [[InlineKeyboardButton("💳 ဝယ်ယူရန်", url=f"https://t.me/{bot_username}?start=buy_{title.replace(' ', '_')}")] ]
        post_text = f"🎬 **ဇာတ်ကားအသစ် တင်လိုက်ပါပြီ**\n\n📝 အမည်: **{title}**\n💰 ဈေးနှုန်း: **{price} MMK**\n\n⚠️ နမူနာ ၃ မိနစ်သာ ကြည့်နိုင်ပါသည်။ အပြည့်အစုံကြည့်ရန် ဝယ်ယူပါ။"
        
        # Note: 'protect_content=True' for security
        channel_msg = await context.bot.send_video(
            chat_id=CHANNEL_ID, 
            video=file_id, 
            caption=post_text, 
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN,
            protect_content=True 
        )
        
        db_query("INSERT INTO movies (file_id, title, price, added_date, channel_post_id) VALUES (?,?,?,?,?)", 
                 (file_id, title, price, datetime.now(), channel_msg.message_id))
        
        await update.message.reply_text(f"✅ **{title}** ကို Update လုပ်ပြီးပါပြီ။")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ ပုံစံမှားနေပါသည်။\n\n`#1000` (ပထမစာကြောင်း)\n`ကားအမည်` (ဒုတိယစာကြောင်း)\nVideo Caption တွင် ထည့်ရေးပါ။")
        return ADD_MOVIE_STATE
    
    return ConversationHandler.END

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Upload လုပ်ခြင်းကို ပယ်ဖျက်လိုက်ပါပြီ။")
    return ConversationHandler.END

# ==========================================
# PAYMENT SYSTEM (Unified)
# ==========================================
async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, amount, item_name, is_vip=False):
    kb = [
        [InlineKeyboardButton("🟦 KBZPay", callback_data=f"pay_kpay_{amount}_{item_name}"), InlineKeyboardButton("🟧 WavePay", callback_data=f"pay_wave_{amount}_{item_name}")],
        [InlineKeyboardButton("🟥 AYA Pay", callback_data=f"pay_ayapay_{amount}_{item_name}"), InlineKeyboardButton("🟦 CB Pay", callback_data=f"pay_cbpay_{amount}_{item_name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="start_back")]
    ]
    text = f"💳 **ငွေပေးချေမည့်နည်းလမ်းကို ရွေးချယ်ပေးပါ**\n\n💰 ကျသင့်ငွေ: **{amount} MMK**\n📝 အကြောင်းအရာ: **{item_name}**"
    
    if update.callback_query:
        await update.callback_query.answer() # Button loading ရပ်အောင် ထည့်ပေးရသည်
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    # Format: pay_method_amount_item
    method, amount, item = data[1], data[2], data[3]
    
    settings = db_query("SELECT phone, name, qr_file_id FROM payment_settings WHERE pay_type=?", (method,), fetchone=True)
    
    if not settings:
        await query.message.reply_text("Payment settings not found.")
        return

    text = (
        f"💸 **{method.upper()} ဖြင့် ငွေပေးချေခြင်း**\n\n"
        f"💰 ကျသင့်ငွေ: **{amount} MMK**\n"
        f"📞 ဖုန်းနံပါတ်: `{settings[0]}`\n"
        f"👤 အမည်: **{settings[1]}**\n\n"
        f"⚠️ **အရေးကြီးသတိပေးချက်များ**\n"
        f"၁။ ငွေလွှဲရာတွင် Note (မှတ်ချက်) နေရာ၌ **Channel ဝင်ရန်/ဇာတ်ကားဝယ်ရန်/ဇာတ်ကားကြည့်ရန်** စသည့် Channel/ဇာတ်ကားနှင့်ပတ်သက်သော စာများ လုံးဝ(လုံးဝ) မရေးပါနှင့်။\n"
        f"၂။ **Note တွင် ရေးမိပါက ငွေပြန်အမ်းမည်မဟုတ်သလို ဇာတ်ကားလည်း ရမည်မဟုတ်ပါ။**\n"
        f"၃။ ငွေကို တစ်ကြိမ်တည်းဖြင့် **အပြတ်အသတ်** လွှဲပေးရပါမည်။\n"
        f"၄။ **ငွေခွဲလွှဲခြင်း လုံးဝ(လုံးဝ) မပြုလုပ်ရပါ။**\n"
        f"၅။ ငွေလွှဲပြီးပါက ပြေစာ (Screenshot) ကို **၃ မိနစ်အတွင်း** ပေးပို့ရပါမည်။\n\n"
        f"💡 **အောက်ပါ Button ကိုနှိပ်၍ Screenshot ပို့ပေးပါ။**"
    )
    kb = [
        [InlineKeyboardButton("📸 ပြေစာပေးပို့ရန်", callback_data=f"upload_receipt_{item}")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="start_back")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# ပြေစာတင်ရန် Button အတွက် Handler
async def request_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_name = query.data.replace("upload_receipt_", "")
    await query.message.reply_text(
        f"📝 **{item_name}** အတွက် ငွေလွှဲ Screenshot ကို ယခု Chat Box သို့ ပေးပို့ပေးပါ။\n\n(Admin မှ စစ်ဆေးပြီးပါက Reply ပြန်ပါလိမ့်မည်။)"
    )
    # ဤနေရာတွင် User ထံမှ ပုံလက်ခံမည့် Logic ဆက်ရေးနိုင်သည်

# ==========================================
# USER ACTIONS
# ==========================================
async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.split("_")[-1])
    except:
        page = 1
        
    movies = db_query("SELECT id, title, price, channel_post_id FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    if not movies:
        return await query.message.edit_text("🎬 **လက်ရှိတွင် ဇာတ်ကားများ မရှိသေးပါ**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]), parse_mode=ParseMode.MARKDOWN)
        
    kb = [[InlineKeyboardButton(f"🎬 {m[1]} ({m[2]} Ks)", url=f"https://t.me/{CHANNEL_ID.replace('@','')}/{m[3]}")] for m in movies]
    
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ ရှေ့သို့", callback_data=f"movie_menu_{page-1}"))
    
    # Check if next page exists
    next_check = db_query("SELECT 1 FROM movies LIMIT 1 OFFSET ?", (page*6,))
    if next_check: nav.append(InlineKeyboardButton("နောက်သို့ ➡️", callback_data=f"movie_menu_{page+1}"))
    
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("🏠 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**\n(အမည်ကိုနှိပ်လျှင် Channel သို့ ရောက်သွားပါမည်)", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    # Deep linking handling
    if args and args[0].startswith("buy_"):
        movie_title = args[0].replace("buy_", "").replace("_", " ")
        movie_data = db_query("SELECT price FROM movies WHERE title=?", (movie_title,), fetchone=True)
        if movie_data:
            return await show_payment_methods(update, context, movie_data[0], movie_title)

    text, markup = get_start_info()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        # Register user in DB
        user = update.effective_user
        db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
                 (user.id, user.username, user.full_name, datetime.now()))
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

# ==========================================
# ADMIN PANEL
# ==========================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    now = datetime.now()
    this_month = now.strftime("%Y-%m")
    
    # Graphs & Stats
    daily_stats = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        res = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND is_scam=0", (day,), fetchone=True)
        amt = res[0] if res and res[0] else 0
        daily_stats.append((day, amt))
    
    res_month = db_query("SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_scam=0", (f"{this_month}%",), fetchone=True)
    monthly_rev = res_month[0] if res_month and res_month[0] else 0
    
    graph_text = generate_line_graph(daily_stats)
    
    text = (
        f"📊 **Zan Admin Dashboard ({now.strftime('%B')})**\n\n"
        f"💰 **ယခုလဝင်ငွေ: {monthly_rev} MMK**\n"
        f"_(လကုန်ပါက စာရင်းအသစ် အလိုအလျောက် ပြန်စပါမည်)_\n\n"
        f"{graph_text}"
    )
    kb = [[InlineKeyboardButton("➕ ဇာတ်ကားသစ်တင်ရန်", callback_data="admin_add_movie")], [InlineKeyboardButton("🏠 Home", callback_data="start_back")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# ==========================================
# MAIN
# ==========================================
def main():
    if BOT_TOKEN == "REPLACE_WITH_YOUR_NEW_TOKEN_FROM_BOTFATHER":
        print("❌ Error: Bot Token မထည့်ရသေးပါ။ BotFather ထံမှ Token အသစ်ယူပြီး ထည့်ပါ။")
        return

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handler for Adding Movies (Admin)
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_movie_flow, pattern="^admin_add_movie$")],
        states={
            ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, admin_save_movie)]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload), CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)

    # VIP Handlers
    app.add_handler(CallbackQueryHandler(lambda u,c: show_payment_methods(u,c, PRICE_BASIC_VIP, "Basic_VIP", True), pattern="^buy_vip_basic$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_payment_methods(u,c, PRICE_PRO_VIP, "Pro_VIP", True), pattern="^buy_vip_pro$"))
    
    # General Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", admin_panel))
    
    # Menu Navigation
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    
    # Payment Selection
    app.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^pay_"))
    
    # Receipt Upload Button Handler (Missing in original code)
    app.add_handler(CallbackQueryHandler(request_receipt_upload, pattern="^upload_receipt_"))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
