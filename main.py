
import os
import logging
from typing import Dict, Tuple
import pandas as pd
from binance.client import Client
from binance.enums import *
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        # Initialize with default values
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.allowed_user_id = os.getenv('TELEGRAM_USER_ID')  # Only respond to this user
        
        self.client = Client(self.api_key, self.api_secret)
        self.symbol = 'BTCUSDT'  # Default symbol
        self.trade_amount = 0.001  # Default trade amount in BTC
        self.short_ema = 9  # Default short EMA period
        self.long_ema = 21  # Default long EMA period
        self.in_position = False
        self.current_order = None
        
        # Initialize Telegram updater
        self.updater = Updater(token=self.telegram_token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        # Add handlers
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('setcoin', self.set_coin))
        self.dispatcher.add_handler(CommandHandler('setamount', self.set_amount))
        self.dispatcher.add_handler(CommandHandler('setema', self.set_ema))
        self.dispatcher.add_handler(CommandHandler('status', self.status))
        self.dispatcher.add_handler(CommandHandler('starttrade', self.start_trading))
        self.dispatcher.add_handler(CommandHandler('stoptrade', self.stop_trading))
        
    def start(self, update: Update, context: CallbackContext):
        """Send a message when the command /start is issued."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        update.message.reply_text(
            "Welcome to Binance Trading Bot!\n\n"
            "Available commands:\n"
            "/setcoin [COIN] - Set trading pair (e.g. BTCUSDT)\n"
            "/setamount [AMOUNT] - Set trade amount\n"
            "/setema [SHORT] [LONG] - Set EMA periods\n"
            "/status - Show current settings\n"
            "/starttrade - Start automated trading\n"
            "/stoptrade - Stop automated trading\n"
        )
    
    def set_coin(self, update: Update, context: CallbackContext):
        """Set the trading pair."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        if not context.args:
            update.message.reply_text('Please specify a trading pair (e.g. /setcoin BTCUSDT)')
            return
            
        self.symbol = context.args[0].upper()
        update.message.reply_text(f'Trading pair set to {self.symbol}')
    
    def set_amount(self, update: Update, context: CallbackContext):
        """Set the trade amount."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        if not context.args:
            update.message.reply_text('Please specify an amount (e.g. /setamount 0.001)')
            return
            
        try:
            self.trade_amount = float(context.args[0])
            update.message.reply_text(f'Trade amount set to {self.trade_amount}')
        except ValueError:
            update.message.reply_text('Invalid amount. Please enter a number.')
    
    def set_ema(self, update: Update, context: CallbackContext):
        """Set EMA periods."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        if len(context.args) < 2:
            update.message.reply_text('Please specify both short and long EMA periods (e.g. /setema 9 21)')
            return
            
        try:
            self.short_ema = int(context.args[0])
            self.long_ema = int(context.args[1])
            update.message.reply_text(f'EMA periods set to Short: {self.short_ema}, Long: {self.long_ema}')
        except ValueError:
            update.message.reply_text('Invalid periods. Please enter integers.')
    
    def status(self, update: Update, context: CallbackContext):
        """Show current settings."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        status_msg = (
            f"Current Settings:\n"
            f"Trading Pair: {self.symbol}\n"
            f"Trade Amount: {self.trade_amount}\n"
            f"EMA Periods: Short={self.short_ema}, Long={self.long_ema}\n"
            f"Trading Status: {'Active' if self.in_position else 'Inactive'}"
        )
        update.message.reply_text(status_msg)
    
    def start_trading(self, update: Update, context: CallbackContext):
        """Start automated trading."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        self.in_position = True
        update.message.reply_text('Automated trading started. Monitoring for EMA crossovers...')
        self.check_ema_crossover()
    
    def stop_trading(self, update: Update, context: CallbackContext):
        """Stop automated trading."""
        if str(update.effective_user.id) != self.allowed_user_id:
            update.message.reply_text('Unauthorized access.')
            return
            
        self.in_position = False
        if self.current_order:
            self.client.cancel_order(
                symbol=self.symbol,
                orderId=self.current_order['orderId']
            )
            self.current_order = None
        update.message.reply_text('Automated trading stopped. All positions closed.')
    
    def get_klines(self) -> pd.DataFrame:
        """Get recent klines data from Binance."""
        klines = self.client.get_klines(
            symbol=self.symbol,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            limit=100
        )
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        return df
    
    def calculate_ema(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate EMA values."""
        df['short_ema'] = df['close'].ewm(span=self.short_ema, adjust=False).mean()
        df['long_ema'] = df['close'].ewm(span=self.long_ema, adjust=False).mean()
        return df['short_ema'].iloc[-1], df['long_ema'].iloc[-1]
    
    def check_ema_crossover(self):
        """Check for EMA crossover and execute trades."""
        if not self.in_position:
            return
            
        df = self.get_klines()
        short_ema, long_ema = self.calculate_ema(df)
        
        # Check for crossover
        if short_ema > long_ema and not self.current_order:
            # Buy signal
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=self.trade_amount
            )
            self.current_order = order
            self.updater.bot.send_message(
                chat_id=self.allowed_user_id,
                text=f"BUY order executed for {self.symbol} at {order['fills'][0]['price']}"
            )
        elif short_ema < long_ema and self.current_order:
            # Sell signal
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=self.trade_amount
            )
            self.current_order = None
            self.updater.bot.send_message(
                chat_id=self.allowed_user_id,
                text=f"SELL order executed for {self.symbol} at {order['fills'][0]['price']}"
            )
        
        # Schedule next check
        self.updater.job_queue.run_once(
            callback=lambda context: self.check_ema_crossover(),
            when=900  # Check every 15 minutes (900 seconds)
        )
    
    def run(self):
        """Start the bot."""
        self.updater.start_polling()
        self.updater.idle()

if __name__ == '__main__':
    bot = TradingBot()
    bot.run()