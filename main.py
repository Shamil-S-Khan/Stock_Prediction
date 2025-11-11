from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import os
import logging
import time
from pymongo import MongoClient
from sklearn.preprocessing import MinMaxScaler

# Import modules from the project
import config
import data_fetcher
import evaluation
import model_manager
import portfolio
import update_actuals

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Database Connection ---
client = MongoClient(config.MONGO_URI)
db = client[config.DB_NAME]
col_pred = db[config.PRED_COLLECTION]

# --- APScheduler Setup ---
scheduler = BackgroundScheduler()

# Define scheduled jobs
def scheduled_fetch_data_job():
    logging.info("Running scheduled data fetch job...")
    data_fetcher.scheduled_job()

def scheduled_full_evaluation_job():
    logging.info("Running scheduled full model evaluation job...")
    evaluation.run_evaluation(symbol="BTC-USD") # Default symbol for full evaluation

def scheduled_update_actuals_job():
    logging.info("Running scheduled update actuals job...")
    update_actuals.update_missing_actuals(symbol="BTC-USD")

# Add jobs to the scheduler
scheduler.add_job(scheduled_fetch_data_job, 'interval', hours=config.FETCH_INTERVAL_HOURS, id='fetch_data_job')
scheduler.add_job(scheduled_full_evaluation_job, 'interval', hours=24, id='full_evaluation_job')
scheduler.add_job(scheduled_update_actuals_job, 'interval', hours=1, id='update_actuals_job')

# Start the scheduler
scheduler.start()

# --- Flask Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/candles")
def api_candles():
    minutes = int(request.args.get("minutes", 1440))
    csv_path = config.CRYPTO_DATA_FILE
    if not os.path.exists(csv_path):
        return jsonify({"error": "Data file not found."}), 404
    
    df = pd.read_csv(csv_path, parse_dates=["timestamp"], on_bad_lines='skip')
    df = df.sort_values("timestamp")
    
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    df = df[df['timestamp'] >= cutoff]
    
    df = df.replace({np.nan: None})
    records = df.to_dict('records')
    for record in records:
        record['timestamp'] = record['timestamp'].isoformat()
        
    return jsonify(records)

@app.route("/api/predictions")
def api_predictions():
    try:
        logging.info(f"API call to /api/predictions with args: {request.args}")
        model_type = request.args.get("model", "ARIMA").lower()
        horizon = int(request.args.get("horizon", "24h")[:-1])
        symbol = request.args.get("symbol", "BTC-USD")

        # Load historical data from CSV for plotting
        csv_path = config.CRYPTO_DATA_FILE
        if not os.path.exists(csv_path):
            logging.error("Data file not found.")
            return jsonify({"error": "Data file not found."}), 404
        
        df = pd.read_csv(csv_path, parse_dates=["timestamp"], on_bad_lines='skip')
        df = df.sort_values("timestamp")

        # Load the latest model
        model, meta = model_manager.load_latest_model(model_type)
        if model is None:
            logging.error(f"No trained model found for type {model_type}.")
            return jsonify({"error": f"No trained model found for type {model_type}."}), 404

        # Generate predictions
        predictions = []
        if model_type == 'arima':
            # Use the loaded model directly for forecasting
            log_forecast = model.forecast(steps=horizon)
            forecast = np.exp(log_forecast)
            last_timestamp = df['timestamp'].iloc[-1]
            pred_dates = pd.date_range(start=last_timestamp, periods=horizon + 1, freq='H')[1:]
            predictions = [{
                "timestamp": date.isoformat(),
                "predicted_close": float(val) if not np.isnan(val) else None
            } for date, val in zip(pred_dates, forecast)]

            # Log predictions for evaluation
            for pred in predictions:
                evaluation.log_prediction(
                    timestamp=pd.to_datetime(pred['timestamp']),
                    horizon=f"{horizon}h",
                    model_type='arima',
                    predicted_value=pred['predicted_close'],
                    symbol=symbol
                )

        elif model_type == 'lstm':
            series = df["Close"].values.reshape(-1, 1)
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_series = scaler.fit_transform(series)
            seq_len = meta['hyperparameters']['seq_len']
            
            last_sequence = scaled_series[-seq_len:].reshape(1, seq_len, 1)
            future_preds_scaled = model.predict(last_sequence)
            future_preds = scaler.inverse_transform(future_preds_scaled).flatten()

            last_timestamp = df['timestamp'].iloc[-1]
            pred_dates = pd.date_range(start=last_timestamp, periods=len(future_preds) + 1, freq='H')[1:]
            predictions = [{
                "timestamp": date.isoformat(),
                "predicted_close": float(val) if not np.isnan(val) else None
            } for date, val in zip(pred_dates, future_preds[:horizon])]

            # Log predictions for evaluation
            for pred in predictions:
                evaluation.log_prediction(
                    timestamp=pd.to_datetime(pred['timestamp']),
                    horizon=f"{horizon}h",
                    model_type='lstm',
                    predicted_value=pred['predicted_close'],
                    symbol=symbol
                )

        # Prepare historical data for plotting
        window_hours = 72 # Show last 72 hours of data
        cutoff = df['timestamp'].iloc[-1] - pd.Timedelta(hours=window_hours)
        historical_df = df[df['timestamp'] >= cutoff]
        historical_df = historical_df.replace({np.nan: None})
        historical_data = historical_df.to_dict('records')
        for record in historical_data:
            record['timestamp'] = record['timestamp'].isoformat()
            for key, value in record.items():
                if isinstance(value, np.floating):
                    record[key] = float(value)
                elif isinstance(value, np.integer):
                    record[key] = int(value)

        # Fetch past predictions for error overlay
        past_predictions = []
        if os.path.exists(config.PREDICTIONS_FILE):
            preds_df = pd.read_csv(config.PREDICTIONS_FILE, parse_dates=['timestamp'])
            # Filter for the same window as historical data, for the same model, and where actuals exist
            past_preds_df = preds_df[
                (preds_df['timestamp'] >= cutoff) &
                (preds_df['model_type'] == model_type) &
                (preds_df['actual_price'].notna())
            ]
            if not past_preds_df.empty:
                past_predictions = past_preds_df.to_dict('records')
                for record in past_predictions:
                    record['timestamp'] = record['timestamp'].isoformat()

        # Filter transactions based on the same time window
        transactions = []
        if os.path.exists(config.TRANSACTIONS_FILE):
            trans_df = pd.read_csv(config.TRANSACTIONS_FILE)
            # Handle mixed timestamp formats with error handling
            trans_df['timestamp'] = pd.to_datetime(trans_df['timestamp'], format='mixed', utc=True, errors='coerce')
            # Remove any rows where timestamp parsing failed
            trans_df = trans_df.dropna(subset=['timestamp'])
            trans_df_filtered = trans_df[trans_df['timestamp'] >= cutoff]
            if not trans_df_filtered.empty:
                transactions = trans_df_filtered.to_dict('records')
                for record in transactions:
                    record['timestamp'] = record['timestamp'].isoformat()

        return jsonify({
            "model": model_type.upper(),
            "horizon": f"{horizon}h",
            "predictions": predictions,
            "historical_data": historical_data,
            "past_predictions": past_predictions,
            "transactions": transactions
        })
    except Exception as e:
        import traceback
        with open("flask_error.log", "a") as f:
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Error in /api/predictions: {e}\n")
            f.write(traceback.format_exc())
            f.write("-" * 50 + "\n")
        logging.error(f"Error in /api/predictions: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during prediction."}), 500

@app.route("/api/portfolio_performance")
def api_portfolio_performance():
    try:
        logging.info(f"API call to /api/portfolio_performance with args: {request.args}")
        port = portfolio.Portfolio()
        portfolio_history_df = port.get_portfolio_history()
        transactions_df = port.get_transactions()
        metrics = port.get_performance_metrics()
        cash = port.cash
        holdings = port.holdings
        # Convert NaNs to None for JSON compatibility
        if portfolio_history_df is not None:
            portfolio_history_df = portfolio_history_df.replace({np.nan: None})
            portfolio_history = portfolio_history_df.to_dict(orient='records')
        else:
            portfolio_history = []

        if transactions_df is not None:
            transactions_df = transactions_df.replace({np.nan: None})
            transactions = transactions_df.to_dict(orient='records')
        else:
            transactions = []

        # Handle np.nan in holdings dictionary
        cleaned_holdings = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in holdings.items()}
        
        return jsonify({
            'portfolio_history': portfolio_history,
            'holdings': cleaned_holdings,
            'transactions': transactions,
            'metrics': metrics
        })
    except Exception as e:
        import traceback
        with open("flask_error.log", "a") as f:
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Error in /api/portfolio_performance: {e}\n")
            f.write(traceback.format_exc())
            f.write("-" * 50 + "\n")
        logging.error(f"Error in /api/portfolio_performance: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred while fetching portfolio performance."}), 500


@app.route("/api/metrics")
def api_metrics():
    model_type = request.args.get("model", "arima")
    horizon = request.args.get("horizon", "24h")
    symbol = request.args.get("symbol", "BTC-USD") # Add symbol parameter
    lookback_period = int(request.args.get("lookback", "30"))
    
    metrics = evaluation.calculate_metrics(model_type, horizon, symbol, lookback_period) # Pass symbol
    
    if metrics:
        return jsonify(metrics)
    else:
        return jsonify({"error": "Not enough data to calculate metrics."}), 404

@app.route("/api/metric_history")
def api_metric_history():
    model_type = request.args.get("model", "arima")
    horizon = request.args.get("horizon", "24h")
    symbol = request.args.get("symbol", "BTC-USD") # Add symbol parameter
    metric_name = request.args.get("metric", "mape")
    days = int(request.args.get("days", "30"))
    
    history = evaluation.get_metric_history(model_type, horizon, symbol, metric_name, days) # Pass symbol
    
    if not history.empty:
        # Convert timestamp to string for JSON serialization
        history['timestamp'] = history['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        return jsonify(history.to_dict('records'))
    else:
        return jsonify({"error": "No metric history found."}), 404


@app.route("/api/dashboard/model_versions")
def api_dashboard_model_versions():
    metadata = model_manager.load_metadata()
    return jsonify(metadata)

@app.route("/api/dashboard/status")
def api_dashboard_status():
    csv_path = config.CRYPTO_DATA_FILE
    if os.path.exists(csv_path):
        last_update_ts = os.path.getmtime(csv_path)
        last_update = datetime.fromtimestamp(last_update_ts).strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_update = "N/A"
    
    status_data = {
        "last_update": last_update,
        "next_retraining": "Hourly"
    }
    return jsonify(status_data)

@app.route("/api/dashboard/metric_charts")
def api_dashboard_metric_charts():
    models = ['arima', 'lstm']
    horizons = ['1h', '3h', '24h', '72h']
    metrics = ['mae', 'rmse', 'mape']
    symbol = request.args.get("symbol", "BTC-USD") # Add symbol parameter
    
    chart_data = {}
    
    for model in models:
        chart_data[model] = {}
        for horizon in horizons:
            chart_data[model][horizon] = {}
            for metric in metrics:
                history = evaluation.get_metric_history(model, horizon, symbol, metric, days=30) # Pass symbol
                if not history.empty:
                    history['timestamp'] = history['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    chart_data[model][horizon][metric] = history.to_dict('records')
                else:
                    chart_data[model][horizon][metric] = []
                    
    return jsonify(chart_data)

@app.route("/api/dashboard/performance_comparison")
def api_dashboard_performance_comparison():
    models = ['arima', 'lstm']
    horizons = ['1h', '3h', '24h', '72h']
    metrics = ['mae', 'rmse', 'mape']
    
    comparison_data = []
    
    today = datetime.now(timezone.utc)
    end_of_current_week = today
    end_of_previous_week = today - timedelta(days=7)
    
    for model in models:
        for horizon in horizons:
            current_week_metrics = evaluation.calculate_metrics(model, horizon, symbol="BTC-USD", lookback_period_days=7) # Pass symbol
            previous_week_metrics = evaluation.calculate_metrics(model, horizon, symbol="BTC-USD", lookback_period_days=14) # Pass symbol
            
            for metric in metrics:
                current_value = current_week_metrics.get(metric) if current_week_metrics else None
                previous_value = previous_week_metrics.get(metric) if previous_week_metrics else None
                
                change = None
                if current_value is not None and previous_value is not None:
                    change = current_value - previous_value
                
                comparison_data.append({
                    "model": model,
                    "horizon": horizon,
                    "metric": metric,
                    "current_week": current_value,
                    "previous_week": previous_value,
                    "change": change
                })
                
    return jsonify(comparison_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

