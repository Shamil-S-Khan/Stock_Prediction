## Finance Forecasting System — Short Report (Extended)

This report documents the extended system with adaptive learning, continuous evaluation, portfolio management, and visualization. It targets a 3–5 page scope.

### 1) Architecture and Data Flow

High-level diagrams are maintained in `docs/architecture.md`. For convenience the main component view is reproduced here:

See `docs/architecture.md` for a full sequence diagram covering ingestion → prediction logging → actuals update → evaluation → retraining and versioning.

For detailed data file (CSV) descriptions and schemas, see `docs/data_dictionary.md`.

---

### 2) Adaptive/Continuous Learning Mechanism

- Hourly ingestion: `data_fetcher.scheduled_job()` fetches the most recent completed 1h bar (UTC) and appends it to `crypto_data.csv`. It simultaneously calls `evaluation.update_with_actual()` so past predictions are filled with actuals when the time passes.
- Retraining trigger: A persistent counter in `data/.new_rows_count` is incremented per new row. When `>= RETRAIN_THRESHOLD` (configurable in `config.py`), `trigger_retraining()` runs `model/arima_model.py` and `model/lstm_model.py`.
- Versioning: Each trainer calls `model_manager.save_model_version()` which writes model artifacts under `models/<type>/` and appends a metadata entry into `models/metadata.json` including timestamp, hyperparameters, initial metrics, and data range.
- Serving latest: `/api/predictions` resolves the most recent version via `model_manager.load_latest_model(type)` and generates the next N hours of forecasts based on the current history window.
- Post-prediction logging: Every forecast is recorded into `data/predictions.csv` with columns `[timestamp, symbol, horizon, model_type, predicted_price, actual_price, error]`.

Edge handling: All timestamps are coerced to timezone-aware UTC; missing/invalid rows are dropped; Docker/Windows path differences are handled by rebuilding relative model paths when needed.

---

### 3) Evaluation and Monitoring Approach

- Actuals completion: `update_actuals.py` runs hourly (and `populate_actuals.py` is available for manual bulk fills). It first tries `crypto_data.csv`, and if absent/unmatched, optionally falls back to yfinance to backfill. The script computes `error = predicted_price - actual_price`.
- Rolling metrics: `evaluation.calculate_metrics()` filters the last K days (default 30) for a given `(model_type, horizon, symbol)` where `actual_price` exists, then computes MAE, RMSE, and MAPE. `run_evaluation()` iterates across models and horizons and appends snapshots to `data/metrics.csv`.
- Visualization: `/dashboard` renders a monitoring page that:
  - charts metric histories per model/horizon,
  - compares current vs previous week metrics,
  - lists model versions (from `metadata.json`),
  - flags alerts (e.g., MAPE > 10%) via a red indicator.
- API endpoints:
  - `/api/metrics?model=arima&horizon=24h&symbol=BTC-USD&lookback=30`
  - `/api/metric_history?model=arima&horizon=24h&metric=mape&days=30`
  - `/api/dashboard/*` helpers used by the dashboard page.

---

### 4) Portfolio Management Strategy and Visualization

- Strategy: `portfolio.run_live_trading_strategy()` evaluates the most recent 24h prediction for `BTC-USD` and compares it to the live/last price:
  - If predicted change > +2% → buy 10% of cash balance;
  - If predicted change < −2% → sell 25% of current holdings;
  - Else → hold.
- State & accounting:
  - State: `data/portfolio_state.json` (cash, holdings)
  - Transactions: `data/transactions.csv` (timestamped buys/sells)
  - Historical value: `data/portfolio_history.csv` (for legacy) and `data/portfolio_historical_values.csv` (new value snapshots)
- Performance metrics: `Portfolio.get_performance_metrics()` computes total return, annualized return, annualized volatility, Sharpe ratio (2% RF), and max drawdown from historical portfolio values.
- Visualization on `/` (index):
  - price candlestick with prediction traces, shaded error overlays, and trade markers (green triangles for buys, red triangles for sells),
  - portfolio value over time line chart,
  - holdings pie chart,
  - live metrics widget (Sharpe, volatility, drawdown, etc.).

---

### 5) Screenshots or Sample Runs

You can capture screenshots of the required visuals directly from the running app.

Required shots (paste below or submit as separate files):
- Candlestick with prediction line and shaded error overlay (index page)
- Portfolio value growth chart and metrics panel (index page)
- Monitoring dashboard with metric history and model versions (dashboard page)

How to produce in Windows PowerShell:

```powershell
# If using Docker (recommended)
docker-compose up --build -d
Start-Process http://localhost:5000        # main chart & portfolio
Start-Process http://localhost:5000/dashboard # monitoring dashboard

# Or run locally
.\tf-env\Scripts\Activate.ps1
python .\finance_forecasting\app.py
```

Tips:
- On the main chart page, use the legend to toggle traces and double‑click to isolate a trace. Use the camera icon to export a PNG.
- If actuals are sparse, run: `python finance_forecasting\populate_actuals.py` to fill from `crypto_data.csv`.
- If yfinance is unstable, the app still renders with cached data and previously recorded predictions/metrics.

---

### 6) Notes on Models

- ARIMA: Trained on log prices; forecasts are exponentiated for level prices. Served directly via latest saved artifact.
- LSTM: Sequence length and scaler metadata saved; last `seq_len` steps are used as input to predict a horizon, then inverse-scaled to price space.
- Both models’ predictions are logged for backtesting and evaluation; the dashboard shows their rolling error behavior.

---

### 7) Appendix (optional quick metrics workflow)

To recompute a small comparison locally:
1. Query `/api/predictions` for ARIMA and LSTM with the same horizon.
2. Wait for actuals to arrive (or run `populate_actuals.py`).
3. Use `evaluation.calculate_metrics()` to obtain MAE/RMSE/MAPE for the last N days.

For deeper details, see `docs/architecture.md`.
