import pandas as pd
from sklearn.metrics import root_mean_squared_error, mean_absolute_percentage_error

df = pd.read_csv("arima_hourly.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp")
series = df["close"]

window = 3  # you can test 3, 5, 10
predictions = series.rolling(window).mean().shift(1).dropna()
actuals = series[window:]

rmse = root_mean_squared_error(actuals, predictions)
mape = mean_absolute_percentage_error(actuals, predictions)

print(f"Moving Average (window={window}) RMSE: {rmse:.2f}")
print(f"Moving Average (window={window}) MAPE: {mape*100:.2f}%")
