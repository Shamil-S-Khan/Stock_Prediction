# Data Dictionary (CSVs)

This project keeps small, human-readable CSVs to make the pipeline transparent and portable. All timestamps are UTC unless noted otherwise.

## Summary

- crypto_data.csv – Primary OHLCV time series for the app (hourly)
- predictions.csv – Logged model forecasts and their realized errors
- metrics.csv – Rolling evaluation snapshots for dashboard charts
- portfolio_history.csv – Legacy portfolio value time series (simple schema)
- portfolio_historical_values.csv – Newer portfolio value snapshots (explicit column name)
- transactions.csv – Executed trades (BUY/SELL) with quantities and prices
- arima_hourly.csv – Legacy/aux dataset for ARIMA baseline experiments
- lstm_daily.csv – Auxiliary daily dataset used for summary statistics in REPORT
- .new_rows_count – Plain-text counter used to trigger retraining

---

## crypto_data.csv

Purpose:
- The canonical source of recent market data used to serve charts and feed models.

Producers:
- `data_fetcher.scheduled_job()` appends the most recent completed hour
- `fetch_recent.py` seeds/refreshes multiple days of hourly data

Consumers:
- `/api/candles` and `/api/predictions` endpoints
- `update_actuals.py` and `populate_actuals.py` (to fill prediction actuals)
- Training scripts (`model/*.py`)

Typical columns:
- `timestamp` (UTC, ISO compatible)
- `Open`, `High`, `Low`, `Close`, `Volume`

Notes:
- Deduplicated by timestamp; sorted ascending before use.
- Robust parsing: files are read with `on_bad_lines='skip'` and `errors='coerce'` for timestamps.

---

## predictions.csv

Purpose:
- Persistent log of forecasts for all models/horizons so we can later join with actuals and compute errors.

Producer:
- `evaluation.log_prediction()` (called from `/api/predictions`, ARIMA/LSTM trainers)

Consumers:
- `update_actuals.py`/`populate_actuals.py` – fill `actual_price` and `error`
- `evaluation.calculate_metrics()`/`run_evaluation()` – compute rolling metrics
- Frontend error overlays (index page) – shaded regions and actual markers

Schema:
- `timestamp` (UTC datetime of the prediction target)
- `symbol` (e.g., `BTC-USD`)
- `horizon` (string like `1h`, `24h`)
- `model_type` (`arima` | `lstm` ...)
- `predicted_price` (float)
- `actual_price` (float, may be null until realized)
- `error` (float, `predicted_price - actual_price`, null until realized)

Notes:
- Logging can happen multiple times; later fills overwrite `actual_price` and `error` for the same key.

---

## metrics.csv

Purpose:
- Time-stamped metrics for monitoring model quality over time.

Producer:
- `evaluation.store_metrics()` (called from `run_evaluation()`)

Consumers:
- `/api/dashboard/metric_charts` and related dashboard views

Schema:
- `timestamp` (UTC when the metrics were computed)
- `model_type` (`arima` | `lstm` ...)
- `horizon` (`1h`, `3h`, `24h`, `72h`)
- `mae` (float)
- `rmse` (float)
- `mape` (float, 0–100)

---

## portfolio_history.csv (legacy)

Purpose:
- Legacy file for portfolio value over time, used by some parts of the codebase for metrics.

Producer:
- Historically appended by older portfolio code paths.

Consumers:
- `Portfolio.get_performance_metrics()` currently expects a column named `value` in this file.

Schema (legacy):
- `timestamp`
- `value` (float total portfolio value)

Note:
- The newer `record_historical_value()` writes to `portfolio_historical_values.csv` with column `portfolio_value`. Both are supported in the UI/metrics.

---

## portfolio_historical_values.csv (new)

Purpose:
- Newer, explicit schema for portfolio total value snapshots.

Producer:
- `Portfolio.record_historical_value()`

Schema:
- `timestamp`
- `portfolio_value`

Consumers:
- Can be used to draw the portfolio value time series; if you standardize on this file, adjust `get_performance_metrics()` accordingly.

---

## transactions.csv

Purpose:
- Full audit trail of executed trades.

Producer:
- `Portfolio._log_transaction()` (called from `buy()`/`sell()`)

Schema:
- `timestamp` (trade time)
- `symbol` (e.g., `BTC-USD`)
- `type` (`BUY` | `SELL`)
- `quantity` (float units of asset)
- `price_per_unit` (float)
- `total_value` (float = quantity * price_per_unit)

Consumers:
- Frontend trade markers; portfolio summaries.

---

## arima_hourly.csv (auxiliary)

Purpose:
- A historical hourly dataset used by the moving-average baseline and earlier experiments.

Consumers:
- `model/arima_baseline.py`

Schema:
- typically includes `timestamp` and a `close` column (lowercase in legacy baseline)

---

## lstm_daily.csv (auxiliary)

Purpose:
- Daily dataset used to compute and show summary statistics in the report.

Consumers:
- Documentation/analysis sections in `REPORT.md`

---

## .new_rows_count

Purpose:
- Plain-text integer counter used by `data_fetcher` to decide when to retrain models.

Producer/Consumer:
- `data_fetcher.scheduled_job()` increments this file; `trigger_retraining()` resets it to `0` after retrain.

---

## Data hygiene and timezone

- All timestamps are coerced to UTC on read using `pd.to_datetime(..., utc=True, errors='coerce')` where appropriate.
- Ingestion scripts drop malformed rows and deduplicate on `timestamp`.
- CSVs are append-friendly; metrics/predictions grow over time.
