import yfinance as yf
import pandas as pd
import os

# Define file path
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "crypto_data.csv")

# Fetch 30 days of hourly BTC-USD data
print("Fetching 30 days of BTC-USD hourly data...")
data = yf.download("BTC-USD", period="7d", interval="1h")

# Make sure it has the correct column names
data.index.name = "timestamp"
data.reset_index(inplace=True)

# Create data directory if missing
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

# Save to CSV
data.to_csv(CSV_PATH, index=False)
print(f"Saved {len(data)} rows to {CSV_PATH}")

# Display a preview
print(data.head())
