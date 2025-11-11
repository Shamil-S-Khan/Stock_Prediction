import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Define file paths
PREDICTIONS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'predictions.csv')
METRICS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'metrics.csv')

# Define models and horizons
models = ['arima', 'lstm']
horizons = ['1h', '3h', '24h', '72h']

# --- Generate predictions.csv ---
predictions_data = []
today = datetime.now()

for i in range(30):
    date = today - timedelta(days=i)
    for model in models:
        for horizon in horizons:
            predicted_price = 100000 + np.random.randn() * 1000
            actual_price = predicted_price + np.random.randn() * 500
            error = predicted_price - actual_price
            predictions_data.append({
                'timestamp': date,
                'horizon': horizon,
                'model_type': model,
                'predicted_price': predicted_price,
                'actual_price': actual_price,
                'error': error
            })

predictions_df = pd.DataFrame(predictions_data)
predictions_df.to_csv(PREDICTIONS_FILE, index=False)
print(f"Generated {len(predictions_df)} rows in {PREDICTIONS_FILE}")


# --- Generate metrics.csv ---
metrics_data = []

for i in range(30):
    date = today - timedelta(days=i)
    for model in models:
        for horizon in horizons:
            mae = np.random.uniform(100, 500)
            rmse = np.random.uniform(200, 700)
            mape = np.random.uniform(1, 15)
            metrics_data.append({
                'timestamp': date,
                'model_type': model,
                'horizon': horizon,
                'mae': mae,
                'rmse': rmse,
                'mape': mape
            })

metrics_df = pd.DataFrame(metrics_data)
metrics_df.to_csv(METRICS_FILE, index=False)
print(f"Generated {len(metrics_df)} rows in {METRICS_FILE}")
