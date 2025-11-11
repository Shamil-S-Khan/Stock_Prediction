import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error
from datetime import datetime, timedelta
from pymongo import MongoClient
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
SYMBOL = "BTC-USD" # Still hardcoded, as config doesn't have a single symbol
SEQ_LEN = 72 # Still hardcoded, as config doesn't have this
HORIZON = 72 # Still hardcoded, as config doesn't have this

def train_lstm():
    # ===== LOAD DATA =====
    df = pd.read_csv(CRYPTO_DATA_FILE, parse_dates=["timestamp"], on_bad_lines='skip')
    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")

    series = df["Close"].values.reshape(-1, 1)

    # ===== SCALE DATA =====
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_series = scaler.fit_transform(series)

    # ===== LOAD LATEST MODEL =====
    latest_model, latest_meta = model_manager.load_latest_model('lstm')

    # ===== CREATE SEQUENCES =====
    def create_sequences_multistep(data, seq_len, horizon):
        X, y = [], []
        for i in range(len(data) - seq_len - horizon):
            X.append(data[i:i+seq_len])
            y.append(data[i+seq_len:i+seq_len+horizon].flatten())
        return np.array(X), np.array(y)

    X, y = create_sequences_multistep(scaled_series, SEQ_LEN, HORIZON)

    # ===== DECIDE ON FULL RETRAIN VS FINE-TUNE =====
    if latest_model is None:
        print("No previous LSTM model found. Training from scratch.")
        X_train, y_train = X, y
        model = Sequential([
            LSTM(100, return_sequences=True, input_shape=(SEQ_LEN, 1)),
            Dropout(0.2),
            LSTM(100, return_sequences=False),
            Dropout(0.2),
            Dense(50, activation='relu'),
            Dense(HORIZON)
        ])
        model.compile(optimizer="adam", loss="mse")
    else:
        print("Previous LSTM model found. Fine-tuning on new data.")
        model = latest_model
        # Find how much new data we have since the last model was trained
        last_train_date = pd.to_datetime(latest_meta['data_range']['end'])
        new_data_df = df[df.index > last_train_date]
        
        if len(new_data_df) < (SEQ_LEN + HORIZON):
            print("Not enough new data to fine-tune. Skipping training.")
            return # Exit if not enough new data

        new_series = new_data_df["Close"].values.reshape(-1, 1)
        scaled_new_series = scaler.transform(new_series) # Use existing scaler
        X_train, y_train = create_sequences_multistep(scaled_new_series, SEQ_LEN, HORIZON)
        print(f"Fine-tuning on {len(X_train)} new sequences.")

    # ===== TRAIN OR FINE-TUNE =====
    if len(X_train) > 0:
        model.fit(
            X_train, y_train,
            epochs=10, # Fewer epochs for fine-tuning
            batch_size=32,
            verbose=1
        )

    # ===== EVALUATION (on the last 10% of the full dataset) =====
    split = int(0.9 * len(X))
    X_test, y_test = X[split:], y[split:]
    y_pred_scaled = model.predict(X_test)
    y_test_actual = scaler.inverse_transform(y_test)
    y_pred_actual = scaler.inverse_transform(y_pred_scaled)
    rmse = np.sqrt(mean_squared_error(y_test_actual[:, 0], y_pred_actual[:, 0]))
    mape = mean_absolute_percentage_error(y_test_actual[:, 0], y_pred_actual[:, 0])
    print("LSTM RMSE:", rmse)
    print("LSTM MAPE:", mape)

    # ===== SAVE MODEL VERSION =====
    metrics = {'rmse': rmse, 'mape': mape}
    params = {'seq_len': SEQ_LEN, 'horizon': HORIZON}
    data_range = {'start': df.index.min().isoformat(), 'end': df.index.max().isoformat()}
    model_manager.save_model_version(model, 'lstm', metrics, params, data_range)

    # ===== PREDICT FUTURE & LOG TO CSV =====
    last_sequence = scaled_series[-SEQ_LEN:].reshape(1, SEQ_LEN, 1)
    future_preds_scaled = model.predict(last_sequence)
    future_preds = scaler.inverse_transform(future_preds_scaled).flatten()

    last_timestamp = df.index[-1]
    for i, pred_val in enumerate(future_preds):
        pred_time = last_timestamp + timedelta(hours=i + 1)
        evaluation.log_prediction(
            timestamp=pred_time,
            horizon=f"{i+1}h",
            model_type='lstm',
            predicted_value=pred_val,
            symbol=SYMBOL
        )

    # ===== SAVE PREDICTIONS TO MONGODB (Optional, can be removed if CSV is primary) =====
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col_pred = db[PRED_COLLECTION]
    col_pred.delete_many({"model": "LSTM", "symbol": SYMBOL})

    last_timestamp = df.index[-1]
    predictions_to_save = []
    for i, pred_val in enumerate(future_preds):
        pred_time = last_timestamp + timedelta(hours=i + 1)
        doc = {
            "model": "LSTM",
            "symbol": SYMBOL,
            "timestamp": pred_time,
            "predicted_close": float(pred_val),
            "created_at": datetime.today()
        }
        predictions_to_save.append(doc)

    if predictions_to_save:
        col_pred.insert_many(predictions_to_save)
        print(f"Saved {len(predictions_to_save)} new LSTM predictions to MongoDB.")

if __name__ == "__main__":
    train_lstm()