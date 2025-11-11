import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timezone
import config

# --- Configuration from config.py ---
STATE_FILE = config.PORTFOLIO_STATE_FILE
HISTORY_FILE = config.PORTFOLIO_HISTORY_FILE
TRANSACTIONS_FILE = config.TRANSACTIONS_FILE
INITIAL_CASH = config.INITIAL_CASH
BUY_THRESHOLD_PCT = config.BUY_THRESHOLD_PCT
SELL_THRESHOLD_PCT = config.SELL_THRESHOLD_PCT
PREDICTIONS_FILE = config.PREDICTIONS_FILE # Needed for run_live_trading_strategy
PORTFOLIO_HISTORICAL_VALUES_FILE = config.PORTFOLIO_HISTORICAL_VALUES_FILE

class Portfolio:
    def __init__(self, initial_cash=10000):
        self.cash = initial_cash
        self.holdings = {}  # {symbol: quantity}
        self.transactions = []
        self._load_state()

    def _load_state(self):
        """Loads portfolio state from JSON file."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.cash = state.get('cash', self.cash)
                    self.holdings = state.get('holdings', self.holdings)
                print("Successfully loaded portfolio state.")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading state file or file is empty, starting fresh: {e}")
        else:
            print("No state file found, starting with a fresh portfolio.")
        
        if os.path.exists(TRANSACTIONS_FILE):
            self.transactions = pd.read_csv(TRANSACTIONS_FILE).to_dict('records')

    def _save_state(self):
        """Saves the current portfolio state to JSON."""
        state = {'cash': self.cash, 'holdings': self.holdings}
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)

    def _log_transaction(self, symbol, transaction_type, quantity, price_per_unit, total_value, timestamp=None):
        """Logs a transaction to the transactions CSV file."""
        new_transaction = {
            'timestamp': timestamp or datetime.now().isoformat(),
            'symbol': symbol,
            'type': transaction_type,
            'quantity': quantity,
            'price_per_unit': price_per_unit,
            'total_value': total_value
        }
        
        df = pd.DataFrame([new_transaction])
        if not os.path.exists(TRANSACTIONS_FILE):
            df.to_csv(TRANSACTIONS_FILE, index=False)
        else:
            df.to_csv(TRANSACTIONS_FILE, mode='a', header=False, index=False)
        
        self.transactions.append(new_transaction)

    def buy(self, symbol, amount_usd, current_price, timestamp=None):
        """Executes a buy order."""
        if self.cash < amount_usd:
            print(f"Insufficient cash to buy ${amount_usd} of {symbol}. Cash available: ${self.cash:.2f}")
            return False
        
        quantity = amount_usd / current_price
        self.cash -= amount_usd
        self.holdings[symbol] = self.holdings.get(symbol, 0) + quantity
        
        self._log_transaction(symbol, 'BUY', quantity, current_price, amount_usd, timestamp)
        self._save_state()
        print(f"BOUGHT: {quantity:.6f} {symbol} for ${amount_usd:.2f}")
        return True

    def sell(self, symbol, quantity, current_price, timestamp=None):
        """Executes a sell order."""
        if symbol not in self.holdings or self.holdings[symbol] < quantity:
            print(f"Insufficient holdings to sell {quantity} of {symbol}. Holdings: {self.holdings.get(symbol, 0)}")
            return False
            
        sale_value = quantity * current_price
        self.cash += sale_value
        self.holdings[symbol] -= quantity
        
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
            
        self._log_transaction(symbol, 'SELL', quantity, current_price, sale_value, timestamp)
        self._save_state()
        print(f"SOLD: {quantity:.6f} {symbol} for ${sale_value:.2f}")
        return True

    def get_portfolio_value(self, current_prices):
        """Calculates the total current value of the portfolio."""
        holdings_value = 0
        for symbol, quantity in self.holdings.items():
            holdings_value += quantity * current_prices.get(symbol, 0)
        return self.cash + holdings_value

    def record_historical_value(self, current_prices, timestamp=None):
        """Records the total portfolio value at a point in time."""
        value = self.get_portfolio_value(current_prices)
        new_record = pd.DataFrame([{
            'timestamp': timestamp or datetime.now().isoformat(),
            'portfolio_value': value
        }])
        if not os.path.exists(config.PORTFOLIO_HISTORICAL_VALUES_FILE):
            new_record.to_csv(config.PORTFOLIO_HISTORICAL_VALUES_FILE, index=False)
        else:
            new_record.to_csv(config.PORTFOLIO_HISTORICAL_VALUES_FILE, mode='a', header=False, index=False)



    def get_portfolio_history(self):
        if not os.path.exists(HISTORY_FILE):
            return None
        return pd.read_csv(HISTORY_FILE, parse_dates=['timestamp'])

    def get_transactions(self):
        if not os.path.exists(TRANSACTIONS_FILE):
            return None
        return pd.read_csv(TRANSACTIONS_FILE, parse_dates=['timestamp'])

    def get_performance_metrics(self):
        """
        Calculates key performance metrics for the portfolio.
        Returns a dictionary of metrics.
        """
        history_df = self.get_portfolio_history()
        
        # Default metrics if not enough data
        default_metrics = {
            'total_return': 0.0,
            'annualized_return': 0.0,
            'annualized_volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }

        if history_df is None or len(history_df) < 2:
            return default_metrics

        try:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp').set_index('timestamp')

            returns = history_df['value'].pct_change().dropna()

            if returns.empty:
                return default_metrics

            # --- Calculations ---
            total_return = (history_df['value'].iloc[-1] / history_df['value'].iloc[0]) - 1
            
            # Annualized Return
            total_days = (history_df.index[-1] - history_df.index[0]).days
            annualized_return = ((1 + total_return) ** (365.0 / total_days)) - 1 if total_days > 0 else 0

            # Annualized Volatility
            annualized_volatility = returns.std() * np.sqrt(252 * 24) # Assuming 24h data, 252 trading days

            # Sharpe Ratio
            risk_free_rate = 0.02 # Assume 2% annual risk-free rate
            annualized_risk_free_rate = (1 + risk_free_rate)**(1/(252*24)) - 1
            sharpe_ratio = (returns.mean() - annualized_risk_free_rate) / returns.std() if returns.std() > 0 else 0
            sharpe_ratio = sharpe_ratio * np.sqrt(252 * 24) # Annualize Sharpe

            # Max Drawdown
            max_drawdown = (history_df['value'] / history_df['value'].cummax() - 1).min()

            # Explicitly cast all return values to float to ensure JSON serializability
            return {
                'total_return': float(total_return),
                'annualized_return': float(annualized_return),
                'annualized_volatility': float(annualized_volatility),
                'sharpe_ratio': float(sharpe_ratio),
                'max_drawdown': float(max_drawdown)
            }

        except Exception as e:
            print(f"Error calculating performance metrics: {e}")
            return default_metrics

def run_live_trading_strategy(current_price, symbol="BTC-USD"):
    """
    Executes the trading strategy based on the latest 24-hour prediction and live price.
    """
    print("\nRunning LIVE trading strategy...")
    
    predictions_file_path = os.path.join(os.path.dirname(__file__), 'data', 'predictions.csv')

    # Gracefully handle missing predictions file
    if not os.path.exists(predictions_file_path):
        print("No predictions file found. Holding position until next model run.")
        return

    # 1. Get the latest 24h prediction for the given symbol
    predictions_df = pd.read_csv(predictions_file_path, parse_dates=['timestamp'])
    
    if predictions_df.empty:
        print("Predictions file is empty. Holding position.")
        return

    print(f"DEBUG: Columns in predictions_df: {predictions_df.columns.tolist()}") # DEBUG LINE
    latest_pred = predictions_df[
        (predictions_df['model_type'] == 'arima') & # or your preferred model
        (predictions_df['horizon'] == '24h') & 
        (predictions_df['symbol'] == symbol)
    ].sort_values('timestamp', ascending=False).iloc[0]
    
    if latest_pred is None:
        print("No recent 24h prediction found. Holding.")
        return

    predicted_price = latest_pred['predicted_price']
    predicted_change_pct = (predicted_price - current_price) / current_price

    print(f"Latest 24h prediction for {symbol}: ${predicted_price:.2f}")
    print(f"Current price for {symbol}: ${current_price:.2f}")
    print(f"Predicted change: {predicted_change_pct*100:.2f}%")

    portfolio = Portfolio()

    # Decide and execute
    if predicted_change_pct > 0.02:
        buy_amount_usd = portfolio.cash * 0.10 # Invest 10% of cash
        if buy_amount_usd > 10:
            portfolio.buy(symbol, buy_amount_usd, current_price)
    elif predicted_change_pct < -0.02:
        if symbol in portfolio.holdings:
            sell_quantity = portfolio.holdings[symbol] * 0.25 # Sell 25% of holding
            portfolio.sell(symbol, sell_quantity, current_price)
    else:
        print("HOLD: Predicted change is within the +/-2% threshold.")

    # Record portfolio value
    portfolio.record_historical_value({symbol: current_price})
    print(f"Portfolio Value: ${portfolio.get_portfolio_value({symbol: current_price}):.2f}")


def backtest_strategy():
    """
    Backtests the trading strategy on historical predictions.
    This is a simplified example and would need to be more robust.
    """
    print("\n--- Running Backtest ---")
    
    # Load historical predictions and actual prices
    predictions_df = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data', 'predictions.csv'), parse_dates=['timestamp'])
    actuals_df = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data', 'crypto_data.csv'), parse_dates=['timestamp'], on_bad_lines='skip')
    
    # For simplicity, let's focus on the 24h ARIMA predictions for BTC-USD
    strategy_df = predictions_df[
        (predictions_df['model_type'] == 'arima') & 
        (predictions_df['horizon'] == '24h')
    ].copy()
    
    # We need the actual price at the time of prediction to decide, and the price 24h later to see the result
    # This requires careful merging
    strategy_df['timestamp'] = strategy_df['timestamp'].dt.round('H')
    actuals_df['timestamp'] = actuals_df['timestamp'].dt.round('H')

    # Merge to get the price at the time of prediction
    merged_df = pd.merge(strategy_df, actuals_df[['timestamp', 'Close']], on='timestamp', how='inner')
    merged_df.rename(columns={'Close': 'price_at_prediction'}, inplace=True)

    # Calculate the predicted price change percentage
    merged_df['predicted_change_pct'] = (merged_df['predicted_price'] - merged_df['price_at_prediction']) / merged_df['price_at_prediction']

    # Simulate portfolio
    backtest_portfolio = Portfolio(initial_cash=10000)
    
    for index, row in merged_df.iterrows():
        current_price = row['price_at_prediction']
        symbol = "BTC-USD" # Assuming BTC-USD for now
        
        print(f"\nDate: {row['timestamp']}, Price: ${current_price:.2f}")
        
        if row['predicted_change_pct'] > 0.02:
            buy_amount = backtest_portfolio.cash * 0.1
            if buy_amount > 10:
                backtest_portfolio.buy(symbol, buy_amount, current_price, timestamp=row['timestamp'])
        elif row['predicted_change_pct'] < -0.02:
            if symbol in backtest_portfolio.holdings:
                sell_quantity = backtest_portfolio.holdings[symbol] * 0.25
                backtest_portfolio.sell(symbol, sell_quantity, current_price, timestamp=row['timestamp'])
        else:
            print("HOLD signal.")
            
        # Log value for performance calculation
        backtest_portfolio.record_historical_value({symbol: current_price}, timestamp=row['timestamp'])

    print("\n--- Backtest Complete ---")
    final_value = backtest_portfolio.get_portfolio_value({symbol: merged_df['price_at_prediction'].iloc[-1]})
    print(f"Initial Portfolio Value: $10,000.00")
    print(f"Final Portfolio Value: ${final_value:.2f}")
    
    # Note: The performance metrics would be based on the backtest's historical value file.
    # For a proper backtest, you'd clear the file first.
    
if __name__ == '__main__':
    # Example of how to run the strategy
    # run_trading_strategy()

    # Example of how to run a backtest
    # To run a clean backtest, you might want to clear the state files first
    if os.path.exists(PORTFOLIO_HISTORICAL_VALUES_FILE):
        os.remove(PORTFOLIO_HISTORICAL_VALUES_FILE)
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    if os.path.exists(TRANSACTIONS_FILE):
        os.remove(TRANSACTIONS_FILE)
        
    backtest_strategy()