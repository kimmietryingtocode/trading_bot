from lumibot.brokers import Alpaca
from lumibot.brokers import YahooDataBackTesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from alpaca_trade_api import REST
from timedelta import Timedelta
from finbert_utils import estimate_sentiment

import numpy as np


from datetime import datetime

API_KEY = ""
API_SECRET = ""
BASE_URL = ""

ALPACA_CREDS = {
    "API_KEY": API_KEY,
    "API_SECRET":API_SECRET,
    "PAPER": True
}

class MLTrader(Strategy):
    def initialize(self, symbol:str="SPY", cash_at_risk:float=.5, atr_period: int=14):
        self.symbol = symbol
        self.sleeptime = '24H'
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.atr_period = atr_period
        self.api = REST(base_url=BASE_URL,key_id = API_KEY, secret_key=API_SECRET)

    def calculate_true_range(self, period: int):
        self = self.sort_index()
        historical_data = self.get_historical_prices_for_assets(self.symbol, period + 1, "day")
        high_prices = np.array([bar.h for bar in historical_data])
        low_prices = np.array([bar.l for bar in historical_data])
        close_prices = np.array([bar.c for bar in historical_data[:-1]])

        tr1 = high_prices[1:] - low_prices[1:]
        tr2 = np.abs(high_prices[1:] - close_prices)
        tr3 = np.abs(low_prices[1:] - close_prices)
        
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        atr = np.mean(true_range[-period:])
        return atr
    
    def position_sizing(self,  volatility_adjusted: bool = True):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0)
        return cash,last_price,quantity
    
    def adjusted_cash_at_risk(self,atr, base_risk_percentage: float = 0.5):
        if atr is None:
            return self.cash_at_risk
        risk_factor = 1/atr
        adjusted_cash_at_risk = base_risk_percentage * risk_factor

        return min(max(adjusted_cash_at_risk,0.1),base_risk_percentage)
    
    def get_dates(self):
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')
    
    def get_sentiment(self):
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, start=three_days_prior, end= today)
        news = [ev.__dict__["raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment

    def get_moving_averages(self, period_short=50, period_long=200):
        # Fetch historical price data from Alpaca API
        today = self.get_datetime()
        start_date = today - Timedelta(days=period_long + 10)  # Get more days to calculate the MAs
        historical_data = self.api.get_barset(self.symbol, 'day', start=start_date.strftime('%Y-%m-%d'), end=today.strftime('%Y-%m-%d'))[self.symbol]
        
        # Extract the closing prices
        closes = [bar.c for bar in historical_data]
        
        # Check if we have enough data for both MAs
        if len(closes) >= period_long:
            short_ma = sum(closes[-period_short:]) / period_short
            long_ma = sum(closes[-period_long:]) / period_long
            return short_ma, long_ma
        else:
            return None, None

    def check_ma_crossover(self):
        short_ma, long_ma = self.get_moving_averages()

        if short_ma is None or long_ma is None:
            return None  # Not enough data

        # Detect crossovers
        if short_ma > long_ma:
            return "bullish"  # Buy signal
        elif short_ma < long_ma:
            return "bearish"  # Sell signal
        else:
            return None

    def on_trading_iteration(self):
        atr = self.calculate_atr(self.atr_period)
        self.cash_at_risk = self.adjust_cash_at_risk(atr)
        cash, last_price, quantity = self.position_sizing()
        probability, sentiment = self.get_sentiment()
        crossover_signal = self.check_ma_crossover()
        if cash > last_price:
            if crossover_signal == "bullish" and sentiment == "positive"  and probability > .999:
                if self.last_trade == "sell":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "buy",
                    type="bracket",
                    take_profit_price = last_price*1.20,
                    stop_loss_price = last_price *.95
                    )
                self.submit_order(order)
                self.last_trade = "buy"
            elif crossover_signal == "bearish" and sentiment == "negative"  and probability > .999:
                if self.last_trade == "buy":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "sell",
                    type="bracket",
                    take_profit_price = last_price*.8,
                    stop_loss_price = last_price *1.05
                    )
                self.submit_order(order)
                self.last_trade = "sell"

start_date = datetime(2024,8,1)
end_date = datetime(2024,8,31)

broker = Alpaca(ALPACA_CREDS)
strategy = MLTrader(name='mlstrat', broker=broker,
                    parameters={"symbol":"SPY", "cash_at_risk":.5})
strategy.backtest(
    YahooDataBackTesting,
    start_date,
    end_date,
    parameters={"symbol":"SPY", "cash_at_risk":.5}
)