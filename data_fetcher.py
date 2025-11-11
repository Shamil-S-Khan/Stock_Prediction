import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import os
import logging
import subprocess
import sys
import time
import config
import argparse
import evaluation
from portfolio import run_live_trading_strategy
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration from config.py ---
CRYPTO_DATA_FILE = config.CRYPTO_DATA_FILE
NEW_ROWS_COUNT_FILE = config.NEW_ROWS_COUNT_FILE
RETRAIN_THRESHOLD = config.RETRAIN_THRESHOLD
RETRAIN_TIMESTAMP_FILE = config.RETRAIN_TIMESTAMP_FILE
MODEL_TYPES = config.MODEL_TYPES

def fetch_data(symbol="BTC-USD", interval="1h"):
    """Fetches the latest hourly data for a given ticker."""
    ticker = symbol
    try:
        logging.info(f"Fetching latest data for {ticker}...")
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="1h")
        if not data.empty:
            data.index.name = 'timestamp'
            return data.iloc[[-1]]  # Only the most recent completed hour
        return None
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return None

def append_to_csv(data):
    """Appends new data to the CSV file."""
    try:
        if os.path.exists(config.CRYPTO_DATA_FILE):
            # Append without header
            data.to_csv(config.CRYPTO_DATA_FILE, mode='a', header=False)
        else:
            # Create new file with header
            data.to_csv(config.CRYPTO_DATA_FILE, mode='w', header=True)
        logging.info(f"Appended 1 new row to {config.CRYPTO_DATA_FILE}")
        return 1
    except Exception as e:
        logging.error(f"Error appending to CSV: {e}")
        return 0

def trigger_retraining():
    """Triggers the model retraining scripts and resets the new row counter."""
    logging.info("Triggering model retraining...")
    try:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'model', 'arima_model.py')], check=True)
        logging.info("ARIMA model retraining complete.")

        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'model', 'lstm_model.py')], check=True)
        logging.info("LSTM model retraining complete.")

        # Reset the new rows counter
        with open(NEW_ROWS_COUNT_FILE, "w") as f:
            f.write("0")
        logging.info("Retraining complete. New row counter reset.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during model retraining: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during retraining: {e}")

def scheduled_job():
    """The main job to be scheduled."""
    logging.info("Running scheduled job...")
    new_data = fetch_data()
    if new_data is not None and not new_data.empty:
        # Update predictions with actual values
        actual_timestamp = new_data.index[0]
        actual_price = new_data['Close'].iloc[0]
        symbol = "BTC-USD" # Assuming BTC-USD for now, can be made dynamic
        evaluation.update_with_actual(actual_timestamp, actual_price, symbol)

        rows_appended = append_to_csv(new_data)

        # Run evaluation
        evaluation.run_evaluation(symbol)

        # Run trading strategy with the new price
        run_live_trading_strategy(current_price=actual_price, symbol="BTC-USD")
        
        # Update the persistent counter
        try:
            current_count = 0
            if os.path.exists(NEW_ROWS_COUNT_FILE):
                with open(NEW_ROWS_COUNT_FILE, 'r') as f:
                    current_count = int(f.read())
            
            total_new_rows = current_count + rows_appended
            
            with open(NEW_ROWS_COUNT_FILE, 'w') as f:
                f.write(str(total_new_rows))
            
            logging.info(f"Data updated. New rows since last retrain: {total_new_rows}")

            if total_new_rows >= RETRAIN_THRESHOLD:
                trigger_retraining()
            else:
                logging.info(f"Not enough new data to trigger retraining. Threshold: {RETRAIN_THRESHOLD}")

        except (IOError, ValueError) as e:
            logging.error(f"Error handling new row count file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data fetcher and model retrainer.")
    parser.add_argument("--now", action="store_true", help="Run the job immediately and then exit.")
    args = parser.parse_args()

    # Ensure data directory exists
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'data')):
        os.makedirs(os.path.join(os.path.dirname(__file__), 'data'))

    if args.now:
        logging.info("Manual update triggered.")
        scheduled_job()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(scheduled_job, 'interval', hours=1)
        scheduler.start()
        logging.info("Scheduler started. Press Ctrl+C to exit.")

        try:
            while True:
                pass
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logging.info("Scheduler shut down.")