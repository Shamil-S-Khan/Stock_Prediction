import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error
from datetime import datetime, timedelta
from pymongo import MongoClient

# ===== DB & MODEL CONFIG =====
MONGO_URI = "mongodb+srv://i222451:i222451@cluster0.z2egq.mongodb.net/"
DB_NAME = "forecast"
PRED_COLLECTION = "predictions"
SYMBOL = "BTC-USD"

# ===== LOAD DATA =====
df = pd.read_csv("arima_hourly.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp")
df = df.set_index("timestamp")

series = df["close"].values.reshape(-1, 1)

# ===== SCALE DATA =====
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_series = scaler.fit_transform(series)

# ===== CREATE MULTI-STEP SEQUENCES =====
def create_sequences_multistep(data, seq_len, horizon):
    X, y = [], []
    for i in range(len(data) - seq_len - horizon):
        X.append(data[i:i+seq_len])
        y.append(data[i+seq_len:i+seq_len+horizon].flatten())
    return np.array(X), np.array(y)

# Use 3 days of hourly data (72 hours) to predict the next 72 hours
SEQ_LEN = 72
HORIZON = 72
X, y = create_sequences_multistep(scaled_series, SEQ_LEN, HORIZON)

# ===== TRAIN-TEST SPLIT =====
split = int(0.9 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# ===== BUILD LSTM MODEL =====
model = Sequential([
    LSTM(100, return_sequences=True, input_shape=(SEQ_LEN, 1)),
    Dropout(0.2),
    LSTM(100, return_sequences=False),
    Dropout(0.2),
    Dense(50, activation='relu'),
    Dense(HORIZON)
])

model.compile(optimizer="adam", loss="mse")
model.summary()

# ===== TRAIN =====
history = model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=20, # Fewer epochs for faster training
    batch_size=32,
    verbose=1
)

# ===== PREDICT & INVERSE TRANSFORM =====
# Predict the future based on the last sequence from the original data
last_sequence = scaled_series[-SEQ_LEN:].reshape(1, SEQ_LEN, 1)
future_preds_scaled = model.predict(last_sequence)
future_preds = scaler.inverse_transform(future_preds_scaled).flatten()

# ===== SAVE PREDICTIONS TO MONGODB =====
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col_pred = db[PRED_COLLECTION]

col_pred.delete_many({"model": "LSTM", "symbol": SYMBOL})
print("Deleted old LSTM predictions from MongoDB.")

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

# ===== PLOT RESULTS (Optional) =====
plt.figure(figsize=(15, 7))
# Plot historical data (last 200 hours)
plt.plot(df.index[-200:], df['close'][-200:], label='Actual Price')

# Plot future predictions
pred_dates = [last_timestamp + timedelta(hours=i + 1) for i in range(len(future_preds))]
plt.plot(pred_dates, future_preds, label='LSTM Forecast (72 Hours)', color='red', linestyle='--')

plt.title(f'{SYMBOL} Price Forecast (LSTM)')
plt.xlabel('Timestamp')
plt.ylabel('Price (USD)')
plt.legend()
plt.grid(True)
plt.show()
