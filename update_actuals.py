import pandas as pd
import yfinance as yf
import os
import logging
from datetime import timedelta, datetime, timezone
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_missing_actuals(symbol="BTC-USD"):
    """
    Reads predictions.csv, finds rows with missing actual_price,
    and fetches the historical price from crypto_data.csv or yfinance to fill them in.
    """
    if not os.path.exists(config.PREDICTIONS_FILE):
        logging.info(f"Predictions file not found: {config.PREDICTIONS_FILE}. Nothing to update.")
        return

    logging.info("Reading predictions.csv...")
    df = pd.read_csv(config.PREDICTIONS_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df['predicted_price'] = pd.to_numeric(df['predicted_price'], errors='coerce')
    df.dropna(subset=['predicted_price'], inplace=True)

    # Filter for rows where actual_price is missing and the timestamp is in the past
    missing_actuals = df[df['actual_price'].isna() & (df['timestamp'] < pd.Timestamp.now(tz='UTC'))]
    
    if missing_actuals.empty:
        logging.info("No missing actual prices to update.")
        return

    logging.info(f"Found {len(missing_actuals)} predictions with missing actual prices.")

    # First, try to get actuals from local crypto_data.csv
    if os.path.exists(config.CRYPTO_DATA_FILE):
        logging.info("Checking crypto_data.csv for actual prices...")
        try:
            crypto_df = pd.read_csv(config.CRYPTO_DATA_FILE, on_bad_lines='skip')
            crypto_df['timestamp'] = pd.to_datetime(crypto_df['timestamp'], utc=True, errors='coerce')
            crypto_df = crypto_df.dropna(subset=['timestamp']).set_index('timestamp')
            
            for index, row in missing_actuals.iterrows():
                target_timestamp = row['timestamp']
                
                # Try to find matching timestamp in crypto_data
                if target_timestamp in crypto_df.index:
                    actual_price = crypto_df.loc[target_timestamp, 'Close']
                    df.loc[index, 'actual_price'] = actual_price
                    df.loc[index, 'error'] = row['predicted_price'] - actual_price
                    logging.info(f"✓ Updated {target_timestamp} with actual ${actual_price:.2f} from crypto_data.csv")
        except Exception as e:
            logging.warning(f"Could not read crypto_data.csv: {e}. Will use yfinance instead.")
    
    # Re-check for still missing actuals and fetch from yfinance if needed
    still_missing = df[df['actual_price'].isna() & (df['timestamp'] < pd.Timestamp.now(tz='UTC'))]
    
    if not still_missing.empty:
        logging.info(f"Fetching {len(still_missing)} remaining actuals from yfinance...")
        min_date = still_missing['timestamp'].min().date() - timedelta(days=1)
        max_date = still_missing['timestamp'].max().date() + timedelta(days=1)

        try:
            hist_data = yf.download(symbol, start=min_date, end=max_date, interval="1h", progress=False)
            if not hist_data.empty:
                hist_data.index = pd.to_datetime(hist_data.index, utc=True)
                
                for index, row in still_missing.iterrows():
                    target_timestamp = row['timestamp']
                    
                    try:
                        if 'Close' in hist_data.columns:
                            actual_price = hist_data.loc[target_timestamp, 'Close']
                        else:
                            actual_price = hist_data.loc[target_timestamp, ('Close', symbol)]
                        
                        df.loc[index, 'actual_price'] = actual_price
                        df.loc[index, 'error'] = row['predicted_price'] - actual_price
                        logging.info(f"Updated {target_timestamp} with actual ${actual_price:.2f} from yfinance")
                    except KeyError:
                        logging.warning(f"Could not find matching price for {target_timestamp}")
        except Exception as e:
            logging.error(f"Error fetching data from yfinance: {e}")

    # Save the updated dataframe back to the CSV
    df.to_csv(config.PREDICTIONS_FILE, index=False)
    logging.info("Successfully updated predictions.csv with actual prices.")

if __name__ == "__main__":
    update_missing_actuals()
