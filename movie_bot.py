import logging
import sqlite3
import threading
import re
import os
import base64
import httpx
import json
import anyio
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
# CONFIGURATION (တိုက်ရိုက်ထည့်သွင်းထားသည်)
# ==========================================
# Render မှာ Environment Variable လိုက်ပြင်စရာမလိုအောင် ဤနေရာတွင် တိုက်ရိုက်ထည့်ထားသည်
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
# AI RECEIPT CHECKER (GEMINI API)
# ==========================================
async def analyze_receipt(base64_image, expected_amount):
    """Gemini API ကို သုံး၍ ပြေစာ စစ်ဆေးခြင်း"""
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
    text = (
        "🎬 **Zan Movie Bot မှ ကြိုဆိုပါတယ်**\n\n"
        "⚠️ **စည်းကမ်းချက်များ**\n"
        "- ငွေလွှဲရာတွင် Note တွင် ဘာမှမရေးပါနှင့်။\n"
        "- Channel/ဇာတ်ကား အမည်များ ရေးမိပါက ငွေပြန်အမ်းမည်မဟုတ်ပါ။\n"
        "- AI မှ အလိုအလျောက် စစ်ဆေးပယ်ချပါလိမ့်မည်။"
    )
    kb = [
        [InlineKeyboardButton("👑 Pro VIP (30000 Ks)", callback_data="buy_vip_pro")],
        [InlineKeyboardButton("👑 Basic VIP (10000 Ks)", callback_data="buy_vip_basic")],
        [InlineKeyboardButton("🎬 ဇာတ်ကား Menu", callback_data="movie_menu_1")]
    ]
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
        "Note (မှတ်ချက်) နေရာတွင် **စာလုံးဝမရေးပါနှင့်**။ ရေးမိပါက AI မှ ပယ်ချမည်ဖြစ်ပြီး ဇာတ်ကားကြည့်ခွင့်ရမည်မဟုတ်ပါ။\n\n"
        "ငွေလွှဲပြီးပါက ပြေစာ (Screenshot) ပို့ပေးပါ။"
    )
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return RECEIPT_WAITING

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
    await update.message.reply_text("လုပ်ဆောင်ချက်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။")
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_buy_action, pattern="^buy_vip_")],
        states={
            RECEIPT_WAITING: [MessageHandler(filters.PHOTO, process_receipt)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
    )
    
    app.add_handler(buy_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(appr|reje)_"))
    
    print("Bot is starting with AI and Hardcoded Tokens...")
    app.run_polling()

if __name__ == "__main__":
    main()
