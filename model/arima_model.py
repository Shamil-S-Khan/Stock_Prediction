import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from pmdarima import auto_arima
from pymongo import MongoClient
from datetime import datetime
from sklearn.metrics import root_mean_squared_error, mean_absolute_percentage_error

# ===== LOAD DATA =====
df = pd.read_csv("arima_hourly.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp")
series = df["close"]
series.index = df["timestamp"]
original_series = series.copy() # Keep original data for plotting
series = np.log(series) # Log transform the data

# ===== AUTO ARIMA FOR BEST (p,d,q) =====
model_auto = auto_arima(series, seasonal=False, trace=True, suppress_warnings=True, stepwise=True)
order = model_auto.order
print("Best ARIMA order:", order)

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
forecast = np.exp(log_forecast) # Inverse transform the forecast

forecast_index = pd.date_range(original_series.index[-1], periods=forecast_steps+1, freq='H')[1:]
forecast_df = pd.DataFrame({"timestamp": forecast_index, "predicted_close": forecast.values})
print(forecast_df)

# ===== PLOT =====
plt.figure(figsize=(10,5))
plt.plot(original_series.tail(100), label='Actual') # Plot original data
plt.plot(forecast_index, forecast, label='Forecast (Next 3 Hours)', color='red', linestyle='-', marker='o', markersize=4)
plt.legend()
plt.title("ARIMA Forecast (Next 72 Hours)")
plt.xlabel("Time")
plt.ylabel("Close Price")
plt.show()

# ===== EVALUATION =====
log_pred_test = fit.forecast(steps=len(test))
pred_test = np.exp(log_pred_test) # Inverse transform for evaluation
rmse = root_mean_squared_error(original_test, pred_test)
mape = mean_absolute_percentage_error(original_test, pred_test)
print("RMSE:", rmse)
print("MAPE:", mape)

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