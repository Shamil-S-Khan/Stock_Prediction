# Code Walkthrough (Finance Forecasting)

This document explains how each core file in `finance_forecasting/` works. For long files, commentary is block-by-block; for compact utilities, it’s line-by-line.

---

## config.py

- Imports `os` for path handling
- Defines key directories: `PROJECT_ROOT`, `DATA_DIR`, `MODELS_DIR`; ensures they exist
- Declares canonical file paths (CSV/JSON for data, metrics, state)
- Loads `MONGO_URI` from env with a default string; sets DB and collection names
- System tuning constants: fetch/retrain intervals, model types, trading thresholds, evaluation lookback

Why it matters: centralizes paths and constants so other modules don’t hard-code them.

---

## app.py (Flask app + scheduler)

- Imports Flask, APScheduler, datetime utils, numpy/pandas, logging, Mongo client, scaler
- Imports project modules: `config`, `data_fetcher`, `evaluation`, `model_manager`, `portfolio`, `update_actuals`
- Configures logging and initializes `app = Flask(...)`
- Creates Mongo connection using `config.MONGO_URI`; grabs DB/collection
- Starts a `BackgroundScheduler` and defines three jobs:
  - `scheduled_fetch_data_job`: calls `data_fetcher.scheduled_job()`
  - `scheduled_full_evaluation_job`: `evaluation.run_evaluation("BTC-USD")`
  - `scheduled_update_actuals_job`: `update_actuals.update_missing_actuals("BTC-USD")`
- Adds jobs with intervals (hourly/daily) and starts scheduler

Routes:
- `/` → renders `templates/index.html`
- `/dashboard` → renders `templates/dashboard.html`
- `/api/candles` → reads `crypto_data.csv`, filters last N minutes, serializes timestamps ISO8601
- `/api/predictions` →
  - reads history from CSV; loads latest model via `model_manager`
  - ARIMA: `model.forecast(horizon)`, exponentiates log-forecast
  - LSTM: scales series, uses last `seq_len` window to predict future horizon
  - logs each prediction via `evaluation.log_prediction` (for error overlays)
  - returns: predictions + recent historical + past predictions with actuals + recent transactions
- `/api/portfolio_performance` → returns portfolio history, holdings, transactions, and metrics from `portfolio.Portfolio`
- `/api/metrics` → wraps `evaluation.calculate_metrics` with params
- `/api/metric_history` → returns timeseries of a specific metric
- `/api/dashboard/model_versions|status|metric_charts|performance_comparison` → feeds dashboard visuals

---

## data_fetcher.py (hourly ingestion + retrain trigger)

- Imports yfinance, logging, subprocess, APScheduler
- Reads constants from `config` (data file paths, retrain threshold, etc.)
- `fetch_data(symbol="BTC-USD", interval="1h")`: pulls the last completed hour with `yf.Ticker(...).history(period="1d", interval="1h")` and returns the last row
- `append_to_csv(data)`: appends to `crypto_data.csv` (creates header if new file)
- `trigger_retraining()`: runs `model/arima_model.py` and `model/lstm_model.py` via `subprocess`; resets `.new_rows_count`
- `scheduled_job()`: main loop
  - fetch new data; update predictions with actuals; append row
  - run evaluation and trading strategy
  - increment new-row counter; if `>= RETRAIN_THRESHOLD` → retrain
- CLI handling: `--now` runs once; otherwise starts its own scheduler

---

## evaluation.py (prediction logging + metrics)

- Constants: `PREDICTIONS_FILE`, `METRICS_FILE`
- `log_prediction(timestamp, horizon, model_type, predicted_value, symbol)`:
  - ensures predictions CSV exists with columns, appends a new prediction row (actual/error null initially)
- `update_with_actual(timestamp, actual_value, symbol)`:
  - finds matching timestamp+symbol rows and sets `actual_price` and `error`
  - robust timezone handling (UTC coercion)
- `calculate_metrics(model_type, horizon, symbol, lookback_period_days)`:
  - filters predictions for the time window where actuals exist; computes MAE/RMSE/MAPE
- `store_metrics(model_type, horizon, metrics)`:
  - appends snapshot row (timestamp, model, horizon, metrics) to `metrics.csv`
- `run_evaluation(symbol)`:
  - iterates models x horizons; calculates metrics; stores snapshots; prints alert if MAPE>10%
- `get_metric_history(model_type, horizon, symbol, metric_name, days)`:
  - returns a filtered timeseries DataFrame for the dashboard

---

## model_manager.py (versioned model storage)

- Paths `models/` and `models/metadata.json` (created if missing)
- `save_model_version(model, model_type, metrics, params, data_range)`:
  - constructs `model_id` with timestamp; saves ARIMA via joblib `.pkl`, LSTM via Keras `.h5`
  - writes a metadata entry (id, type, time, path, data_range, initial_metrics, hyperparameters)
- `load_metadata()` → loads the list of model entries or empty list
- `load_latest_model(model_type)`:
  - picks the newest entry of the given type; robustly resolves path (works in Docker/Windows); loads actual model
- `load_model_by_id(model_id)`:
  - finds by id and loads similarly

---

## portfolio.py (stateful trading + metrics)

- Class `Portfolio` maintains cash, holdings, transactions; persists to JSON/CSV on each trade
- `buy(symbol, amount_usd, price)` and `sell(symbol, qty, price)` update state and log transactions
- `record_historical_value(current_prices)` appends value snapshots to `portfolio_historical_values.csv`
- `get_portfolio_history()`, `get_transactions()` read CSVs if present
- `get_performance_metrics()` computes total return, annualized return/volatility, Sharpe (2% RF), max drawdown from historical values
- `run_live_trading_strategy(current_price, symbol)` uses latest 24h ARIMA prediction to buy/sell/hold; records value
- `backtest_strategy()` illustrates a simple backtest using `predictions.csv` + `crypto_data.csv`

---

## update_actuals.py (fill actual prices)

- Reads `predictions.csv`; selects rows with missing `actual_price` that are in the past
- First tries to match against local `crypto_data.csv` (fast, robust parsing, deduped timestamps)
- If still missing, downloads hourly historical prices via yfinance for a min–max date range and fills remaining
- Always recomputes `error = predicted_price - actual_price` and writes back to CSV

---

## populate_actuals.py (bulk local fill)

- Helper to populate `actual_price` and `error` from `crypto_data.csv` only (no network)
- Uses `usecols=['timestamp','Close']`, drops duplicate timestamps, updates matching rows, saves

---

## fetch_recent.py (seed recent data)

- Downloads the last N days of hourly OHLC for a symbol using yfinance
- Merges with existing `crypto_data.csv` if present, dedupes by timestamp, writes back sorted

---

## model/arima_model.py (train + version + predict)

- Loads `crypto_data.csv`; sorts; selects `Close` as series; logs transform (`np.log`) for ARIMA
- Loads latest ARIMA metadata to reuse order; otherwise runs `pmdarima.auto_arima` to discover best `(p,d,q)`
- Splits train/test; fits `statsmodels` ARIMA; forecasts 72 steps; exponentiates back to price space
- Logs each forecast to `predictions.csv` using `evaluation.log_prediction`
- Evaluates on held-out test; computes RMSE/MAPE (sklearn)
- Saves model version via `model_manager.save_model_version`
- Upserts predictions to MongoDB (optional)

---

## model/lstm_model.py (train + version + predict)

- Loads `crypto_data.csv`, sets `timestamp` as index; extracts `Close`
- Scales with `MinMaxScaler(0,1)`; creates multi-step sequences for `SEQ_LEN=72`, `HORIZON=72`
- If no prior model: builds a Keras Sequential LSTM with dropout; else fine-tunes on new data since the last train end
- Trains for 10 epochs; evaluates on last 10%: RMSE/MAPE on the first step ahead
- Saves a version via `model_manager.save_model_version`
- Predicts next 72 hours from last window; logs each prediction to `predictions.csv`
- Writes predictions to MongoDB (optional)

---

## model/arima_baseline.py (moving average baseline)

- Reads `arima_hourly.csv`, computes rolling mean with window=3 shifted by 1 (to avoid peeking), then RMSE/MAPE

---

## templates/index.html (main UI)

- Controls for symbol/model/horizon with a Refresh button; legend usage tips
- Price chart: candlestick for historical + dash line for past predictions + shaded error band + actual markers + future predictions; buy/sell markers
- Portfolio charts: value over time (line), holdings distribution (pie), metrics panel (Sharpe, volatility, drawdown)
- Fetches `/api/predictions` and `/api/portfolio_performance` to render charts

---

## templates/dashboard.html (monitoring UI)

- System status (last update, next retraining)
- Alerts: MAPE > 10% indicator
- Metric charts for models x horizons; performance comparison table week-over-week
- Model version history table (from `models/metadata.json`)

---

## test/test_app.py (legacy test harness)

- Creates a fake DB and patches `finance_forecasting.app` internals for isolated testing
- Tests time conversion utilities, error cases, and API responses; some assumptions differ from the current structure

---

## zip_project.py (packaging helper)

- Zips the project to Desktop, excluding any venvs (tf-env/venv/.venv/env), caches, and git metadata
- Keeps data/ and models/ (as requested)
- CLI options: `--root` and `--out`

---

If you want true line-by-line comments embedded into each file, I can auto-generate `*_annotated.py` copies alongside the originals, but this doc covers the intent, flow, and interactions succinctly.
