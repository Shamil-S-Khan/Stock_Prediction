from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

MONGO_URI = "mongodb+srv://i222451:i222451@cluster0.z2egq.mongodb.net/"
DB_NAME = "forecast"
CANDLES_COLLECTION = "candlestick_data"
PRED_COLLECTION = "predictions"

app = Flask(__name__, static_folder="static", template_folder="templates")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Normalize a pandas/NumPy/str timestamp to UTC tz-aware pandas.Timestamp
def _to_utc_timestamp(value):
    ts = pd.to_datetime(value)
    # If tz-naive, localize to UTC; if tz-aware, convert to UTC
    if getattr(ts, 'tz', None) is None:
        return ts.tz_localize('UTC')
    return ts.tz_convert('UTC')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/candles")
def api_candles():
    """
    Returns last N 5-min candles from MongoDB as JSON.
    Query params:
      - minutes (optional): how many minutes back to include (default 1440 = 1 day of 5-min candles)
    """
    minutes = int(request.args.get("minutes", 1440))
    cutoff = datetime.today() - timedelta(minutes=minutes)
    col = db[CANDLES_COLLECTION]
    cursor = col.find({"timestamp": {"$gte": cutoff}}).sort("timestamp", 1)
    rows = list(cursor)
    # Convert BSON datetimes to ISO strings for JSON
    data = [{
        "timestamp": r["timestamp"].isoformat(),
        "open": r["open"],
        "high": r["high"],
        "low": r["low"],
        "close": r["close"],
        "volume": r.get("volume", 0)
    } for r in rows]
    return jsonify(data)

def _fetch_predictions(model_name, horizon_hours, symbol, start_after=None):
    query = {"model": model_name, "symbol": symbol}
    if start_after is not None:
        # Only strictly future predictions relative to the last historical timestamp
        query["timestamp"] = {"$gt": _to_utc_timestamp(start_after)}
    cursor = db[PRED_COLLECTION].find(query).sort("timestamp", 1).limit(horizon_hours)
    rows = list(cursor)
    normalized = []
    for r in rows:
        ts = _to_utc_timestamp(r["timestamp"]).isoformat()
        normalized.append({
            "timestamp": ts,
            "predicted_close": float(r["predicted_close"]) if r.get("predicted_close") is not None else None
        })
    return normalized

@app.route("/api/predictions")
def api_predictions():
    """
    Return predictions for a given model and horizon.
    Query params:
      - model: "ARIMA", "LSTM", or "MA"
      - horizon: "1h","3h","24h","72h" (used by frontend for labels)
      - symbol: optional symbol filter (default "BTC-USD")
    """
    model = request.args.get("model", "ARIMA")
    horizon = request.args.get("horizon", "1h")
    symbol = request.args.get("symbol", "BTC-USD")
    horizon_hours = int(horizon[:-1]) if horizon.endswith('h') else 24 # default to 24h if not specified

    if model.upper() == "ARIMA":
        csv_path = r"C:\Coursera\Microsoft_AI_ML\arima_hourly.csv"
        ma_preds = []
        historical_data = []
        arima_preds = []
        
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, parse_dates=["timestamp"]).sort_values("timestamp")
            last_time = None
            if not df.empty:
                # Ensure last_time is UTC tz-aware for consistent comparisons
                last_time = _to_utc_timestamp(df['timestamp'].iloc[-1])

            arima_preds = _fetch_predictions("ARIMA", horizon_hours, symbol, start_after=last_time)

            # Filter historical data based on horizon
            horizon_hours_val = int(horizon[:-1])
            window_hours_mapping = {1: 6, 3: 12, 24: 24, 72: 72}
            window_hours = window_hours_mapping.get(horizon_hours_val, 24)

            if not df.empty:
                last_timestamp_pd = df['timestamp'].iloc[-1]
                cutoff = last_timestamp_pd - pd.Timedelta(hours=window_hours)
                df_filtered = df[df['timestamp'] >= cutoff]
            else:
                df_filtered = df

            required_cols = ['timestamp', 'open', 'high', 'low', 'close']
            if all(col in df_filtered.columns for col in required_cols):
                historical_data = df_filtered[required_cols].to_dict('records')
            else:
                historical_data = df_filtered[['timestamp', 'close']].to_dict('records')

            for record in historical_data:
                record['timestamp'] = record['timestamp'].isoformat()

            # ma_preds generation
            window = 3
            if horizon.endswith("h"):
                steps = int(horizon[:-1])
                freq = "H"
            else:
                steps = int(horizon[:-1])
                freq = "D"
            
            if not df.empty:
                last_time_for_ma = _to_utc_timestamp(df["timestamp"].iloc[-1])
                last_mean = df["close"].rolling(window).mean().iloc[-1]
                for s in range(1, steps + 1):
                    future_ts = (last_time_for_ma + (pd.Timedelta(hours=s) if freq == "H" else pd.Timedelta(days=s))).isoformat()
                    ma_preds.append({"timestamp": future_ts, "predicted_close": float(last_mean)})

        else: # if csv does not exist
            arima_preds = _fetch_predictions("ARIMA", horizon_hours, symbol)

        return jsonify({
            "model": "ARIMA", 
            "horizon": horizon, 
            "predictions": arima_preds,
            "baseline_predictions": ma_preds,
            "historical_data": historical_data
        })

    if model.upper() == "LSTM":
        csv_path = r"C:\Coursera\Microsoft_AI_ML\arima_hourly.csv"
        historical_data = []
        predictions = []
        
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, parse_dates=["timestamp"]).sort_values("timestamp")
            last_time = None
            if not df.empty:
                # Ensure last_time is UTC tz-aware for consistent comparisons
                last_time = _to_utc_timestamp(df['timestamp'].iloc[-1])

            predictions = _fetch_predictions("LSTM", horizon_hours, symbol, start_after=last_time)

            # Filter historical data based on horizon
            horizon_hours_val = int(horizon[:-1])
            window_hours_mapping = {1: 6, 3: 12, 24: 24, 72: 72}
            window_hours = window_hours_mapping.get(horizon_hours_val, 24)

            if not df.empty:
                last_timestamp_pd = df['timestamp'].iloc[-1]
                cutoff = last_timestamp_pd - pd.Timedelta(hours=window_hours)
                df_filtered = df[df['timestamp'] >= cutoff]
            else:
                df_filtered = df

            required_cols = ['timestamp', 'open', 'high', 'low', 'close']
            if all(col in df_filtered.columns for col in required_cols):
                historical_data = df_filtered[required_cols].to_dict('records')
            else:
                historical_data = df_filtered[['timestamp', 'close']].to_dict('records')

            for record in historical_data:
                record['timestamp'] = record['timestamp'].isoformat()
        
        else: # if csv does not exist
            predictions = _fetch_predictions("LSTM", horizon_hours, symbol)

        return jsonify({
            "model": "LSTM", 
            "horizon": horizon, 
            "predictions": predictions,
            "historical_data": historical_data
        })

    if model.upper() == "ENSEMBLE":
        csv_path = r"C:\Coursera\Microsoft_AI_ML\arima_hourly.csv"
        historical_data = []
        arima_preds = []
        lstm_preds = []
        
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, parse_dates=["timestamp"]).sort_values("timestamp")
            last_time = None
            if not df.empty:
                # Ensure last_time is UTC tz-aware for consistent comparisons
                last_time = _to_utc_timestamp(df['timestamp'].iloc[-1])

            arima_preds = _fetch_predictions("ARIMA", horizon_hours, symbol, start_after=last_time)
            lstm_preds = _fetch_predictions("LSTM", horizon_hours, symbol, start_after=last_time)

            # Filter historical data based on horizon
            horizon_hours_val = int(horizon[:-1])
            window_hours_mapping = {1: 6, 3: 12, 24: 24, 72: 72}
            window_hours = window_hours_mapping.get(horizon_hours_val, 24)

            if not df.empty:
                last_timestamp_pd = df['timestamp'].iloc[-1]
                cutoff = last_timestamp_pd - pd.Timedelta(hours=window_hours)
                df_filtered = df[df['timestamp'] >= cutoff]
            else:
                df_filtered = df

            required_cols = ['timestamp', 'open', 'high', 'low', 'close']
            if all(col in df_filtered.columns for col in required_cols):
                historical_data = df_filtered[required_cols].to_dict('records')
            else:
                historical_data = df_filtered[['timestamp', 'close']].to_dict('records')

            for record in historical_data:
                record['timestamp'] = record['timestamp'].isoformat()
        
        else: # if csv does not exist
            arima_preds = _fetch_predictions("ARIMA", horizon_hours, symbol)
            lstm_preds = _fetch_predictions("LSTM", horizon_hours, symbol)

        ensemble_predictions = []
        # Assuming both models return predictions for the same timestamps and in the same order
        # This is a simple average. For weighted average, you'd add weights.
        for i in range(min(len(arima_preds), len(lstm_preds))):
            avg_close = (arima_preds[i]["predicted_close"] + lstm_preds[i]["predicted_close"]) / 2
            ensemble_predictions.append({
                "timestamp": arima_preds[i]["timestamp"],
                "predicted_close": avg_close
            })
        return jsonify({"model": "ENSEMBLE", "horizon": horizon, "predictions": ensemble_predictions, "historical_data": historical_data})

    if model.upper() == "MA":
        # Moving average baseline computed from hourly CSV.
        # horizon may be "1h","3h","24h","72h" — convert to steps (hours or days)
        csv_path = r"C:\Coursera\Microsoft_AI_ML\arima_hourly.csv"
        if not os.path.exists(csv_path):
            return jsonify({"error": "arima_hourly.csv not found on server for MA baseline."}), 404
        
        df = pd.read_csv(csv_path, parse_dates=["timestamp"]).sort_values("timestamp")

        # Filter historical data based on horizon
        horizon_hours_val = int(horizon[:-1])
        window_hours_mapping = {1: 6, 3: 12, 24: 24, 72: 72}
        window_hours = window_hours_mapping.get(horizon_hours_val, 24)

        if not df.empty:
            last_timestamp = df['timestamp'].iloc[-1]
            cutoff = last_timestamp - pd.Timedelta(hours=window_hours)
            df_filtered = df[df['timestamp'] >= cutoff]
        else:
            df_filtered = df

        required_cols = ['timestamp', 'open', 'high', 'low', 'close']
        if all(col in df_filtered.columns for col in required_cols):
            historical_data = df_filtered[required_cols].to_dict('records')
        else:
            historical_data = df_filtered[['timestamp', 'close']].to_dict('records')

        for record in historical_data:
            record['timestamp'] = record['timestamp'].isoformat()

        window = int(request.args.get("window", 3))
        # Compute rolling mean as prediction for next timestamp(s). We'll return last N predicted steps
        # We'll create forecast entries for the next H steps by repeating the last rolling mean.
        if horizon.endswith("h"):
            steps = int(horizon[:-1])  # e.g., "3h" -> 3
            freq = "H"
        else:
            steps = int(horizon[:-1]) if horizon.endswith("d") else 1
            freq = "D"
            if horizon.endswith("d"):
                steps = int(horizon[:-1])
        last_time = _to_utc_timestamp(df["timestamp"].iloc[-1])
        last_mean = df["close"].rolling(window).mean().iloc[-1]
        preds = []
        for s in range(1, steps + 1):
            future_ts = (last_time + (pd.Timedelta(hours=s) if freq == "H" else pd.Timedelta(days=s))).isoformat()
            preds.append({"timestamp": future_ts, "predicted_close": float(last_mean)})
        return jsonify({"model": "MA", "horizon": horizon, "predictions": preds, "historical_data": historical_data})

    return jsonify({"error": "unknown model"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
