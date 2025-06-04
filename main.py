from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
import ccxt
import time
import pandas as pd
import ta
import threading
import os
from dotenv import load_dotenv

# 🔐 د محیطي променې پورته کول
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# ⚙️ د Binance تنظیمات
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# د کارن تنظیمات
user_settings = {}
current_positions = {}
bot_active = True

# ✅ د مالک تایید
def is_owner(user_id):
    return user_id == OWNER_ID

# 🟢 د بوټ پیل امر
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    
    keyboard = [
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("📊 د معاملو حالت", callback_data="status")],
        [InlineKeyboardButton("⏸️ ودرو", callback_data="pause"), InlineKeyboardButton("▶️ پیل", callback_data="resume")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ د کرپټو کرنګ بوټ ته ښه راغلاست!\n\n"
        "د لاندې امډو په کارولو سره کنټرول وکړئ:",
        reply_markup=reply_markup
    )

# ⚙️ د تنظیماتو مینو
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📌 د معاملې تنظیمات", callback_data="trade_settings")],
        [InlineKeyboardButton("⚠️ د خطر مدیریت", callback_data="risk_settings")],
        [InlineKeyboardButton("🔙 بیرته", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="د تنظیماتو مینو:\nمهرباني وکړئ یو انتخاب وکړئ:",
        reply_markup=reply_markup
    )

# 📌 د معاملې تنظیمات
async def trade_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if OWNER_ID in user_settings:
        settings = user_settings[OWNER_ID]
        text = (
            f"🔧 اوسنی تنظیمات:\n\n"
            f"📌 سمبول: {settings['symbol']}\n"
            f"💰 مقدار: {settings['qty']}\n"
            f"⚖️ لیورج: {settings['leverage']}x\n"
            f"⏱️ وخت: {settings['timeframe']}\n"
            f"📈 لنډ EMA: {settings['short_ema']}\n"
            f"📊 اوږد EMA: {settings['long_ema']}"
        )
    else:
        text = "❌ هیڅ تنظیمات شتون نلري!"
    
    keyboard = [
        [InlineKeyboardButton("✏️ تنظیمات تغیر کړئ", callback_data="change_settings")],
        [InlineKeyboardButton("🔙 بیرته", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )

# 📝 د تنظیماتو تغیر
async def change_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="مهرباني وکړئ د معاملې تنظیمات په لاندې فورمټ ولیکئ:\n\n"
             "/set SYMBOL QTY LEVERAGE TIMEFRAME SHORT_EMA LONG_EMA\n\n"
             "لکه:\n"
             "/set BTCUSDT 0.001 10 15m 9 21"
    )

# ⚠️ د خطر مدیریت
async def risk_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if OWNER_ID in user_settings:
        settings = user_settings[OWNER_ID]
        sl = settings.get('stop_loss', 'نه دی تنظیم شوی')
        tp = settings.get('take_profit', 'نه دی تنظیم شوی')
        max_risk = settings.get('max_risk', 'نه دی تنظیم شوی')
        
        text = (
            f"⚠️ د خطر مدیریت تنظیمات:\n\n"
            f"🛑 Stop Loss: {sl}\n"
            f"🎯 Take Profit: {tp}\n"
            f"☠️ اعظمي خطر: {max_risk}"
        )
    else:
        text = "❌ لومړی د معاملې تنظیمات تنظیم کړئ!"
    
    keyboard = [
        [InlineKeyboardButton("🛑 Stop Loss تنظیم کړئ", callback_data="set_sl")],
        [InlineKeyboardButton("🎯 Take Profit تنظیم کړئ", callback_data="set_tp")],
        [InlineKeyboardButton("☠️ اعظمي خطر تنظیم کړئ", callback_data="set_risk")],
        [InlineKeyboardButton("🔙 بیرته", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )

# 🛑 د Stop Loss تنظیم
async def set_stop_loss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="مهرباني وکړئ د Stop Loss په سلنه ولیکئ (لکه 1.5):"
    )
    return "WAITING_SL"

# ... (په ورته ډول د Take Profit او نورو تنظیماتو لپاره توابع)

# 🔄 د بوټ فعال/غیرفعال کول
async def toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    global bot_active
    if query.data == "pause":
        bot_active = False
        status = "⏸️ بوټ ودرول شو"
    else:
        bot_active = True
        status = "▶️ بوټ فعال شو"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("📊 د معاملو حالت", callback_data="status")],
        [InlineKeyboardButton("⏸️ ودرو", callback_data="pause"), InlineKeyboardButton("▶️ پیل", callback_data="resume")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f"{status}\n\nد بوټ اوسنی حالت: {'فعال' if bot_active else 'غیرفعال'}",
        reply_markup=reply_markup
    )

# 📊 د معاملو حالت
async def trade_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if OWNER_ID in current_positions:
        position = current_positions[OWNER_ID]
        text = f"📊 اوسنی پوزیشن: {position}"
    else:
        text = "📊 اوسنی پوزیشن: هیڅ فعال پوزیشن نشته"
    
    keyboard = [
        [InlineKeyboardButton("🔙 بیرته", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )

# 📌 د تنظیماتو امر
async def set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    
    try:
        symbol = context.args[0].upper()
        qty = float(context.args[1])
        leverage = int(context.args[2])
        timeframe = context.args[3]
        short_ema = int(context.args[4]) if len(context.args) > 4 else 9
        long_ema = int(context.args[5]) if len(context.args) > 5 else 21
        
        user_settings[OWNER_ID] = {
            'symbol': symbol,
            'qty': qty,
            'leverage': leverage,
            'timeframe': timeframe,
            'short_ema': short_ema,
            'long_ema': long_ema,
            'stop_loss': 1.0,  # Default 1% stop loss
            'take_profit': 2.0,  # Default 2% take profit
            'max_risk': 10.0  # Default 10% max risk per trade
        }
        
        await update.message.reply_text(
            f"✅ تنظیمات په بریالیتوب سره ثبت شول:\n\n"
            f"📌 سمبول: {symbol}\n"
            f"💰 مقدار: {qty}\n"
            f"⚖️ لیورج: {leverage}x\n"
            f"⏱️ وخت: {timeframe}\n"
            f"📈 لنډ EMA: {short_ema}\n"
            f"📊 اوږد EMA: {long_ema}"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ ناسم فورمټ! مهرباني وکړئ داسې ولیکئ:\n\n"
            "/set SYMBOL QTY LEVERAGE TIMEFRAME [SHORT_EMA] [LONG_EMA]\n\n"
            "لکه:\n"
            "/set BTCUSDT 0.001 10 15m 9 21"
        )

# ... (نور د معاملې منطق او نور توابع)

# 🟢 د بوټ پیل
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # د امرونو هندلرونه
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_config))
    
    # د کالبیک هندلرونه
    app.add_handler(CallbackQueryHandler(settings_menu, pattern="settings"))
    app.add_handler(CallbackQueryHandler(trade_settings, pattern="trade_settings"))
    app.add_handler(CallbackQueryHandler(risk_settings, pattern="risk_settings"))
    app.add_handler(CallbackQueryHandler(toggle_bot, pattern="^(pause|resume)$"))
    app.add_handler(CallbackQueryHandler(trade_status, pattern="status"))
    app.add_handler(CallbackQueryHandler(change_settings, pattern="change_settings"))
    app.add_handler(CallbackQueryHandler(set_stop_loss, pattern="set_sl"))
    
    # د معاملې لوپ په جلا تریډ کې پیل کول
    trading_thread = threading.Thread(target=run_trading_loop, daemon=True)
    trading_thread.start()
    
    app.run_polling()