import logging
import sqlite3
import threading
import re
import os
import base64
import httpx
import json
import anyio
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
    ConversationHandler
)
from telegram.constants import ParseMode

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN: Final = "8515688348:AAEFbdCJ6HHR6p4cCgzvUvcRDr7i7u-sL6U"
GOOGLE_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk"

ADMIN_ID: Final = 6445257462              
CHANNEL_ID: Final = "@ZanchannelMM" 
DB_NAME: Final = "movie_database.db"

# Pricing Defaults
PRICE_BASIC_VIP: Final = 10000
PRICE_PRO_VIP: Final = 30000

# States
ADD_MOVIE_STATE = 1
RECEIPT_WAITING = 2

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

# ==========================================
# KEEP ALIVE SERVER
# ==========================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running live!")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"Keep-alive server running on port {port}")
    server.serve_forever()

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
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, joined_date DATE)''')
    db_query('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATETIME, channel_post_id INTEGER)''')
    db_query('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount INTEGER, date DATE, is_approved INTEGER DEFAULT 0)''')
    db_query('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT)''')
    
    payments = [('kpay', '09960202983', 'Sai Zaw Ye Lwin'), ('wave', '09960202983', 'Sai Zaw Ye Lwin')]
    for p in payments:
        db_query("INSERT OR IGNORE INTO payment_settings (pay_type, phone, name) VALUES (?,?,?)", p)

# ==========================================
# ADMIN: MOVIE UPLOAD & PANEL (RESTORED)
# ==========================================
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
        price_match = re.search(r'#(\d+)', lines[0])
        
        if not price_match or len(lines) < 2:
            raise ValueError("Format Error")
            
        price = int(price_match.group(1))
        title = lines[1].strip()
        file_id = update.message.video.file_id
        
        bot_username = (await context.bot.get_me()).username
        kb = [[InlineKeyboardButton("💳 ဝယ်ယူရန်", url=f"https://t.me/{bot_username}?start=buy_{title.replace(' ', '_')}")] ]
        post_text = f"🎬 **ဇာတ်ကားအသစ် တင်လိုက်ပါပြီ**\n\n📝 အမည်: **{title}**\n💰 ဈေးနှုန်း: **{price} MMK**\n\n⚠️ နမူနာ ၃ မိနစ်သာ ကြည့်နိုင်ပါသည်။ အပြည့်အစုံကြည့်ရန် ဝယ်ယူပါ။"
        
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

def generate_line_graph(daily_data):
    if not daily_data: return "No data."
    max_val = max([d[1] for d in daily_data]) if any(d[1] > 0 for d in daily_data) else 1
    graph = "📊 **နေ့စဉ်ဝင်ငွေပြဇယား**\n"
    for date, amt in daily_data:
        bar_len = int((amt/max_val)*10)
        bar = "▇" * bar_len if amt > 0 else ""
        graph += f"`{date[-5:]}: {amt:>6} Ks` {bar}\n"
    return graph

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    now = datetime.now()
    this_month = now.strftime("%Y-%m")
    
    daily_stats = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        res = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND is_approved=1", (day,), fetchone=True)
        amt = res[0] if res and res[0] else 0
        daily_stats.append((day, amt))
    
    res_month = db_query("SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_approved=1", (f"{this_month}%",), fetchone=True)
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

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ လုပ်ဆောင်ချက်ကို ပယ်ဖျက်လိုက်ပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]))
    return ConversationHandler.END

# ==========================================
# AI RECEIPT CHECKER
# ==========================================
async def analyze_receipt(base64_image, expected_amount):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GOOGLE_API_KEY}"
    
    prompt = (
        f"You are a payment auditor. Analyze this bank receipt. "
        f"1. Is it an authentic transfer receipt? "
        f"2. Does the transfer amount match {expected_amount} MMK? "
        f"3. Check the 'Note' or 'Remark' field. If it contains words like 'Channel', 'Movie', 'ဇာတ်ကား', 'ကြည့်ရန်', 'ဝယ်ရန်', set has_forbidden_note to true. "
        f"Return ONLY JSON: {{\"is_valid\": bool, \"amount_detected\": int, \"has_forbidden_note\": bool, \"reason\": string}}"
    )
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": base64_image}}
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    async with httpx.AsyncClient() as client:
        for delay in [1, 2, 4]:
            try:
                response = await client.post(url, json=payload, timeout=30.0)
                if response.status_code == 200:
                    result = response.json()
                    text_res = result['candidates'][0]['content']['parts'][0]['text']
                    return json.loads(text_res)
            except Exception as e:
                logger.error(f"AI Attempt failed: {e}")
                await anyio.sleep(delay)
    return None

# ==========================================
# BOT HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        
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
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="start_back")]
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        # Register user in DB
        user = update.effective_user
        db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
                 (user.id, user.username, user.full_name, datetime.now()))
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def handle_buy_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    amount = PRICE_PRO_VIP if "pro" in query.data else PRICE_BASIC_VIP
    item = "Pro VIP Access" if "pro" in query.data else "Basic VIP Access"
    
    context.user_data['pending_item'] = item
    context.user_data['pending_amount'] = amount
    
    text = (
        f"💳 **{item} ဝယ်ယူရန်**\n\n"
        f"💰 ကျသင့်ငွေ: **{amount} MMK**\n"
        f"📱 KBZ Pay: `09960202983`\n"
        f"👤 အမည်: **Sai Zaw Ye Lwin**\n\n"
        f"⛔️ **သတိပြုရန်**\n"
        "Note (မှတ်ချက်) နေရာတွင် **Channelနှင့်ပတ်သတ်သောစာလုံး(လုံးဝ)မရေးပါနှင့်**။ ရေးမိပါက AI မှ ပယ်ချမည်ဖြစ်ပြီး ဇာတ်ကားကြည့်ခွင့်ရမည်မဟုတ်ပါ။\n\n"
        "ငွေလွှဲပြီးပါက ပြေစာ (Screenshot) ပို့ပေးပါ။"
    )
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    return RECEIPT_WAITING

async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.split("_")[-1])
    except:
        page = 1
        
    movies = db_query("SELECT id, title, price, channel_post_id FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    
    if not movies:
        await query.message.edit_text("🎬 **လက်ရှိတွင် ဇာတ်ကားများ မရှိသေးပါ**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]), parse_mode=ParseMode.MARKDOWN)
        return

    kb = [[InlineKeyboardButton(f"🎬 {m[1]} ({m[2]} Ks)", url=f"https://t.me/{CHANNEL_ID.replace('@','')}/{m[3]}")] for m in movies]
    
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ ရှေ့သို့", callback_data=f"movie_menu_{page-1}"))
    next_check = db_query("SELECT 1 FROM movies LIMIT 1 OFFSET ?", (page*6,))
    if next_check: nav.append(InlineKeyboardButton("နောက်သို့ ➡️", callback_data=f"movie_menu_{page+1}"))
    
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("🏠 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**\n(Channel သို့ရောက်သွားပါမည်)", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def process_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပြေစာ Screenshot ကို ပုံစံဖြင့် ပို့ပေးပါ။")
        return RECEIPT_WAITING

    status_msg = await update.message.reply_text("🔍 **AI စနစ်ဖြင့် ပြေစာကို စစ်ဆေးနေပါသည်...**")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        expected_amount = context.user_data.get('pending_amount', 0)
        analysis = await analyze_receipt(base64_image, expected_amount)
        
        if not analysis:
            await status_msg.edit_text("⚠️ AI စစ်ဆေးမှု ခေတ္တချို့ယွင်းနေပါသည်။ Admin ထံ တိုက်ရိုက်ပြေစာပို့ပေးပါ။")
            return ConversationHandler.END

        # Note စစ်ဆေးခြင်း
        if analysis.get('has_forbidden_note'):
            await status_msg.edit_text(
                "❌ **ငွေလွှဲမှုကို ပယ်ချလိုက်သည်**\n\n"
                "အကြောင်းပြချက်: Note တွင် 'Channel/ဇာတ်ကား' နှင့် ပတ်သက်သော စာများ ရေးသားထားသောကြောင့် ဖြစ်သည်။ "
                "စည်းကမ်းချက်အတိုင်း ငွေပြန်အမ်းမည်မဟုတ်ပါ။"
            )
            return ConversationHandler.END

        # ပမာဏ စစ်ဆေးခြင်း
        if not analysis.get('is_valid') or analysis.get('amount_detected') < expected_amount:
            await status_msg.edit_text(
                f"❌ **ပြေစာ မမှန်ကန်ပါ**\n\n"
                f"လိုအပ်သောပမာဏ: {expected_amount} Ks\n"
                f"ပြေစာပါပမာဏ: {analysis.get('amount_detected')} Ks\n"
                f"ကျေးဇူးပြု၍ ပမာဏမှန်ကန်အောင် ပြန်ပို့ပေးပါ။"
            )
            return ConversationHandler.END

        # အောင်မြင်ပါက Admin ဆီသို့ ပို့ခြင်း
        await status_msg.edit_text("✅ **AI စစ်ဆေးမှု အောင်မြင်သည်။**\nAdmin ၏ အတည်ပြုချက်ကို ခေတ္တစောင့်ဆိုင်းပေးပါ။")
        
        admin_kb = [
            [InlineKeyboardButton("✅ အတည်ပြုသည်", callback_data=f"appr_{update.effective_user.id}_{expected_amount}")],
            [InlineKeyboardButton("❌ ပယ်ချသည်", callback_data=f"reje_{update.effective_user.id}")]
        ]
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=(
                f"🔔 **ငွေလွှဲပြေစာ အသစ် (AI Verified)**\n\n"
                f"👤 User: {update.effective_user.full_name}\n"
                f"🆔 ID: `{update.effective_user.id}`\n"
                f"💰 ပမာဏ: {analysis.get('amount_detected')} MMK\n"
                f"📝 AI Reason: {analysis.get('reason')}"
            ),
            reply_markup=InlineKeyboardMarkup(admin_kb)
        )
        
    except Exception as e:
        logger.error(e)
        await status_msg.edit_text("❌ စနစ်ချို့ယွင်းမှု ဖြစ်ပေါ်ခဲ့သည်။ ပြန်လည်ကြိုးစားပါ။")
    
    return ConversationHandler.END

# Admin Approval Callback
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    action = data[0] # appr or reje
    user_id = int(data[1])
    
    if action == "appr":
        amount = data[2]
        db_query("UPDATE users SET is_vip = 1 WHERE user_id = ?", (user_id,))
        db_query("INSERT INTO transactions (user_id, type, amount, date, is_approved) VALUES (?,?,?,?,?)", 
                 (user_id, "VIP_PURCHASE", amount, datetime.now().date(), 1))
        
        await context.bot.send_message(chat_id=user_id, text="✅ **ငွေလွှဲမှု အတည်ပြုပြီးပါပြီ။**\nယခုမှစ၍ VIP Channel ရှိ ဇာတ်ကားများကို ကြည့်ရှုနိုင်ပါပြီ။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n🟢 **အတည်ပြုပြီး**")
    else:
        await context.bot.send_message(chat_id=user_id, text="❌ **သင်၏ ငွေလွှဲပြေစာကို Admin မှ ပယ်ချလိုက်ပါသည်။**\nအချက်အလက် မှားယွင်းနေခြင်းကြောင့် ဖြစ်နိုင်ပါသည်။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n🔴 **ပယ်ချပြီး**")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("လုပ်ဆောင်ချက်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="start_back")]]))
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    
    # Auto-Sleep ကာကွယ်ရန် Server
    threading.Thread(target=start_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # 1. Admin Conversation Handler (Movie Upload)
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_movie_flow, pattern="^admin_add_movie$")],
        states={
            ADD_MOVIE_STATE: [MessageHandler(filters.VIDEO, admin_save_movie)]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload), CommandHandler("start", start)],
    )
    app.add_handler(admin_conv)

    # 2. User Conversation Handler (Buy VIP)
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_buy_action, pattern="^buy_vip_")],
        states={
            RECEIPT_WAITING: [MessageHandler(filters.PHOTO, process_receipt)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel), 
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^start_back$")
        ]
    )
    app.add_handler(buy_conv)
    
    # 3. Standard Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", admin_panel)) # Restored Admin Command
    
    # 4. Callback Handlers
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(appr|reje)_"))
    
    print("Bot is starting (All Features Restored)...")
    app.run_polling()

if __name__ == "__main__":
    main()
