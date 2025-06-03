import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from binance.um_futures import UMFutures as Client
from dotenv import load_dotenv

# د لاګ ترتیب
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# د چاپېریال متغیرونه لوستل
load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
telegram_token = os.getenv("TELEGRAM_TOKEN")
allowed_user_id = int(os.getenv("TELEGRAM_USER_ID"))

# د اصلي بایننس حساب لپاره کلاینت
client = Client(key=api_key, secret=api_secret, base_url="https://fapi.binance.com")

# د EMA محاسبه
def calculate_ema(prices, period, smoothing=2):
    ema = [sum(prices[:period]) / period]
    for price in prices[period:]:
        ema.append((price * (smoothing / (1 + period))) + ema[-1] * (1 - (smoothing / (1 + period))))
    return ema

async def get_ema_crossover(symbol: str, interval: str, short_period: int = 9, long_period: int = 21):
    candles = client.klines(symbol=symbol, interval=interval, limit=100)
    closes = [float(c[4]) for c in candles]
    short_ema = calculate_ema(closes, short_period)
    long_ema = calculate_ema(closes, long_period)
    
    if short_ema[-2] < long_ema[-2] and short_ema[-1] > long_ema[-1]:
        return "BUY"
    elif short_ema[-2] > long_ema[-2] and short_ema[-1] < long_ema[-1]:
        return "SELL"
    return None

async def execute_trade(update: Update, symbol: str, side: str, quantity: float, leverage: int = 5):
    try:
        # د لیوریج او مارجین ډول تنظیم
        client.change_leverage(symbol=symbol, leverage=leverage)
        client.change_margin_type(symbol=symbol, marginType="ISOLATED")
        
        # د معاملې اجرا
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )
        
        entry_price = float(order['avgPrice'])
        message = (f"✅ د {symbol} معامله اجرا شوه!\n"
                  f"ډول: {side}\n"
                  f"مقدار: {quantity}\n"
                  f"قیمت: {entry_price}\n"
                  f"لیوریج: {leverage}x")
        
        if update:
            await update.message.reply_text(message)
        else:
            logger.info(message)
            
        return order
    except Exception as e:
        error_msg = f"❌ د معاملې په اجرا کې ستونزه: {str(e)}"
        if update:
            await update.message.reply_text(error_msg)
        logger.error(error_msg)
        return None

async def set_stop_loss_take_profit(symbol: str, entry_price: float, side: str, risk_percent: float = 1, rr_ratio: float = 3):
    try:
        # د SL/TP قیمتونه محاسبه کول
        if side == "BUY":
            sl_price = entry_price * (1 - risk_percent/100)
            tp_price = entry_price * (1 + risk_percent/100 * rr_ratio)
        else:
            sl_price = entry_price * (1 + risk_percent/100)
            tp_price = entry_price * (1 - risk_percent/100 * rr_ratio)
        
        # د SL/TP امرونه
        client.new_order(
            symbol=symbol,
            side="SELL" if side == "BUY" else "BUY",
            type="STOP_MARKET",
            stopPrice=round(sl_price, 4),
            closePosition=True
        )
        
        client.new_order(
            symbol=symbol,
            side="SELL" if side == "BUY" else "BUY",
            type="TAKE_PROFIT_MARKET",
            stopPrice=round(tp_price, 4),
            closePosition=True
        )
        
        logger.info(f"د {symbol} لپاره SL/TP تنظیم شو (SL: {sl_price}, TP: {tp_price})")
        return True
    except Exception as e:
        logger.error(f"د SL/TP تنظیم کې ستونزه: {str(e)}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != allowed_user_id:
        await update.message.reply_text("⛔ تاسو اجازه نلرئ!")
        return
    
    await update.message.reply_text(
        "✅ په بریالیتوب سره وصل شوی!\n\n"
        "د موجودو امرونو لیست:\n"
        "/trade [سمبول] [BUY/SELL] [مقدار] (لیوریج)\n"
        "/ema [سمبول] (interval)\n"
        "/price [سمبول]\n"
        "/balance\n"
        "/positions"
    )

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != allowed_user_id:
        await update.message.reply_text("⛔ تاسو اجازه نلرئ!")
        return
        
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ سم شکل: /trade [سمبول] [BUY/SELL] [مقدار] (لیوریج)")
        return
    
    symbol = args[0].upper()
    side = args[1].upper()
    quantity = float(args[2])
    leverage = int(args[3]) if len(args) > 3 else 5
    
    order = await execute_trade(update, symbol, side, quantity, leverage)
    if order:
        await set_stop_loss_take_profit(symbol, float(order['avgPrice']), side)

async def check_ema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != allowed_user_id:
        await update.message.reply_text("⛔ تاسو اجازه نلرئ!")
        return
        
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ سم شکل: /ema [سمبول] (interval)")
        return
    
    symbol = args[0].upper()
    interval = args[1] if len(args) > 1 else "15m"
    
    signal = await get_ema_crossover(symbol, interval)
    
    if signal:
        await update.message.reply_text(f"🚦 د {symbol} لپاره د EMA کراس سیګنال: {signal}")
    else:
        await update.message.reply_text(f"🔍 د {symbol} لپاره هیڅ کراس سیګنال نشته")

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ سم شکل: /price [سمبول]")
        return
    
    symbol = args[0].upper()
    try:
        ticker = client.ticker_price(symbol)
        await update.message.reply_text(f"📊 د {symbol} اوسنی قیمت: {ticker['price']} USDT")
    except Exception as e:
        await update.message.reply_text(f"❌ د ډېټا ترلاسه کولو کې ستونزه: {str(e)}")

async def get_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = client.account()['totalWalletBalance']
        await update.message.reply_text(f"💰 د چمتو پیسو اندازه: {balance} USDT")
    except Exception as e:
        await update.message.reply_text(f"❌ د بالانس په ترلاسه کولو کې ستونزه: {str(e)}")

async def get_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        positions = client.get_positions()
        response = "📊 تاسو په لاندې پوزیشنونو کې یاست:\n\n"
        
        for pos in positions:
            if float(pos['positionAmt']) != 0:
                pnl = float(pos['unRealizedProfit'])
                response += (f"🔹 {pos['symbol']}\n"
                           f"مقدار: {pos['positionAmt']}\n"
                           f"PNL: {pnl:.2f} USDT ({ (pnl/float(pos['initialMargin']))*100 if float(pos['initialMargin']) != 0 else 0 :.2f}%)\n"
                           f"لیوریج: {pos['leverage']}x\n\n")
        
        await update.message.reply_text(response if len(response) > 30 else "🔍 تاسو اوس مهال هیڅ پوزیشن نلرئ")
    except Exception as e:
        await update.message.reply_text(f"❌ د پوزیشنونو په ترلاسه کولو کې ستونزه: {str(e)}")

async def auto_trade(context: ContextTypes.DEFAULT_TYPE):
    try:
        symbols = ["BTCUSDT", "ETHUSDT"]
        for symbol in symbols:
            signal = await get_ema_crossover(symbol, "1h")
            if signal:
                price = float(client.ticker_price(symbol)['price'])
                balance = float(client.account()['totalWalletBalance'])
                quantity = round((balance * 0.01) / price, 4)  # د 1% سرمایه
                
                order = await execute_trade(None, symbol, signal, quantity, 5)
                if order:
                    await set_stop_loss_take_profit(symbol, float(order['avgPrice']), signal)
    except Exception as e:
        logger.error(f"په اتومات ټریډ کې ستونزه: {str(e)}")

def main():
    app = Application.builder().token(telegram_token).build()
    
    # د امرونو اضافه کول
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CommandHandler("ema", check_ema))
    app.add_handler(CommandHandler("price", get_price))
    app.add_handler(CommandHandler("balance", get_balance))
    app.add_handler(CommandHandler("positions", get_positions))
    
    # د خپلواک معاملې تنظیم (د 1 ساعت په موده)
    job_queue = app.job_queue
    job_queue.run_repeating(auto_trade, interval=3600, first=10)
    
    # د بوټ پیلول
    app.run_polling()

if __name__ == "__main__":
    main()