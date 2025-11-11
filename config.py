import os

# --- General Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')

# Ensure data and models directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# --- File Paths ---
CRYPTO_DATA_FILE = os.path.join(DATA_DIR, 'crypto_data.csv')
PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.csv')
METRICS_FILE = os.path.join(DATA_DIR, 'metrics.csv')
PORTFOLIO_STATE_FILE = os.path.join(DATA_DIR, 'portfolio_state.json')
PORTFOLIO_HISTORY_FILE = os.path.join(DATA_DIR, 'portfolio_history.csv')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.csv')
PORTFOLIO_HISTORICAL_VALUES_FILE = os.path.join(DATA_DIR, 'portfolio_historical_values.csv')
NEW_ROWS_COUNT_FILE = os.path.join(DATA_DIR, '.new_rows_count')
RETRAIN_TIMESTAMP_FILE = os.path.join(DATA_DIR, '.retrain_timestamp')

# --- API Keys & Secrets ---
# It's recommended to use environment variables for sensitive data
MONGO_URI = os.getenv("MONGO_URI","")
DB_NAME = "forecast"
PRED_COLLECTION = "predictions"

# --- Data Fetching ---
FETCH_INTERVAL_HOURS = 1 # How often to fetch new data

# --- Model Training ---
RETRAIN_THRESHOLD = 1 # Number of new data points before retraining
MODEL_TYPES = ['arima', 'lstm'] # Models to train

# --- Trading Strategy ---
INITIAL_CASH = 10000 # Starting cash for portfolio
BUY_THRESHOLD_PCT = 0.02 # Buy if prediction > this percentage increase
SELL_THRESHOLD_PCT = 0.02 # Sell if prediction > this percentage decrease

# --- Evaluation ---
EVALUATION_LOOKBACK_DAYS = 30 # Period for calculating metrics

# --- Metric Thresholds for Retraining ---
MAPE_THRESHOLD = 10.0  # Maximum acceptable MAPE percentage
MAE_THRESHOLD = 500.0  # Maximum acceptable MAE
RMSE_THRESHOLD = 600.0  # Maximum acceptable RMSE
