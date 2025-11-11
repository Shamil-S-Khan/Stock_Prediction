import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from pmdarima import auto_arima
from pymongo import MongoClient
from datetime import datetime
from sklearn.metrics import root_mean_squared_error, mean_absolute_percentage_error
import os
import sys
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import model_manager
import evaluation

# --- Configuration from config.py ---
CRYPTO_DATA_FILE = config.CRYPTO_DATA_FILE
MONGO_URI = config.MONGO_URI
DB_NAME = config.DB_NAME
PRED_COLLECTION = config.PRED_COLLECTION

def train_arima():
    # ===== LOAD DATA =====
    df = pd.read_csv(CRYPTO_DATA_FILE, parse_dates=["timestamp"], on_bad_lines='skip')
    df = df.sort_values("timestamp")
    series = df["Close"]
    series.index = df["timestamp"]
    original_series = series.copy()
    series = np.log(series)

    # ===== LOAD LATEST MODEL OR FIND PARAMS =====
    latest_model, latest_meta = model_manager.load_latest_model('arima')
    order = None
    if latest_meta:
        order = tuple(latest_meta['hyperparameters']['order'])
        print(f"Loaded best order {order} from previous model.")

    if order is None:
        print("No previous model found or order not specified. Running auto_arima...")
        model_auto = auto_arima(series, seasonal=False, trace=True, suppress_warnings=True, stepwise=True)
        order = model_auto.order
        print("Best ARIMA order found:", order)

    # ===== TRAIN-TEST SPLIT =====
    split = int(0.8 * len(series))
    train, test = series[:split], series[split:]
    original_train, original_test = original_series[:split], original_series[split:]

    # ===== FIT MODEL =====
    model = ARIMA(train, order=order)
    fit = model.fit()
    print(fit.summary())

    # ===== FORECAST =====
    forecast_steps = 72
    log_forecast = fit.forecast(steps=forecast_steps)
    forecast = np.exp(log_forecast)

    forecast_index = pd.date_range(original_series.index[-1], periods=forecast_steps+1, freq='H')[1:]
    forecast_df = pd.DataFrame({"timestamp": forecast_index, "predicted_close": forecast.values})
    print(forecast_df)

    # ===== LOG PREDICTIONS TO CSV =====
    for idx, row in forecast_df.iterrows():
        evaluation.log_prediction(
            timestamp=row['timestamp'],
            horizon=f"{idx+1}h", # Simple horizon based on step
            model_type='arima',
            predicted_value=row['predicted_close'],
            symbol="BTC-USD"
        )

    # ===== EVALUATION =====
    log_pred_test = fit.forecast(steps=len(test))
    pred_test = np.exp(log_pred_test)
    rmse = root_mean_squared_error(original_test, pred_test)
    mape = mean_absolute_percentage_error(original_test, pred_test)
    print("ARIMA RMSE:", rmse)
    print("ARIMA MAPE:", mape)

    # ===== SAVE MODEL VERSION =====
    metrics = {'rmse': rmse, 'mape': mape}
    params = {'order': order}
    data_range = {'start': df['timestamp'].min().isoformat(), 'end': df['timestamp'].max().isoformat()}
    model_manager.save_model_version(fit, 'arima', metrics, params, data_range)

    # ===== SAVE PREDICTIONS TO MONGODB =====
    client = MongoClient("mongodb+srv://i222451:i222451@cluster0.z2egq.mongodb.net/")
    db = client["forecast"]
    col_pred = db["predictions"]

    for t, val in zip(forecast_index, forecast):
        doc = {
            "model": "ARIMA",
            "symbol": "BTC-USD",
            "timestamp": t.to_pydatetime(),
            "predicted_close": float(val),
            "created_at": datetime.today()
        }
        col_pred.update_one(
            {"timestamp": doc["timestamp"], "model": "ARIMA"},
            {"$set": doc},
            upsert=True
        )

if __name__ == "__main__":
    train_arima()