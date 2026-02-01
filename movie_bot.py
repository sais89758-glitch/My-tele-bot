import logging
import sqlite3
import json
import requests
import os
import base64
import asyncio
import threading
import re
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
from typing import Final

# Graph plotting library
try:
    import matplotlib
    matplotlib.use('Agg') # Use non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

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

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Lock for Security/Stability
db_lock = threading.Lock()

# ==========================================
# RENDER HEALTH CHECK SERVER (Keep Alive)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server started on port {port}")
    server.serve_forever()

# ==========================================
# DATABASE SETUP
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, vip_expiry DATE, joined_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, movie_id INTEGER, PRIMARY KEY (user_id, movie_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
        # Update transactions table to ensure it exists correctly
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, type TEXT, date DATE, status TEXT)''')
        # Ensure visitors table exists
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
            logger.error(f"Database Error: {e}")
            return None

# ==========================================
# AI RECEIPT CHECKER
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
    prompt = (
        f"Analyze this Burmese banking receipt. \n"
        f"1. Check if the photo is clear, not blurry, and not over-exposed. \n"
        f"2. If blurry or unreadable, return 'blurry'. \n"
        f"3. If clear, check if valid and extract amount in MMK. \n"
        f"Expected amount: {expected_amount} MMK. \n"
        f"Return ONLY JSON: {{\"is_valid\": bool, \"is_blurry\": bool, \"amount\": num}}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/png", "data": base64_image}}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        response = requests.post(url, json=payload, timeout=25)
        return json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'])
    except:
        return {"is_valid": False, "is_blurry": True, "amount": 0}

# ==========================================
# USER UI HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Track User and Visitor
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", (user.id, user.username, user.full_name, today))
    db_query("INSERT OR IGNORE INTO visitors (user_id, date) VALUES (?,?)", (user.id, today))

    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "**လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:**\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Video Record ဖမ်းခြင်း၊ Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ တစ်ကားချင်း ဝယ်ယူထားသော ဇာတ်ကားများကို ဤ Channel အတွင်း ရာသက်ပန် ပြန်လည်ကြည့်ရှုနိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        f"1️⃣ **Basic VIP ({PRICE_BASIC} Ks) - 1 Month Access**\n"
        "   - **တစ်လအတွင်း** တင်သမျှကားများကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n"
        "   - တစ်လပြည့်ပြီးနောက် တင်သော ကားအသစ်များကို ကြည့်ရှုခွင့်မရှိပါ။\n\n"
        f"2️⃣ **Pro VIP ({PRICE_PRO} Ks) - Lifetime Access**\n"
        "   - Channel တွင် တင်သမျှ ကားအဟောင်း/အသစ် အားလုံးကို ရာသက်ပန် ကြည့်ရှုခွင့်ရပါမည်။\n\n"
        "💡 ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။"
    )
    keyboard = [
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="buy_vip_basic")],
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=CHANNEL_URL)]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def view_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m_id = int(query.data.split("_")[-1])
    movie = db_query("SELECT * FROM movies WHERE id=?", (m_id,), fetchone=True)
    user_id = query.from_user.id
    
    user_data = db_query("SELECT is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    is_vip = user_data[0] if user_data else 0
    has_purchased = db_query("SELECT 1 FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip >= 1 or has_purchased: # Note: Logic for Basic VIP expiry vs movie date would go here if strict enforcement is needed
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}", protect_content=True)
    else:
        warning_text = (
            f"🎬 **{movie[2]} (Preview)**\n\n"
            "⚠️ ဤဗီဒီယိုသည် ၃ မိနစ်စာ နမူနာသာ ဖြစ်သည်။\n"
            "• တစ်ကားချင်းဝယ်ယူပါက ရာသက်ပန် ပြန်ကြည့်နိုင်ပါသည်။\n"
            "• VIP ဝင်ပါက အားလုံးကြည့်နိုင်ပါသည်။"
        )
        kb = [[InlineKeyboardButton(f"💸 ဝယ်မည် ({movie[3]} Ks)", callback_data=f"buy_single_{m_id}")],
              [InlineKeyboardButton("👑 VIP ဝင်မည်", callback_data="buy_vip_basic")],
              [InlineKeyboardButton("🔙 Back", callback_data="movie_menu_1")]]
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=warning_text, duration=180, protect_content=True, reply_markup=InlineKeyboardMarkup(kb))

# ==========================================
# PAYMENT FLOW WITH TIMEOUT
# ==========================================
async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    
    if data[1] == "vip":
        plan = data[2]
        context.user_data['buy_type'] = f"vip_{plan}"
        context.user_data['expected_amount'] = PRICE_BASIC if plan == 'basic' else PRICE_PRO
    else:
        m_id = int(data[2])
        movie = db_query("SELECT title, price FROM movies WHERE id=?", (m_id,), fetchone=True)
        context.user_data['buy_type'] = f"single_{m_id}"
        context.user_data['expected_amount'] = movie[1]

    text = "💳 ငွေပေးချေမည့်နည်းလမ်းကို ရွေးချယ်ပေးပါ"
    keyboard = [
        [InlineKeyboardButton("🟦 KBZPay", callback_data="pay_method_kpay"), InlineKeyboardButton("🟧 WavePay", callback_data="pay_method_wave")],
        [InlineKeyboardButton("🟥 AYA Pay", callback_data="pay_method_ayapay"), InlineKeyboardButton("🟦 CB Pay", callback_data="pay_method_cbpay")],
        [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
    ]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def auto_delete_pay_info(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data['msg_id'])
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text="⏰ **ငွေလွဲချိန် ကုန်ဆုံးသွားပါပြီ။**\n\nလုံခြုံရေးအရ QR နှင့် အချက်အလက်များကို ဖျက်လိုက်ပါသည်။\nငွေလွဲပြီးပါက Menu မှတဆင့် ငွေပေးချေမှု ခလုတ်ကို ပြန်နှိပ်ပြီး အချက်အလက်ပြန်တောင်းကာ ပြေစာ ပို့ပေးပါ။",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Auto Delete Error: {e}")

async def show_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[-1]
    context.user_data['method'] = method
    
    pay_info = db_query("SELECT phone, name, qr_file_id FROM payment_settings WHERE pay_type=?", (method,), fetchone=True)
    expected = context.user_data['expected_amount']
    
    text = (
        f"💸 **{method.upper()} ဖြင့် ငွေပေးချေခြင်း**\n\n"
        f"💰 ကျသင့်ငွေ: **{expected} MMK**\n"
        f"📞 Phone: `{pay_info[0]}`\n"
        f"👤 Name: **{pay_info[1]}**\n\n"
        "⚠️ **စည်းကမ်းချက်များ:**\n"
        "• ငွေပမာဏကို တစ်ခါတည်း အပြည့်အဝလွဲရပါမည်။\n"
        "• ပြေစာပုံမဟုတ်ဘဲ တခြားပုံတင်ခြင်း (သို့) ပြေစာအတုတင်ခြင်းများရှိပါက Bot မှ အမြဲတမ်း Ban ပါမည်။\n\n"
        "⏳ **အချိန်ကန့်သတ်ချက်:**\n"
        "• ဤအချက်အလက်များသည် **၃ မိနစ်သာ** ပေါ်နေမည်ဖြစ်သည်။\n"
        "• **၃ မိနစ်အတွင်း** ငွေလွဲပြေစာ (SS) ကို ပို့ပေးရပါမည်။"
    )
    
    sent_msg = None
    if pay_info[2]:
        sent_msg = await context.bot.send_photo(chat_id=query.from_user.id, photo=pay_info[2], caption=text, parse_mode=ParseMode.MARKDOWN)
    else:
        sent_msg = await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    # 3-Minute Timer (180 seconds)
    context.job_queue.run_once(auto_delete_pay_info, 180, chat_id=query.from_user.id, data={'msg_id': sent_msg.message_id}, name=str(query.from_user.id))
        
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပြေစာ Screenshot ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    current_jobs = context.job_queue.get_jobs_by_name(str(user.id))
    for job in current_jobs:
        job.schedule_removal()

    photo = await update.message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    expected = context.user_data['expected_amount']
    buy_type = context.user_data['buy_type']

    load = await update.message.reply_text("🔍 ပြေစာအား AI ဖြင့် စစ်ဆေးနေပါသည်...")
    result = await verify_receipt_with_ai(photo_bytes, expected)
    today = datetime.now().strftime("%Y-%m-%d")

    if result.get('is_blurry'):
        await load.edit_text("❌ **ပုံမကြည်လင်ပါ။**\n\nကျေးဇူးပြု၍ ပြေစာကို အလင်းမပြန်အောင် ပြန်ရိုက်ပြီး ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    if result.get('is_valid') and result.get('amount', 0) >= expected:
        if buy_type.startswith("vip_"):
            plan = buy_type.split("_")[1]
            v_type = 1 if plan == 'basic' else 2
            expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d") if plan == 'basic' else "9999-12-31"
            db_query("UPDATE users SET is_vip=?, vip_expiry=? WHERE user_id=?", (v_type, expiry, user.id))
            db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, expected, f'vip_{plan}', today, 'success'))
            msg = f"✅ {plan.upper()} VIP အဖြစ် အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ။"
        else:
            m_id = int(buy_type.split("_")[1])
            db_query("INSERT OR IGNORE INTO purchases VALUES (?,?)", (user.id, m_id))
            db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, expected, f'single_{m_id}', today, 'success'))
            msg = f"✅ ဇာတ်ကားဝယ်ယူမှု အောင်မြင်ပါသည်။"
        await load.edit_text(msg)
    else:
        # Record Scam Attempt
        db_query("INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?,?,?,?,?)", (user.id, 0, 'scam_attempt', today, 'failed'))
        await load.edit_text("❌ ပြေစာမမှန်ကန်ပါ (သို့မဟုတ်) ပမာဏ လိုအပ်နေပါသည်။")

    return ConversationHandler.END

# ==========================================
# ADMIN STATS & GRAPH
# ==========================================
async def generate_admin_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_month = now.strftime("%Y-%m")
    month_name = now.strftime("%B")

    # 1. Traffic Stats
    visitors_today = db_query("SELECT COUNT(*) FROM visitors WHERE date=?", (today,), fetchone=True)[0]
    total_visitors = db_query("SELECT COUNT(*) FROM visitors", fetchone=True)[0]

    # 2. Transaction Stats (Today)
    vip_today = db_query("SELECT COUNT(*) FROM transactions WHERE type LIKE 'vip_%' AND date=? AND status='success'", (today,), fetchone=True)[0]
    single_today = db_query("SELECT COUNT(*) FROM transactions WHERE type LIKE 'single_%' AND date=? AND status='success'", (today,), fetchone=True)[0]
    scam_today = db_query("SELECT COUNT(*) FROM transactions WHERE status='failed' AND date=?", (today,), fetchone=True)[0]
    rev_today = db_query("SELECT SUM(amount) FROM transactions WHERE date=? AND status='success'", (today,), fetchone=True)[0] or 0
    
    # 3. Transaction Stats (Monthly Total)
    vip_total = db_query("SELECT COUNT(*) FROM transactions WHERE type LIKE 'vip_%' AND date LIKE ? AND status='success'", (f"{current_month}%",), fetchone=True)[0]
    single_total = db_query("SELECT COUNT(*) FROM transactions WHERE type LIKE 'single_%' AND date LIKE ? AND status='success'", (f"{current_month}%",), fetchone=True)[0]
    scam_total = db_query("SELECT COUNT(*) FROM transactions WHERE status='failed' AND date LIKE ?", (f"{current_month}%",), fetchone=True)[0]
    rev_total = db_query("SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND status='success'", (f"{current_month}%",), fetchone=True)[0] or 0

    # 4. Window Shoppers (Visited but didn't buy today)
    buyers_today = db_query("SELECT COUNT(DISTINCT user_id) FROM transactions WHERE date=? AND status='success'", (today,), fetchone=True)[0]
    window_shoppers_today = max(0, visitors_today - buyers_today)

    # 5. Single Buyers Detail (Today)
    single_details = db_query("""
        SELECT u.full_name, m.title 
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        LEFT JOIN movies m ON CAST(SUBSTR(t.type, 8) AS INTEGER) = m.id
        WHERE t.type LIKE 'single_%' AND t.date=? AND t.status='success'
    """, (today,))
    
    single_buyer_text = "\n".join([f"👤 {row[0]} -> 🎬 {row[1]}" for row in single_details]) if single_details else "မရှိပါ"

    report_text = (
        f"📊 **Admin Daily & Monthly Report**\n"
        f"📅 Date: {today}\n\n"
        f"💰 **ဝင်ငွေစာရင်း (MMK):**\n"
        f"• ယနေ့ ဝင်ငွေ: {rev_today:,.0f} Ks\n"
        f"• {month_name} လချုပ်: {rev_total:,.0f} Ks\n\n"
        f"👥 **လူဝင်ရောက်မှု (Traffic):**\n"
        f"• ယနေ့ Visitor: {visitors_today}\n"
        f"• Window Shoppers (မဝယ်သူများ): {window_shoppers_today}\n"
        f"• စုစုပေါင်း Visitor: {total_visitors}\n\n"
        f"👑 **VIP အရောင်းစာရင်း:**\n"
        f"• ယနေ့ VIP ဝင်သူ: {vip_today}\n"
        f"• {month_name} VIP စုစုပေါင်း: {vip_total}\n\n"
        f"🎬 **တစ်ကားချင်း ဝယ်သူများ:**\n"
        f"• ယနေ့ ဝယ်သူအရေအတွက်: {single_today}\n"
        f"• {month_name} စုစုပေါင်း: {single_total}\n"
        f"👇 **ယနေ့ဝယ်ယူသူ စာရင်း:**\n{single_buyer_text}\n\n"
        f"🚫 **လုံခြုံရေး (Scams):**\n"
        f"• ယနေ့ Scam/Fail: {scam_today}\n"
        f"• {month_name} စုစုပေါင်း: {scam_total}"
    )

    # Generate Graph
    photo = None
    if HAS_MATPLOTLIB:
        try:
            # Query Daily Revenue for Graph
            daily_rev = db_query("SELECT date, SUM(amount) FROM transactions WHERE date LIKE ? AND status='success' GROUP BY date ORDER BY date", (f"{current_month}%",))
            if daily_rev:
                dates = [d[0].split('-')[-1] for d in daily_rev] # Get days only
                amounts = [d[1] for d in daily_rev]
                
                plt.figure(figsize=(10, 5))
                plt.plot(dates, amounts, marker='o', linestyle='-', color='b')
                plt.title(f'Daily Revenue - {month_name}')
                plt.xlabel('Day')
                plt.ylabel('Amount (MMK)')
                plt.grid(True)
                
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                photo = buf
                plt.close()
        except Exception as e:
            logger.error(f"Graph Error: {e}")

    if photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=report_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text=report_text, parse_mode=ParseMode.MARKDOWN)

# ==========================================
# MOVIE MENU & ADMIN
# ==========================================
async def movie_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    movies = db_query("SELECT id, title, price FROM movies ORDER BY id DESC LIMIT 6 OFFSET ?", ((page-1)*6,))
    if not movies: return await query.answer("မရှိသေးပါ။")
    kb = [[InlineKeyboardButton(f"{m[1]} ({m[2]} Ks)", callback_data=f"view_{m[0]}")] for m in movies]
    kb.append([InlineKeyboardButton("🔙 Home", callback_data="start_back")])
    await query.message.edit_text("🎬 **ဇာတ်ကားစာရင်း**", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = [[InlineKeyboardButton("💳 Payment Settings", callback_data="adm_pay_set")], [InlineKeyboardButton("❌ Close", callback_data="start_back")]]
    await update.message.reply_text("⚙️ **Admin Panel**", reply_markup=InlineKeyboardMarkup(kb))

async def admin_pay_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton("Edit KPay", callback_data="edit_pay_kpay"), InlineKeyboardButton("Edit Wave", callback_data="edit_pay_wave")],
          [InlineKeyboardButton("Edit AYAPay", callback_data="edit_pay_ayapay"), InlineKeyboardButton("Edit CBPay", callback_data="edit_pay_cbpay")],
          [InlineKeyboardButton("🔙 Back", callback_data="start_back")]]
    await query.message.edit_text("ပြင်ဆင်လိုသည့် Payment ရွေးပါ -", reply_markup=InlineKeyboardMarkup(kb))

async def start_edit_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['edit_method'] = query.data.split("_")[-1]
    await query.message.reply_text(f"📝 {context.user_data['edit_method'].upper()} အတွက် အချက်အလက်ပို့ပါ။\n\nပုံစံ:\n`ဖုန်းနံပါတ်` \n`နာမည်` \n\n(သို့မဟုတ် QR ပုံကို caption တွင် အထက်ပါအတိုင်းရေး၍ ပို့ပါ။)")
    return SETTING_PAY_INFO

async def save_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    method = context.user_data['edit_method']
    qr_id = update.message.photo[-1].file_id if update.message.photo else ""
    raw_text = update.message.caption if update.message.photo else update.message.text
    
    if not raw_text:
        await update.message.reply_text("❌ စာသားထည့်ပေးရန် လိုအပ်ပါသည်။")
        return SETTING_PAY_INFO

    lines = [line.strip() for line in raw_text.replace('|', '\n').split('\n') if line.strip()]
    
    try:
        if len(lines) >= 2:
            phone = lines[0]
            name = lines[1]
            db_query("UPDATE payment_settings SET phone=?, name=?, qr_file_id=? WHERE pay_type=?", (phone, name, qr_id, method))
            await update.message.reply_text(f"✅ {method.upper()} အတွက် အချက်အလက်များ သိမ်းဆည်းပြီးပါပြီ။\n\n📞 ဖုန်း: {phone}\n👤 နာမည်: {name}")
        else:
            raise ValueError("Invalid format")
    except Exception as e:
        await update.message.reply_text("❌ ပုံစံမှားနေပါသည်။ \n\nဖုန်းနံပါတ် (စာကြောင်းအသစ်ဆင်း) \nနာမည် \n\nပုံစံအတိုင်း ပို့ပေးပါ။")
        return SETTING_PAY_INFO
        
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    
    # Start Health Check in a separate thread
    threading.Thread(target=run_health_check, daemon=True).start()
    
    defaults = Defaults(protect_content=True)
    app = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_pay_info, pattern="^pay_method_")],
        states={UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, confirm_receipt)]},
        fallbacks=[CommandHandler("start", start)]
    )
    
    admin_pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_pay, pattern="^edit_pay_")],
        states={SETTING_PAY_INFO: [MessageHandler(filters.TEXT | filters.PHOTO, save_pay_info)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saizawyelwin", generate_admin_report)) # Changed to Direct Report
    app.add_handler(admin_pay_conv)
    app.add_handler(buy_conv)
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(start_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))
    app.add_handler(CallbackQueryHandler(admin_pay_settings, pattern="^adm_pay_set$"))

    # Render Conflict Fix: drop_pending_updates=True clears old requests
    print("Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
