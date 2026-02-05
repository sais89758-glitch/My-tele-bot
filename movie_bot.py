# Zan Movie Channel Bot – ENHANCED VERSION
# Fixed: Back Buttons, Visual UI, and QR Fetching Logic

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
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0, vip_expiry TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, account_name TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS payment_settings (method TEXT PRIMARY KEY, qr_id TEXT, phone TEXT, account_name TEXT)")
    
    methods = ['KBZ', 'Wave', 'AYA', 'CB']
    for m in methods:
        cur.execute("INSERT OR IGNORE INTO payment_settings (method, phone, account_name) VALUES (?, ?, ?)", (m, "09960202983", "Sai Zaw Ye Lwin"))
    conn.commit(); conn.close()

init_db()

def get_db():
    return sqlite3.connect("movie_bot.db", check_same_thread=False)

# ================= STATES =================
WAITING_SLIP, WAITING_NAME = range(2)
WAITING_AD_CONTENT, WAITING_AD_TIME = range(2, 4)
PAY_SET_QR, PAY_SET_PHONE, PAY_SET_NAME = range(4, 7)

# ================= START & HOME =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 <b>Zan Movie Channel Bot</b>\n\n"
        "⛔️ Screenshot (SS) မရ\n"
        "⛔️ Screen Record မရ\n"
        "⛔️ Download / Save / Forward မရ\n\n"
        "📌 ဇာတ်ကားများကို Channel အတွင်းသာ ကြည့်ရှုနိုင်ပါသည်။"
    )
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP ဝင်ရန် - {VIP_PRICE} MMK", callback_data="vip_buy")],
        [InlineKeyboardButton("📢 Channel ဝင်ရန်", url=MAIN_CHANNEL_URL)],
    ]
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= USER VIP PURCHASE FLOW =================
async def vip_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    text = (
        "⚠️ <b>ငွေမလွဲခင် မဖြစ်မနေ ဖတ်ပါ</b>\n\n"
        "⛔️ လွဲပြီးသားငွေ ပြန်မအမ်းပါ\n"
        "⛔️ ခွဲလွဲခြင်း လုံးဝမလက်ခံပါ\n"
        "⛔️ ငွေကို တစ်ခါတည်း အပြည့်လွဲရပါမည်\n\n"
        "သိရှိနားလည်ပါက ဆက်လုပ်ပါ"
    )
    kb = [
        [InlineKeyboardButton("✅ ဆက်လက်လုပ်ဆောင်မည်", callback_data="pay_methods")],
        [InlineKeyboardButton("❌ မဝယ်တော့ပါ", callback_data="back_home")]
    ]
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [[InlineKeyboardButton(f"💳 {m} Pay", callback_data=f"pay_{m}")] for m in ['KBZ', 'Wave', 'AYA', 'CB']]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
    await query.message.edit_text("<b>ငွေပေးချေမှုနည်းလမ်းရွေးပါ</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["method"] = method

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT qr_id, phone, account_name FROM payment_settings WHERE method=?", (method,))
    res = cur.fetchone()
    conn.close()
    
    qr_id, phone, name = res if res else (None, "N/A", "N/A")

    text = (
        f"<b>ငွေလွဲရန် ({VIP_PRICE} MMK)</b>\n\n"
        f"💳 {method} Pay\n"
        f"📱 ဖုန်း: {phone}\n"
        f"👤 အမည်: {name}\n\n"
        "‼️ <b>တစ်ကြိမ်ထဲ အပြည့်လွဲပါ</b>\n"
        "ခွဲလွဲ / မှားလွဲပါက\n"
        "ငွေပြန်မအမ်း / VIP မအတည်ပြုပါ\n\n"
        "⚠️ <b>ပြေစာ Screenshot ပို့ပါ</b>"
    )
    
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="pay_methods")]]
    
    # QR ပုံရှိလျှင် တွဲပို့မည်၊ မရှိလျှင် စာသားသာပို့မည်
    if qr_id:
        try:
            # အရင်စာကိုဖျက်ပြီး ပုံအသစ်ပို့သည် (ပိုသပ်ရပ်စေရန်)
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=query.message.chat_id, 
                photo=qr_id, 
                caption=text, 
                parse_mode="HTML", 
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception as e:
            logger.error(f"Photo sending failed: {e}")
            await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        
    return WAITING_SLIP

async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ <b>ဓာတ်ပုံ (Screenshot) သာ ပို့ပေးပါ။</b>", parse_mode="HTML")
        return WAITING_SLIP
    context.user_data["slip_file"] = update.message.photo[-1].file_id
    await update.message.reply_text("👤 <b>ငွေလွဲသူအကောင့်နာမည်ကို ရိုက်ပို့ပေးပါ။</b>", parse_mode="HTML")
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    method = context.user_data.get("method")
    file_id = context.user_data.get("slip_file")
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id, method, account_name, status, created_at) VALUES (?,?,?,?,?)", 
                (user_id, method, account_name, "PENDING", datetime.now().isoformat()))
    conn.commit(); conn.close()
    
    await update.message.reply_text("✅ <b>Admin ထံသို့ ပို့လိုက်ပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။</b>", parse_mode="HTML")
    
    admin_text = (
        f"🔔 <b>New VIP Request</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📛 User: @{username}\n"
        f"💳 Method: {method}\n"
        f"📝 Name: {account_name}"
    )
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ================= ADMIN DASHBOARD =================
async def admin_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = [
        [InlineKeyboardButton("📊 စာရင်းနှင့် ဝင်ငွေ", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ကြော်ညာတင်ရန်", callback_data="admin_ads")],
        [InlineKeyboardButton("💳 Payment ပြင်ဆင်ရန်", callback_data="admin_pay_menu")],
    ]
    text = "🛠 <b>Admin Dashboard</b>\n\nလုပ်ဆောင်လိုသည့် Menu ကို ရွေးချယ်ပါ။"
    if update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ================= ADMIN ADS FLOW =================
async def admin_ads_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("📢 Channel သို့ ပို့မည့် ကြော်ညာ (စာ/ပုံ/ဗီဒီယို) ပို့ပေးပါ။")
    return WAITING_AD_CONTENT

async def receive_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    context.user_data['ad_photo'] = msg.photo[-1].file_id if msg.photo else None
    context.user_data['ad_video'] = msg.video.file_id if msg.video else None
    context.user_data['ad_text'] = msg.caption if (msg.photo or msg.video) else msg.text
    
    kb = [
        [InlineKeyboardButton("မဖျက်ပါ", callback_data="adtime_0")],
        [InlineKeyboardButton("ဒီည (00:00) တွင်ဖျက်မည်", callback_data="adtime_mid_0")],
        [InlineKeyboardButton("၁ ရက်အကြာ (00:00)", callback_data="adtime_mid_1")],
        [InlineKeyboardButton("၃ ရက်အကြာ (00:00)", callback_data="adtime_mid_3")],
        [InlineKeyboardButton("၇ ရက်အကြာ (00:00)", callback_data="adtime_mid_7")],
    ]
    await msg.reply_text("⏰ <b>ဘယ်အချိန်မှာ အော်တိုဖျက်မလဲ?</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_AD_TIME

async def finalize_ad_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    data = query.data
    delete_seconds = 0
    
    if "mid_" in data:
        days = int(data.split("_")[-1])
        now = datetime.now()
        target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
        delete_seconds = int((target - now).total_seconds())
    elif "adtime_" in data:
        delete_seconds = int(data.split("_")[1])

    photo, video, text = context.user_data.get('ad_photo'), context.user_data.get('ad_video'), context.user_data.get('ad_text')
    
    try:
        if photo: sent = await context.bot.send_photo(MAIN_CHANNEL_ID, photo, caption=text)
        elif video: sent = await context.bot.send_video(MAIN_CHANNEL_ID, video, caption=text)
        else: sent = await context.bot.send_message(MAIN_CHANNEL_ID, text)

        if delete_seconds > 0:
            async def dlt(s, mid): 
                await asyncio.sleep(s)
                try: await context.bot.delete_message(MAIN_CHANNEL_ID, mid)
                except: pass
            asyncio.create_task(dlt(delete_seconds, sent.message_id))
        
        await query.message.edit_text("✅ <b>ကြော်ညာပို့ပြီးပါပြီ။</b>", parse_mode="HTML")
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")
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
    await update.message.reply_text("✅ <b>အချက်အလက်များ ပြင်ဆင်ပြီးပါပြီ။</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("OK", callback_data="back_admin_home")]]))
    return ConversationHandler.END

# ================= STATS & ACTIONS =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='APPROVED'")
    all_inc = cur.fetchone()[0] * VIP_PRICE
    cur.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
    vips = cur.fetchone()[0]
    conn.close()
    
    text = (
        "📊 <b>ဝင်ငွေနှင့် စာရင်းများ</b>\n\n"
        f"👥 VIP စုစုပေါင်း: {vips} ယောက်\n"
        f"💰 စုစုပေါင်းဝင်ငွေ: {all_inc} MMK"
    )
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin_home")]]))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action, user_id = update.callback_query.data.split("_")
    user_id = int(user_id)
    conn = get_db(); cur = conn.cursor()
    if action == "approve":
        exp = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_vip, vip_expiry) VALUES (?, 1, ?)", (user_id, exp))
        cur.execute("UPDATE payments SET status='APPROVED' WHERE user_id=? AND status='PENDING'", (user_id,))
        await context.bot.send_message(user_id, "✅ <b>သင့် VIP အကောင့်ကို အတည်ပြုလိုက်ပါပြီ။</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 VIP Channel Join ရန်", url=VIP_CHANNEL_URL)]]))
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n✅ Approved")
    else:
        cur.execute("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (user_id,))
        await context.bot.send_message(user_id, "❌ <b>ငွေလွဲမှု မအောင်မြင်ပါ သို့မဟုတ် အချက်အလက်မှားယွင်းနေပါသည်။</b>", parse_mode="HTML")
        await update.callback_query.edit_message_caption(caption=update.callback_query.message.caption + "\n\n❌ Rejected")
    conn.commit(); conn.close()

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_info, pattern="^pay_")],
        states={
            WAITING_SLIP: [MessageHandler(filters.PHOTO, receive_slip), CallbackQueryHandler(payment_methods, pattern="^pay_methods$")],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^back_home$")]
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ads_start, pattern="^admin_ads$")],
        states={
            WAITING_AD_CONTENT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_ad_content)],
            WAITING_AD_TIME: [CallbackQueryHandler(finalize_ad_broadcast, pattern="^adtime_")],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_payment_start, pattern="^editpay_")],
        states={
            PAY_SET_QR: [MessageHandler(filters.PHOTO, receive_pay_qr)],
            PAY_SET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_phone)],
            PAY_SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pay_name)],
        },
        fallbacks=[CommandHandler("tharngal", admin_dashboard_menu)]
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tharngal", admin_dashboard_menu))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(vip_warning, pattern="^vip_buy$"))
    app.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_methods$"))
    app.add_handler(CallbackQueryHandler(admin_dashboard_menu, pattern="^back_admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pay_menu, pattern="^admin_pay_menu$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    print("Bot is started...")
    app.run_polling()

if __name__ == "__main__":
    main()
