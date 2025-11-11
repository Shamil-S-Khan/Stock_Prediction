"""
Quick script to populate actual prices from crypto_data.csv
Handles malformed CSV by using only the first 6 columns
"""
import pandas as pd
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def populate_actuals_from_crypto_data():
    """Populate actual prices from crypto_data.csv, handling malformed rows"""
    
    if not os.path.exists(config.PREDICTIONS_FILE):
        print(f"Predictions file not found: {config.PREDICTIONS_FILE}")
        return
    
    # Read predictions
    print("Reading predictions.csv...")
    pred_df = pd.read_csv(config.PREDICTIONS_FILE)
    pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'], utc=True, format='mixed', errors='coerce')
    pred_df = pred_df.dropna(subset=['timestamp'])
    
    # Count missing actuals
    missing_count = pred_df['actual_price'].isna().sum()
    print(f"Found {missing_count} predictions with missing actual prices")
    
    if missing_count == 0:
        print("No missing actuals to update!")
        return
    
    # Read crypto_data with specific columns to avoid malformed row issues
    if not os.path.exists(config.CRYPTO_DATA_FILE):
        print(f"Crypto data file not found: {config.CRYPTO_DATA_FILE}")
        return
        
    print("Reading crypto_data.csv...")
    # Use usecols to only read the columns we need
    crypto_df = pd.read_csv(
        config.CRYPTO_DATA_FILE, 
        usecols=['timestamp', 'Close'],
        on_bad_lines='skip'
    )
    crypto_df['timestamp'] = pd.to_datetime(crypto_df['timestamp'], utc=True, errors='coerce')
    crypto_df = crypto_df.dropna(subset=['timestamp'])
    # Remove duplicates, keep last
    crypto_df = crypto_df.drop_duplicates(subset=['timestamp'], keep='last')
    crypto_df = crypto_df.set_index('timestamp')
    
    print(f"Crypto data has {len(crypto_df)} unique rows")
    
    # Update actuals
    updated = 0
    for idx, row in pred_df.iterrows():
        if pd.isna(row['actual_price']):
            ts = row['timestamp']
            if ts in crypto_df.index:
                actual = float(crypto_df.loc[ts, 'Close'])
                pred_value = float(row['predicted_price'])
                pred_df.at[idx, 'actual_price'] = actual
                pred_df.at[idx, 'error'] = pred_value - actual
                updated += 1
                if updated % 50 == 0:
                    print(f"Updated {updated} predictions...")
    
    # Save
    pred_df.to_csv(config.PREDICTIONS_FILE, index=False)
    print(f"✓ Successfully updated {updated} predictions with actual prices!")
    print(f"  Remaining missing: {pred_df['actual_price'].isna().sum()}")

if __name__ == "__main__":
    populate_actuals_from_crypto_data()
