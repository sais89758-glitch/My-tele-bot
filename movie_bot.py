# Zan Movie Channel Bot – FULL UPDATED VERSION
# Features: VIP Flow Fixed, Custom Ad Timer, Myanmar Language Support

import logging
import sqlite3
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ================= CONFIGURATION =================
# သင့် Bot Token ကို ဒီမှာ ထည့်ပါ
BOT_TOKEN = "8515688348:AAH45NOcsGPPD9UMyc43u8zDLLnlKS8eGs0" 
ADMIN_ID = 6445257462
VIP_PRICE = 30000

# Links & IDs
MAIN_CHANNEL_URL = "https://t.me/ZanchannelMM"
MAIN_CHANNEL_ID = "@ZanchannelMM" 
VIP_CHANNEL_URL = "https://t.me/+bDFiZZ9gwRRjY2M1"

# ================= LOGGING SETUP =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("movie_bot.db", check_same_thread=False)
    cur = conn.cursor()
    # Users Table
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    # Payments Table
    cur.execute("CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, account_name TEXT, status TEXT, created_at TEXT)")
    # Payment Settings Table
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr_id TEXT, phone TEXT, account_name TEXT)")
    
    # Default Payment Data Check
    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

# ================= STATES =================
WAITING_SLIP, WAITING_NAME = range(2)  # User VIP Flow
WAITING_AD_CONTENT, WAITING_AD_TIME = range(2, 4)  # Admin Ad Flow
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(4, 7)  # Admin Payment Edit Flow

# ================= START & HOME =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 Zan Movie Channel Bot\n\n"
        "⛔️ Screenshot (SS) မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )
    # VIP ခလုတ်စာသား ပြင်ဆင်ထားခြင်း
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် - {VIP_PRICE} MMK", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= USER VIP PURCHASE FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "⚠️ ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )
    kb = [
        [InlineKeyboardButton("ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("မဝယ်တော့ပါ", callback_data="back_home")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Method ရွေးချယ်ရန် Button များ
    kb = [[InlineKeyboardButton(f"{m} Pay", callback_data=f"pay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("Back", callback_data="back_home")])
    await query.message.edit_text("ငွေပေးချေမှုနည်းလမ်းရွေးပါ", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Callback data မှ method ကို ယူခြင်း (ဥပမာ: pay_KBZ -> KBZ)
    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT qr_id, phone, account_name FROM payment_settings WHERE method=?", (method,))
    row = cur.fetchone()
    conn.close()

    qr_id, phone, name = row if row else (None, "N/A", "N/A")

    # User ပေးထားသည့် ပုံစံအတိုင်း စာသားပြင်ဆင်ခြင်း
    caption_text = (
        f"ငွေလွဲရန် ({VIP_PRICE} MMK)\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {phone}\n"
        f"👤 အမည်: {name}\n\n"
        "‼️ တစ်ကြိမ်ထဲ အပြည့်လွဲပါ\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ ပြေစာ Screenshot ပို့ပါ"
    )
    
    # Message အဟောင်းကို ဖျက်ပြီး အသစ်ပို့ (QR ပါရင် ပုံနဲ့ပို့၊ မပါရင် စာပဲပို့)
    try:
        await query.message.delete()
    except:
        pass

    if qr_id:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_id, caption=caption_text)
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text)
        
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။")
        return WAITING_SLIP
    
    context.user_data["slip_file"] = update.message.photo[-1].file_id
    await update.message.reply_text("ငွေလွဲသူအကောင့်နာမည်ကို ပို့ပါ")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "No Username"
    method = context.user_data.get("method")
    file_id = context.user_data.get("slip_file")
    
    # Database ထဲ သိမ်းမည်
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, method, account_name, status, created_at) VALUES (?,?,?,?,?)", 
        (user_id, method, account_name, "PENDING", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    # User ကို အကြောင်းပြန်စာ (User တောင်းဆိုထားသည့်အတိုင်း)
    reply_text = (
        "ငွေပေးချေမှုကို အတည်ပြုရန် Admin အား အကြောင်းကြားပြီးပါပြီ။\n"
        "Admin ထံမှ အမြန်ဆုံး အကြောင်းကြားပေးပါမည်။"
    )
    await update.message.reply_text(reply_text)
    
    # Admin ထံသို့ ပို့ခြင်း (User တောင်းဆိုထားသည့်အတိုင်း ခလုတ်များဖြင့်)
    admin_text = (
        f"New VIP Request 🔔\n\n"
        f"👤 ID: `{user_id}`\n"
        f"📛 User: @{username}\n"
        f"💳 Method: {method}\n"
        f"📝 Name: {account_name}"
    )
    
    kb = [
        [InlineKeyboardButton("✅ လက်ခံရရှိပြီး (Approve)", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ ငွေမရောက်ပါ / အချက်အလက်မှားယွင်းသည်", callback_data=f"reject_{user_id}")]
    ]
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID, 
        photo=file_id, 
        caption=admin_text, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return ConversationHandler.END

# ================= ADMIN DASHBOARD =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    kb = [
        [InlineKeyboardButton("📋 စာရင်းကြည့်ရန်", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ဆင်ရန်", callback_data="admin_pay_menu")],
    ]
    text = "🛠 <b>Admin Dashboard</b>\nဘာလုပ်ချင်ပါသလဲ ရွေးချယ်ပါ။"
    
    if update.callback_query: 
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: 
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN ADS FLOW (Updated Timer) =================
async def admin_ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("📢 Channel သို့ ပို့မည့် ကြော်ညာ (စာ/ပုံ/ဗီဒီယို) ပို့ပေးပါ။")
    return WAITING_AD_CONTENT

async def receive_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    context.user_data['ad_photo'] = msg.photo[-1].file_id if msg.photo else None
    context.user_data['ad_video'] = msg.video.file_id if msg.video else None
    context.user_data['ad_text'] = msg.caption if (msg.photo or msg.video) else msg.text
    
    # အချိန်ရွေးချယ်ရန် ခလုတ်များ
    kb = [
        [InlineKeyboardButton("မဖျက်ပါ (Never)", callback_data="adtime_0")],
        [InlineKeyboardButton("၁ နာရီ", callback_data="adtime_3600"), InlineKeyboardButton("၆ နာရီ", callback_data="adtime_21600")],
        [InlineKeyboardButton("၁၂ နာရီ", callback_data="adtime_43200"), InlineKeyboardButton("၂၄ နာရီ", callback_data="adtime_86400")],
        [InlineKeyboardButton("၃ ရက်", callback_data="adtime_259200"), InlineKeyboardButton("၇ ရက်", callback_data="adtime_604800")],
    ]
    
    text = (
        "⏰ ဘယ်အချိန်မှာ အော်တိုဖျက်မလဲ?\n\n"
        "👇 ခလုတ်နှိပ်၍ ရွေးနိုင်သလို စာရိုက်၍လည်း သတ်မှတ်နိုင်သည်:\n"
        "- `30m` (မိနစ် ၃၀ ကြာရင်)\n"
        "- `2h` (၂ နာရီ ကြာရင်)\n"
        "- `1d` (၁ ရက် ကြာရင်)\n"
        "- `22:00` (ဒီည ၁၀ နာရီတိတိမှာ)\n"
    )
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_AD_TIME

async def finalize_ad_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_seconds = 0
    
    # ခလုတ်နှိပ်ခြင်း သို့မဟုတ် စာရိုက်ခြင်းကို စစ်ဆေးသည်
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if "adtime_" in data:
            delete_seconds = int(data.split("_")[1])
        msg_obj = query.message
    else:
        # User typed custom time
        text = update.message.text.lower().strip()
        msg_obj = update.message
        
        now = datetime.now()
        
        try:
            if text.endswith("m"): # Minutes
                delete_seconds = int(text[:-1]) * 60
            elif text.endswith("h"): # Hours
                delete_seconds = int(text[:-1]) * 3600
            elif text.endswith("d"): # Days
                delete_seconds = int(text[:-1]) * 86400
            elif ":" in text: # Specific Time (HH:MM)
                target_time = datetime.strptime(text, "%H:%M").time()
                target_dt = datetime.combine(now.date(), target_time)
                if target_dt <= now: # If time passed today, set for tomorrow
                    target_dt += timedelta(days=1)
                delete_seconds = int((target_dt - now).total_seconds())
            else:
                await update.message.reply_text("❌ Format မှားနေပါတယ်။ `30m`, `1h`, `20:00` ပုံစံရိုက်ထည့်ပါ။")
                return WAITING_AD_TIME
        except:
             await update.message.reply_text("❌ Error: အချိန်တွက်မရပါ။ ပြန်ရိုက်ပါ။")
             return WAITING_AD_TIME

    # Broadcasting
    photo = context.user_data.get('ad_photo')
    video = context.user_data.get('ad_video')
    text = context.user_data.get('ad_text')
    
    sent_msg = None
    try:
        if photo: 
            sent_msg = await context.bot.send_photo(MAIN_CHANNEL_ID, photo, caption=text)
        elif video: 
            sent_msg = await context.bot.send_video(MAIN_CHANNEL_ID, video, caption=text)
        else: 
            sent_msg = await context.bot.send_message(MAIN_CHANNEL_ID, text)

        # Status Message
        status = "✅ ကြော်ညာတင်ပြီးပါပြီ။"
        if delete_seconds > 0:
            status += f"\n⏳ နောက် {delete_seconds//60} မိနစ် ({delete_seconds} စက္ကန့်) ကြာရင် ဖျက်ပါမည်။"
            
            # Background Task to Delete
            async def auto_delete(sec, msg_id): 
                await asyncio.sleep(sec)
                try: 
                    await context.bot.delete_message(MAIN_CHANNEL_ID, msg_id)
                    await context.bot.send_message(ADMIN_ID, f"🗑 Auto-deleted message ID {msg_id}")
                except Exception as e: 
                    logger.error(f"Failed to delete: {e}")

            asyncio.create_task(auto_delete(delete_seconds, sent_msg.message_id))
        
        if update.callback_query:
            await msg_obj.edit_text(status)
        else:
            await msg_obj.reply_text(status)
            
    except Exception as e:
        err_text = f"❌ Error: {e}"
        if update.callback_query: await msg_obj.edit_text(err_text)
        else: await msg_obj.reply_text(err_text)
        
    return ConversationHandler.END

# ================= ADMIN PAYMENT SETTINGS FLOW =================
async def admin_pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(f"{m} Pay", callback_data=f"editpay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")])
    await update.callback_query.message.edit_text("ပြင်ဆင်လိုသော Payment ရွေးပါ:", reply_markup=InlineKeyboardMarkup(kb))

async def edit_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = update.callback_query.data.split("_")[1]
    context.user_data['edit_method'] = method
    await update.callback_query.message.edit_text(f"[{method}] အတွက် QR ပုံ အသစ်ပို့ပေးပါ။")
    return PAY_SET_QR

async def receive_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("QR ပုံ ပို့ပေးပါ။")
        return PAY_SET_QR
    context.user_data['edit_qr'] = update.message.photo[-1].file_id
    await update.message.reply_text("ဖုန်းနံပါတ် အသစ်ပို့ပေးပါ။")
    return PAY_SET_PHONE

async def receive_pay_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['edit_phone'] = update.message.text
    await update.message.reply_text("အကောင့်နာမည် အသစ်ပို့ပေးပါ။")
    return PAY_SET_NAME

async def receive_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    method = context.user_data['edit_method']
    qr_id = context.user_data['edit_qr']
    phone = context.user_data['edit_phone']
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE payment_settings SET qr_id=?, phone=?, account_name=? WHERE method=?", (qr_id, phone, name, method))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ {method} အချက်အလက်များ သိမ်းပြီးပါပြီ။", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="back_admin_home")]]))
    return ConversationHandler.END

# ================= STATS & ACTIONS =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    all_inc = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vips = cur.fetchone()[0]
    conn.close()
    text = f"📊 VIP စုစုပေါင်း: {vips} ယောက်\n💰 စုစုပေါင်းဝင်ငွေ: {all_inc} MMK"
    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action, user_id = update.callback_query.data.split("_")
    user_id = int(user_id)
    conn = get_db(); cur = conn.cursor()
    
    if action == "approve":
        exp = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, exp))
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        
        # User ကို အကြောင်းကြားစာ
        await context.bot.send_message(
            user_id, 
            "✅ သင့် VIP အကောင့်ကို အတည်ပြုလိုက်ပါပြီ။\nအောက်ပါ Link မှ Join နိုင်ပါပြီ။", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 VIP Channel Join ရန်", url=VIP_CHANNEL_URL)]])
        )
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n✅ Approved (လက်ခံပြီး)")
        
    else: # Reject
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        # User ကို အကြောင်းကြားစာ
        await context.bot.send_message(user_id, "❌ ငွေလွဲမှု အဆင်မပြေပါ သို့မဟုတ် အချက်အလက်မှားယွင်းနေပါသည်။ Admin ကို ပြန်လည်ဆက်သွယ်ပါ။")
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n❌ Rejected (ပယ်ချပြီး)")
        
    conn.commit(); conn.close()

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User Payment Flow
    # Entry Point: User clicks "Pay_KBZ", etc. from the list
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^back_home$")]
    )
    
    # Admin Ads Flow
    ads_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")],
        states={
            WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_ad_content)],
            WAITING_AD_TIME: [
                CallbackQueryHandler(finalize_ad_broadcast, pattern="^adtime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_ad_broadcast) # Allow typing time
            ],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    )

    # Admin Pay Edit Flow
    pay_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_payment_start, pattern="^editpay_")],
        states={
            PAY_SET_QR: [MessageHandler(filters.PHOTO, receive_pay_qr)],
            PAY_SET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_phone)],
            PAY_SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    )

    app.add_handler(pay_conv)
    app.add_handler(ads_conv)
    app.add_handler(pay_edit_conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    
    # Navigation Handlers
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard_menu, pattern="^back_admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pay_menu, pattern="^admin_pay_menu$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
