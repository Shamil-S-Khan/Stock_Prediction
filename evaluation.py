import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from datetime import datetime, timezone, timedelta
import os
import sys
import subprocess
import logging
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration from config.py ---
PREDICTIONS_FILE = config.PREDICTIONS_FILE
METRICS_FILE = config.METRICS_FILE
MAPE_THRESHOLD = config.MAPE_THRESHOLD
MAE_THRESHOLD = config.MAE_THRESHOLD
RMSE_THRESHOLD = config.RMSE_THRESHOLD

def log_prediction(timestamp, horizon, model_type, predicted_value, symbol):
    """
    Logs a new prediction to the predictions CSV file.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        df = pd.DataFrame(columns=['timestamp', 'symbol', 'horizon', 'model_type', 'predicted_price', 'actual_price', 'error'])
        df.to_csv(PREDICTIONS_FILE, index=False)

    new_prediction = pd.DataFrame({
        'timestamp': [timestamp],
        'symbol': [symbol],
        'horizon': [horizon],
        'model_type': [model_type],
        'predicted_price': [predicted_value],
        'actual_price': [None],
        'error': [None]
    })
    new_prediction.to_csv(PREDICTIONS_FILE, mode='a', header=False, index=False)

def update_with_actual(timestamp, actual_value, symbol):
    """
    Updates predictions with the actual price and calculates the error.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return

    df = pd.read_csv(PREDICTIONS_FILE)
    
    # Robustly convert to datetime, coercing errors, and removing failed rows
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True)

    # Ensure the column is timezone-aware for correct comparison
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')

    # Find predictions that match the timestamp and symbol
    target_indices = df[(df['timestamp'] == timestamp) & (df['symbol'] == symbol)].index
    
    if not target_indices.empty:
        df.loc[target_indices, 'actual_price'] = actual_value
        df.loc[target_indices, 'error'] = df.loc[target_indices, 'predicted_price'] - actual_value
        df.to_csv(PREDICTIONS_FILE, index=False)

def calculate_metrics(model_type, horizon, symbol, lookback_period_days=30):
    """
    Calculates MAE, RMSE, and MAPE for a given model and horizon over a lookback period.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return None

    df = pd.read_csv(PREDICTIONS_FILE)
    
    # Robustly convert to datetime and handle timezones
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True)
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')

    # Filter data for the specified model, horizon, symbol, and lookback period
    end_date = datetime.now(timezone.utc)
    
    start_date = end_date - timedelta(days=lookback_period_days)
    
    filtered_df = df[
        (df['model_type'] == model_type) &
        (df['horizon'] == horizon) &
        (df['symbol'] == symbol) &
        (df['timestamp'] >= start_date) &
        (df['timestamp'] <= end_date) &
        (df['actual_price'].notna())
    ]
    
    if filtered_df.empty:
        return None
        
    # Calculate metrics
    mae = mean_absolute_error(filtered_df['actual_price'], filtered_df['predicted_price'])
    mse = mean_squared_error(filtered_df['actual_price'], filtered_df['predicted_price'])
    rmse = np.sqrt(mse)
    mape = (filtered_df['error'].abs() / filtered_df['actual_price']).mean() * 100
    
    metrics = {
        'mae': mae,
        'rmse': rmse,
        'mape': mape
    }
        
    return metrics

def run_evaluation(symbol):
    """
    Runs the evaluation for all models and horizons for a given symbol.
    """
    models = ['arima', 'lstm']
    horizons = ['1h', '3h', '24h', '72h']
    retrain_needed = False
    
    for model in models:
        for horizon in horizons:
            metrics = calculate_metrics(model, horizon, symbol)
            if metrics:
                store_metrics(model, horizon, metrics, symbol)
                
                # Check if any metric exceeds threshold
                if (metrics['mape'] > MAPE_THRESHOLD or 
                    metrics['mae'] > MAE_THRESHOLD or 
                    metrics['rmse'] > RMSE_THRESHOLD):
                    
                    logging.warning(
                        f"ALERT: Metrics for {model} at horizon {horizon} for {symbol} exceed thresholds:\n"
                        f"  MAPE: {metrics['mape']:.2f}% (threshold: {MAPE_THRESHOLD}%)\n"
                        f"  MAE: {metrics['mae']:.2f} (threshold: {MAE_THRESHOLD})\n"
                        f"  RMSE: {metrics['rmse']:.2f} (threshold: {RMSE_THRESHOLD})"
                    )
                    retrain_needed = True
    
    # Trigger retraining if any model exceeded thresholds
    if retrain_needed:
        logging.info("Metric thresholds exceeded. Triggering model retraining...")
        trigger_model_retraining()

def trigger_model_retraining():
    """
    Triggers retraining of all models by running the training scripts.
    """
    try:
        logging.info("Starting ARIMA model retraining...")
        arima_path = os.path.join(os.path.dirname(__file__), 'model', 'arima_model.py')
        subprocess.run([sys.executable, arima_path], check=True)
        logging.info("ARIMA model retraining complete.")

        logging.info("Starting LSTM model retraining...")
        lstm_path = os.path.join(os.path.dirname(__file__), 'model', 'lstm_model.py')
        subprocess.run([sys.executable, lstm_path], check=True)
        logging.info("LSTM model retraining complete.")
        
        logging.info("All models retrained successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during model retraining: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during retraining: {e}")

def store_metrics(model_type, horizon, metrics, symbol=None):
    """
    Stores the calculated metrics in the metrics CSV file.
    """
    if not os.path.exists(METRICS_FILE):
        df = pd.DataFrame(columns=['timestamp', 'model_type', 'horizon', 'mae', 'rmse', 'mape', 'symbol'])
        df.to_csv(METRICS_FILE, index=False)

    new_metrics = pd.DataFrame({
        'timestamp': [datetime.now(timezone.utc)],
        'model_type': [model_type],
        'horizon': [horizon],
        'mae': [metrics['mae']],
        'rmse': [metrics['rmse']],
        'mape': [metrics['mape']],
        'symbol': [symbol]
    })
    new_metrics.to_csv(METRICS_FILE, mode='a', header=False, index=False)

def get_metric_history(model_type, horizon, symbol, metric_name, days=30):
    """
    Retrieves the history of a specific metric for a given model and horizon.
    """
    if not os.path.exists(METRICS_FILE):
        return pd.DataFrame()

    df = pd.read_csv(METRICS_FILE)
    # Parse timestamps with mixed formats (with and without timezone)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
    
    # Filter data for the specified model, horizon, symbol, and metric
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Build filter condition
    condition = (
        (df['model_type'] == model_type) &
        (df['horizon'] == horizon) &
        (df['timestamp'] >= start_date) &
        (df['timestamp'] <= end_date)
    )
    
    # Only filter by symbol if column exists, symbol is provided, and column has non-empty values
    if symbol and 'symbol' in df.columns:
        # Check if the symbol column has any non-empty values
        if df['symbol'].notna().any() and (df['symbol'] != '').any():
            condition = condition & (df['symbol'] == symbol)
    
    metric_history = df[condition][['timestamp', metric_name]]
    
    return metric_history