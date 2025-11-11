"""
Fetch the last 7 days of hourly data to populate crypto_data.csv
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

def fetch_recent_data(symbol="BTC-USD", days=7):
    """Fetch recent hourly data and append to crypto_data.csv"""
    
    print(f"Fetching {days} days of hourly data for {symbol}...")
    
    try:
        # Fetch data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=f"{days}d", interval="1h")
        
        if data.empty:
            print("No data returned from yfinance")
            return
        
        # Prepare data
        data.index.name = 'timestamp'
        data = data.reset_index()
        data = data[['timestamp', 'Close', 'High', 'Low', 'Open', 'Volume']]
        
        # Ensure timezone aware
        data['timestamp'] = pd.to_datetime(data['timestamp'], utc=True)
        
        print(f"Fetched {len(data)} rows")
        
        # Read existing data if it exists
        if os.path.exists(config.CRYPTO_DATA_FILE):
            existing = pd.read_csv(config.CRYPTO_DATA_FILE, usecols=['timestamp', 'Close', 'High', 'Low', 'Open', 'Volume'], on_bad_lines='skip')
            existing['timestamp'] = pd.to_datetime(existing['timestamp'], utc=True, errors='coerce')
            existing = existing.dropna(subset=['timestamp'])
            
            # Combine and remove duplicates
            combined = pd.concat([existing, data])
            combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
            combined = combined.sort_values('timestamp')
            
            # Save
            combined.to_csv(config.CRYPTO_DATA_FILE, index=False)
            print(f"✓ Updated crypto_data.csv with {len(combined)} total rows ({len(data)} new)")
        else:
            data.to_csv(config.CRYPTO_DATA_FILE, index=False)
            print(f"✓ Created crypto_data.csv with {len(data)} rows")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_recent_data()
