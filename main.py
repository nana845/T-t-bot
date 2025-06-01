import os
import time
import requests
from binance.client import Client
from telegram import Bot, Update
from telegram.ext import CommandHandler, Updater

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Telegram Bot Token and Chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance API Keys
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Initialize Binance Client
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# Initialize Telegram Bot
bot = Bot(token=TELEGRAM_TOKEN)

# Function to calculate EMA
def calculate_ema(prices, length):
    ema = []
    multiplier = 2 / (length + 1)
    ema.append(sum(prices[:length]) / length)
    for price in prices[length:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema[-1]

# Trading Function
def trade(update: Update, context):
    # User-defined parameters
    coin = context.args[0]  # Coin pair (e.g., BTCUSDT)
    short_ema_length = int(context.args[1])  # Short-term EMA length
    long_ema_length = int(context.args[2])  # Long-term EMA length
    trade_amount = float(context.args[3])  # Trade amount in USDT

    # Fetch historical data
    klines = client.get_klines(symbol=coin, interval=Client.KLINE_INTERVAL_1MINUTE, limit=max(short_ema_length, long_ema_length) * 2)
    closes = [float(kline[4]) for kline in klines]

    # Calculate EMAs
    short_ema = calculate_ema(closes, short_ema_length)
    long_ema = calculate_ema(closes, long_ema_length)

    # Check for buy signal
    if short_ema > long_ema:
        # Place buy order
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Buying {trade_amount} USDT of {coin} based on EMA strategy.")
        order = client.order_market_buy(symbol=coin, quoteOrderQty=trade_amount)

        # Monitor for sell signal
        while True:
            klines = client.get_klines(symbol=coin, interval=Client.KLINE_INTERVAL_1MINUTE, limit=max(short_ema_length, long_ema_length) * 2)
            closes = [float(kline[4]) for kline in klines]
            short_ema = calculate_ema(closes, short_ema_length)
            long_ema = calculate_ema(closes, long_ema_length)

            if short_ema < long_ema:
                # Place sell order
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Selling {coin} based on EMA strategy.")
                balance = client.get_asset_balance(asset=coin.replace("USDT", ""))
                quantity = float(balance['free'])
                client.order_market_sell(symbol=coin, quantity=quantity)
                break
            time.sleep(60)

# Telegram Command Handler
def start(update: Update, context):
    update.message.reply_text("Welcome to the EMA Trading Bot! Use the /trade command to start trading.")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("trade", trade))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()