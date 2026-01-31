import logging
import sqlite3
import json
import requests
import os
import base64
import asyncio
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
BOT_TOKEN: Final = "8515688348:AAE0a7XcOIfRF9DJfrbdLNFsnJxPJFem18o" 
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

# ==========================================
# DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_vip INTEGER DEFAULT 0, vip_expiry DATE, joined_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, price INTEGER, added_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, movie_id INTEGER, PRIMARY KEY (user_id, movie_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS payment_settings (pay_type TEXT PRIMARY KEY, phone TEXT, name TEXT, qr_file_id TEXT)''')
    payments = [('kpay', 'None', 'None', ''), ('wave', 'None', 'None', ''), ('ayapay', 'None', 'None', ''), ('cbpay', 'None', 'None', '')]
    c.executemany("INSERT OR IGNORE INTO payment_settings VALUES (?,?,?,?)", payments)
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
# AI RECEIPT CHECKER (Enhanced)
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    base64_image = base64.b64encode(photo_bytes).decode('utf-8')
    prompt = (
        f"Analyze this Burmese banking receipt. \n"
        f"1. Check if the photo is clear, not blurry, and not over-exposed (no glare). \n"
        f"2. If the photo is not clear enough to read transaction details, return 'blurry'. \n"
        f"3. If clear, check if valid and extract amount in MMK. \n"
        f"Expected amount: {expected_amount} MMK. \n"
        f"Return ONLY JSON: {{\"is_valid\": bool, \"is_blurry\": bool, \"amount\": num, \"reason\": \"string\"}}"
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
    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", (user.id, user.username, user.full_name, today))

    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        f"1️⃣ **Basic VIP** - {PRICE_BASIC} Ks (တစ်လစာ)\n"
        f"2️⃣ **Pro VIP** - {PRICE_PRO} Ks (ရာသက်ပန်)\n\n"
        "💡 VIP မဝင်လိုပါက တစ်ကားချင်းလည်း ဝယ်ယူနိုင်ပါသည်။\n"
        "ဘာမှမဝယ်ထားပါက နမူနာ ၃ မိနစ်သာ ကြည့်ရှုခွင့်ရပါမည်။"
    )
    keyboard = [
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="buy_vip_basic")],
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("🎬 ဇာတ်ကားမီနူး", callback_data="movie_menu_1")],
        [InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url=CHANNEL_URL)]
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def view_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m_id = int(query.data.split("_")[-1])
    movie = db_query("SELECT * FROM movies WHERE id=?", (m_id,), fetchone=True)
    user_id = query.from_user.id
    
    user_data = db_query("SELECT is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    is_vip = user_data[0] if user_data else 0
    has_purchased = db_query("SELECT 1 FROM purchases WHERE user_id=? AND movie_id=?", (user_id, m_id), fetchone=True)

    if is_vip >= 1 or has_purchased:
        await context.bot.send_video(chat_id=user_id, video=movie[1], caption=f"🎬 {movie[2]}", protect_content=True)
    else:
        warning_text = (
            f"🎬 **{movie[2]} (Preview)**\n\n"
            "⚠️ ဤဗီဒီယိုသည် ၃ မိနစ်စာ နမူနာသာ ဖြစ်သည်။\n"
            "အဆုံးထိ ကြည့်ရှုနိုင်ရန် VIP (သို့မဟုတ်) တစ်ကားချင်း ဝယ်ယူပါ။"
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
    """၃ မိနစ်ပြည့်လျှင် ငွေလွဲအချက်အလက်များကို ဖျက်ပြီး အစသို့ ပြန်ပို့ခြင်း"""
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data['msg_id'])
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text="⏰ **ငွေလွဲချိန် ကုန်ဆုံးသွားပါပြီ။**\nလုံခြုံရေးအရ အချက်အလက်များကို ဖျက်လိုက်ပါသည်။ ငွေလွဲပြီးပါက Menu မှ အချက်အလက်ပြန်တောင်းပြီး ပြေစာ ပို့ပေးပါ။",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

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
        "⚠️ **အရေးကြီးသတိပေးချက်:**\n"
        "• ဤအချက်အလက်များသည် **၃ မိနစ်သာ** ပေါ်နေမည်ဖြစ်သည်။\n"
        "• **၃ မိနစ်အတွင်း** ငွေလွဲပြေစာ (SS) ကို ပို့ပေးရပါမည်။\n"
        "• အချိန်မီမပို့နိုင်ပါက ငွေကို အရင်လွဲထားပြီးမှ အချက်အလက်ပြန်တောင်းပြီး ပြေစာပို့ပါ။\n"
        "• ပုံမကြည်လင်ပါက စနစ်မှ လက်ခံမည်မဟုတ်ပါ။"
    )
    
    sent_msg = None
    if pay_info[2]:
        sent_msg = await context.bot.send_photo(chat_id=query.from_user.id, photo=pay_info[2], caption=text, parse_mode=ParseMode.MARKDOWN)
    else:
        sent_msg = await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    # ၃ မိနစ် (၁၈၀ စက္ကန့်) Timer ပေးခြင်း
    context.job_queue.run_once(auto_delete_pay_info, 180, chat_id=query.from_user.id, data={'msg_id': sent_msg.message_id}, name=str(query.from_user.id))
        
    return UPLOAD_RECEIPT

async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပြေစာ Screenshot ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    # Timer ကို ဖျက်ခြင်း (ပြေစာရောက်လာပြီဖြစ်သောကြောင့်)
    current_jobs = context.job_queue.get_jobs_by_name(str(user.id))
    for job in current_jobs:
        job.schedule_removal()

    photo = await update.message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    expected = context.user_data['expected_amount']
    buy_type = context.user_data['buy_type']

    load = await update.message.reply_text("🔍 ပြေစာအား AI ဖြင့် စစ်ဆေးနေပါသည်...")
    result = await verify_receipt_with_ai(photo_bytes, expected)

    if result.get('is_blurry'):
        await load.edit_text("❌ **ပုံမကြည်လင်ပါ (သို့မဟုတ်) အလင်းပြန်နေပါသည်။**\n\nကျေးဇူးပြု၍ ပြေစာကို အလင်းမပြန်အောင်၊ စာသားများ ထင်ရှားအောင် ပြန်ရိုက်ပြီး ပို့ပေးပါ။")
        return UPLOAD_RECEIPT

    if result.get('is_valid') and result.get('amount', 0) >= expected:
        if buy_type.startswith("vip_"):
            plan = buy_type.split("_")[1]
            v_type = 1 if plan == 'basic' else 2
            expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d") if plan == 'basic' else "9999-12-31"
            db_query("UPDATE users SET is_vip=?, vip_expiry=? WHERE user_id=?", (v_type, expiry, user.id))
            msg = f"✅ {plan.upper()} VIP အဖြစ် အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ။"
        else:
            m_id = int(buy_type.split("_")[1])
            db_query("INSERT OR IGNORE INTO purchases VALUES (?,?)", (user.id, m_id))
            msg = f"✅ ဇာတ်ကားဝယ်ယူမှု အောင်မြင်ပါသည်။ အပြည့်အစုံ ကြည့်ရှုနိုင်ပါပြီ။"
        await load.edit_text(msg)
    else:
        await load.edit_text("❌ ပြေစာမမှန်ကန်ပါ (သို့မဟုတ်) ပမာဏ လိုအပ်နေပါသည်။ ထပ်မံကြိုးစားကြည့်ပါ သို့မဟုတ် Admin ကို ဆက်သွယ်ပါ။")

    return ConversationHandler.END

# ==========================================
# MOVIE MENU & ADMIN (Simplified for structure)
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

# (Other admin handlers same as before)
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
    await query.message.reply_text(f"📝 {context.user_data['edit_method'].upper()} အတွက် `ဖုန်းနံပါတ် | နာမည်` ပို့ပါ။")
    return SETTING_PAY_INFO

async def save_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data['edit_method']
    qr_id = update.message.photo[-1].file_id if update.message.photo else ""
    text = update.message.caption if update.message.photo else update.message.text
    try:
        phone, name = [x.strip() for x in text.split("|")]
        db_query("UPDATE payment_settings SET phone=?, name=?, qr_file_id=? WHERE pay_type=?", (phone, name, qr_id, method))
        await update.message.reply_text("✅ သိမ်းဆည်းပြီးပါပြီ။")
    except: await update.message.reply_text("❌ ပုံစံမှားနေသည်။")
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

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
    app.add_handler(CommandHandler("saizawyelwin", admin_panel))
    app.add_handler(admin_pay_conv)
    app.add_handler(buy_conv)
    app.add_handler(CallbackQueryHandler(start, pattern="^start_back$"))
    app.add_handler(CallbackQueryHandler(start_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(movie_menu, pattern="^movie_menu_"))
    app.add_handler(CallbackQueryHandler(view_details, pattern="^view_"))
    app.add_handler(CallbackQueryHandler(admin_pay_settings, pattern="^adm_pay_set$"))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
