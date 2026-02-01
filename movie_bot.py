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
    """
    Gemini 2.5 Flash ကိုသုံးပြီး ပြေစာ အတု/အစစ် နှင့် Note ပါမပါ စစ်ဆေးခြင်း
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GEMINI_API_KEY}"
    
    image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
    
    prompt = (
        f"Analyze this payment receipt. "
        f"1. Check if the amount is at least {expected_amount} MMK. "
        f"2. IMPORTANT: Check the 'Note' or 'Message' field. If it contains words like 'Channel', 'Movie', 'ဇာတ်ကား', 'ဝယ်ရန်', 'ဝင်ရန်', 'ကြည့်ရန်', "
        f"mark 'has_forbidden_note' as true. "
        f"3. Detect visual editing/fakes. "
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
    user_data = db_query("SELECT is_banned FROM users WHERE user_id=?", (user.id,), fetchone=True)
    if user_data and user_data[0] == 1:
        await update.message.reply_text("⛔️ သင်သည် စည်းကမ်းချက်များကို ချိုးဖောက်သဖြင့် အသုံးပြုခွင့် ပိတ်ပင်ခံထားရပါသည်။")
        return

    db_query("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date) VALUES (?,?,?,?)", 
             (user.id, user.username, user.full_name, datetime.now()))

    # Welcome message and buttons logic...
    text = (
        "🎬 **Zan Movie Channel Bot**\n\n"
        "လုံခြုံရေးနှင့် စည်းကမ်းချက်များ:\n"
        "⛔️ ဇာတ်ကားများကို SS ရိုက်ခြင်း၊ Video Record ဖမ်းခြင်း၊ ဖုန်းထဲသို့ Save လုပ်ခြင်း နှင့် Forward လုပ်ခြင်းများ လုံးဝမရပါ။\n"
        "✅ တစ်ကားချင်း ဝယ်ယူထားသော ဇာတ်ကားများကို ဤ Channel အတွင်း ရာသက်ပန် ပြန်ကြည့်နိုင်ပါသည်။\n\n"
        "👑 **VIP အစီအစဉ်များ**\n"
        "1️⃣ Basic VIP (10000 Ks) - 1 Month Access\n"
        "2️⃣ Pro VIP (30000 Ks) - Lifetime Access\n"
    )
    
    kb = [[InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="pay_select_BasicVIP_10000")],
          [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="pay_select_ProVIP_30000")],
          [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_start")]]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, method, tx_id = query.data.split("_")
    
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
        await update.message.reply_text("❌ ပြေစာဓာတ်ပုံ ပို့ပေးပါ။")
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
        # Note ပါသွားရင် Reject လုပ်မယ့်အပိုင်း
        if ai_result.get('has_forbidden_note'):
            db_query("UPDATE transactions SET status='REJECTED_NOTE' WHERE id=?", (tx_id,))
            await msg.edit_text(
                "❌ **ဝယ်ယူမှု မအောင်မြင်ပါ။**\n\n"
                "အကြောင်းပြချက်: ငွေလွှဲပြေစာ၏ Note (မှတ်ချက်) တွင် တားမြစ်ထားသော စာသားများ ပါဝင်နေပါသည်။\n"
                "စည်းကမ်းချက်အတိုင်း ငွေပြန်အမ်းပေးမည်မဟုတ်သလို ဇာတ်ကားလည်း ကြည့်ရှုခွင့်ရမည်မဟုတ်ပါ။"
            )
            return ConversationHandler.END

        if ai_result.get('is_scam'):
            db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (user.id,))
            await msg.edit_text("⛔️ ပြေစာအတုဖြစ်သဖြင့် သင့်အား Ban လုပ်လိုက်ပါသည်။")
            return ConversationHandler.END
        
        if ai_result.get('is_valid') and ai_result.get('amount_detected') >= expected_amount:
            db_query("UPDATE transactions SET status='SUCCESS' WHERE id=?", (tx_id,))
            # Handle VIP or Movie access logic here...
            await msg.edit_text(f"🎉 **{item_name}** ဝယ်ယူမှု အောင်မြင်ပါသည်။")
            return ConversationHandler.END

    await msg.edit_text("✅ ပြေစာရပါပြီ။ Admin က Note ပါမပါ စစ်ဆေးပြီး အတည်ပြုပေးပါမည်။")
    # Send to admin for manual review if AI is unsure
    return ConversationHandler.END

# ... rest of the code (admin_decision, main, etc.)
