import logging
import sqlite3
import threading
import re
import os
import io
import time
import asyncio
import json
import base64
import requests
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

# Optional: Graph library
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
GEMINI_API_KEY: Final = "AIzaSyA5y7nWKVSHSALeKSrG1fiTBTB0hdWUZtk"

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
    db_query('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        full_name TEXT, 
        vip_type TEXT DEFAULT 'NONE', 
        vip_expiry DATETIME,
        is_banned INTEGER DEFAULT 0,
        joined_date DATETIME)''')
    
    db_query('''CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        file_id TEXT, 
        title TEXT, 
        price INTEGER, 
        channel_msg_id INTEGER)''')
    
    db_query('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        item_name TEXT, 
        amount INTEGER, 
        pay_method TEXT, 
        status TEXT DEFAULT 'PENDING', 
        date DATETIME)''')

# ==========================================
# GEMINI AI RECEIPT SCANNER
# ==========================================
async def verify_receipt_with_ai(photo_bytes, expected_amount):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GEMINI_API_KEY}"
    image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
    
    prompt = (
        f"Analyze this payment receipt from Myanmar (KBZPay, WavePay, etc.). "
        f"1. Check if the amount is at least {expected_amount} MMK. "
        f"2. IMPORTANT: Check the 'Note' or 'Message' or 'Remark' field. If it contains words like 'Channel', 'Movie', 'ဇာတ်ကား', 'ဝယ်ရန်', 'ဝင်ရန်', 'ကြည့်ရန်', 'VIP', "
        f"mark 'has_forbidden_note' as true. "
        f"3. Detect visual editing, fake fonts, or if it is an old receipt. "
        f"Return JSON: {{'is_valid': bool, 'amount_detected': int, 'has_forbidden_note': bool, 'is_scam': bool, 'reason': string}}"
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": image_base64}}
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        text_resp = result['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_resp)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return None

# ==========================================
# USER FLOW
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if banned
    user_data = db_query("SELECT is_banned FROM users WHERE user_id=?", (user.id,), fetchone=True)
    if user_data and user_data[0] == 1:
        msg_text = "⛔️ သင်သည် စည်းကမ်းချက်များကို ချိုးဖောက်သဖြင့် အသုံးပြုခွင့် ပိတ်ပင်ခံထားရပါသည်။"
        if update.callback_query:
            await update.callback_query.answer(msg_text, show_alert=True)
        else:
            await update.message.reply_text(msg_text)
        return

    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, datetime.now()))

    # Start buying process if link used
    args = context.args
    if args and args[0].startswith("buy_"):
        try:
            movie_id = int(args[0].split("_")[1])
            movie = db_query("SELECT title, price FROM movies WHERE id=?", (movie_id,), fetchone=True)
            if movie:
                await show_payment_options(update, movie[0], movie[1])
                return
        except: pass

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
    db_query("INSERT INTO transactions (user_id, item_name, amount, date) VALUES (?,?,?,?)", 
             (user_id, item_name, amount, datetime.now()))
    tx_id = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
    
    text = f"💳 **ငွေပေးချေရန် ရွေးချယ်ပါ**\n\n📝 ဝယ်ယူမည့်အရာ: **{item_name}**\n💰 ကျသင့်ငွေ: **{amount} MMK**"
    kb = [
        [InlineKeyboardButton("KBZPay", callback_data=f"pay_method_KBZ_{tx_id}"), 
         InlineKeyboardButton("WavePay", callback_data=f"pay_method_Wave_{tx_id}")],
        [InlineKeyboardButton("AYA Pay", callback_data=f"pay_method_AYA_{tx_id}"), 
         InlineKeyboardButton("CB Pay", callback_data=f"pay_method_CB_{tx_id}")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="refresh_start")]
    ]
    
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    # Expected format: pay_method_KBZ_123 or pay_select_BasicVIP_10000
    
    if data_parts[1] == "select":
        item_name = data_parts[2]
        amount = int(data_parts[3])
        await show_payment_options(update, item_name, amount)
        return
    
    # Process payment method selection
    method = data_parts[2]
    tx_id = data_parts[3]
    
    tx = db_query("SELECT item_name, amount FROM transactions WHERE id=?", (tx_id,), fetchone=True)
    if not tx: return
    
    context.user_data['current_tx_id'] = tx_id
    context.user_data['pay_method'] = method
    context.user_data['expected_amount'] = tx[1]
    context.user_data['item_name'] = tx[0]
    
    text = (
        f"✅ **{method} ဖြင့် ငွေလွှဲရန်**\n"
        f"ဖုန်းနံပါတ်: `09960202983` (Sai Zaw Ye Lwin)\n\n"
        f"⚠️ **အရေးကြီးသတိပေးချက်များ (ဖတ်ရန်)**\n"
        f"၁။ ငွေလွှဲရာတွင် Note (မှတ်ချက်) နေရာ၌ **ဘာမှမရေးပါနှင့်။**\n"
        f"❌ **(အထူးသတိပေးချက်)** - Note တွင် 'Channel ဝင်ရန်'၊ 'ဇာတ်ကားဝယ်ရန်'၊ 'ဇာတ်ကားကြည့်ရန်' စသည့် စာသားများ ရေးမိပါက **ငွေပြန်အမ်းပေးမည်မဟုတ်သလို ဇာတ်ကားလည်း ကြည့်ရှုခွင့်ရမည်မဟုတ်ပါ။**\n"
        f"၂။ ငွေကို တစ်ကြိမ်တည်းဖြင့် အပြတ်အသတ် လွှဲပေးရပါမည်။\n"
        f"၃။ ငွေခွဲလွှဲခြင်း လုံးဝ မပြုလုပ်ရပါ။\n"
        f"၄။ ငွေလွှဲပြီးပါက ပြေစာ (Screenshot) ကို ၃ မိနစ်အတွင်း ပေးပို့ရပါမည်။\n\n"
        f"❗️ ငွေလွှဲပြီးပါက **Screenshot (ပြေစာ)** ကို ဤနေရာသို့ ပေးပို့ပါ။"
    )
    await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    return WAIT_RECEIPT

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ပြေစာဓာတ်ပုံ (Screenshot) ပို့ပေးပါ။")
        return WAIT_RECEIPT
    
    msg = await update.message.reply_text("⏳ AI က ပြေစာနှင့် Note များကို စစ်ဆေးနေပါသည်...")
    
    tx_id = context.user_data.get('current_tx_id')
    expected_amount = context.user_data.get('expected_amount')
    item_name = context.user_data.get('item_name')
    user = update.effective_user

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    ai_result = await verify_receipt_with_ai(bytes(photo_bytes), expected_amount)
    
    if ai_result:
        # Check forbidden note
        if ai_result.get('has_forbidden_note'):
            db_query("UPDATE transactions SET status='REJECTED_NOTE' WHERE id=?", (tx_id,))
            await msg.edit_text(
                "❌ **ဝယ်ယူမှု မအောင်မြင်ပါ။**\n\n"
                "အကြောင်းပြချက်: ငွေလွှဲပြေစာ၏ Note (မှတ်ချက်) တွင် တားမြစ်ထားသော စာသားများ (ဇာတ်ကား/Channel) ပါဝင်နေပါသည်။\n"
                "စည်းကမ်းချက်အတိုင်း ငွေပြန်အမ်းပေးမည်မဟုတ်သလို ဇာတ်ကားလည်း ကြည့်ရှုခွင့်ရမည်မဟုတ်ပါ။"
            )
            return ConversationHandler.END

        # Check scam
        if ai_result.get('is_scam'):
            db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (user.id,))
            db_query("UPDATE transactions SET status='SCAM' WHERE id=?", (tx_id,))
            await msg.edit_text("⛔️ သင်၏ပြေစာမှာ အတုဖြစ်ကြောင်း AI က စစ်ဆေးတွေ့ရှိရပါသည်။ ထို့ကြောင့် သင့်ကို Ban လုပ်လိုက်ပါသည်။")
            return ConversationHandler.END
        
        # Check valid and amount
        if ai_result.get('is_valid') and ai_result.get('amount_detected') >= expected_amount:
            db_query("UPDATE transactions SET status='SUCCESS' WHERE id=?", (tx_id,))
            if "BasicVIP" in item_name:
                expiry = datetime.now() + timedelta(days=30)
                db_query("UPDATE users SET vip_type='BasicVIP', vip_expiry=? WHERE user_id=?", (expiry, user.id))
                await msg.edit_text(f"🎉 **{item_name}** ဝယ်ယူမှု အောင်မြင်ပါသည်။ ၁ လစာ အသုံးပြုနိုင်ပါပြီ။")
            elif "ProVIP" in item_name:
                db_query("UPDATE users SET vip_type='ProVIP' WHERE user_id=?", (user.id,))
                await msg.edit_text(f"🎉 **{item_name}** ဝယ်ယူမှု အောင်မြင်ပါသည်။ ရာသက်ပန် အသုံးပြုနိုင်ပါပြီ။")
            else:
                movie = db_query("SELECT file_id, title FROM movies WHERE title=?", (item_name,), fetchone=True)
                if movie:
                    await context.bot.send_video(user.id, video=movie[0], caption=f"🎬 **{movie[1]}**\nဝယ်ယူမှုအတွက် ကျေးဇူးတင်ပါသည်။")
                    await msg.delete()
            return ConversationHandler.END

    # Manual Review if AI fails or unsure
    await msg.edit_text("✅ ပြေစာရပါပြီ။ Admin က စစ်ဆေးပြီး အတည်ပြုပေးပါမည်။")
    caption = f"📩 **Review Needed**\n👤 {user.full_name}\n💰 {expected_amount}\n🆔 TxID: {tx_id}"
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{tx_id}_{user.id}"), 
           InlineKeyboardButton("❌ Scam & Ban", callback_data=f"adm_scm_{tx_id}_{user.id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ==========================================
# ADMIN ACTIONS
# ==========================================
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, _, tx_id, user_id = query.data.split("_")
    
    if action == "adm_app":
        tx = db_query("SELECT item_name FROM transactions WHERE id=?", (tx_id,), fetchone=True)
        if tx:
            item = tx[0]
            db_query("UPDATE transactions SET status='SUCCESS' WHERE id=?", (tx_id,))
            if "BasicVIP" in item:
                expiry = datetime.now() + timedelta(days=30)
                db_query("UPDATE users SET vip_type='BasicVIP', vip_expiry=? WHERE user_id=?", (expiry, user_id))
            elif "ProVIP" in item:
                db_query("UPDATE users SET vip_type='ProVIP' WHERE user_id=?", (user_id,))
            await context.bot.send_message(user_id, f"🎉 **{item}** ဝယ်ယူမှု အောင်မြင်ပါသည်။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n✅ APPROVED")
    
    elif action == "adm_scm":
        db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        db_query("UPDATE transactions SET status='SCAM' WHERE id=?", (tx_id,))
        await context.bot.send_message(user_id, "❌ သင်၏ပြေစာ မမှန်ကန်သဖြင့် Ban လုပ်လိုက်ပါသည်။")
        await query.message.edit_caption(caption=query.message.caption + "\n\n⛔️ BANNED")

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # VIP & Payment Selection Handler
    app.add_handler(CallbackQueryHandler(payment_handler, pattern="^pay_select_"))
    
    # Payment Method & Receipt Conversation
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_handler, pattern="^pay_method_")],
        states={WAIT_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^refresh_start$")]
    )

    app.add_handler(pay_conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^refresh_start$"))
    app.add_handler(CommandHandler("start", start))
    
    logger.info("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
