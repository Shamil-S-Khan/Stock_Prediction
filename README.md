# Cryptocurrency Price Forecasting & Portfolio Management System

A comprehensive machine learning system for cryptocurrency price prediction, automated portfolio management, and real-time performance monitoring. Built with Flask, LSTM, and ARIMA models.

## 🌟 Features

### Forecasting Models
- **LSTM (Long Short-Term Memory)**: Deep learning model for capturing long-term dependencies
- **ARIMA (AutoRegressive Integrated Moving Average)**: Statistical model for time series forecasting
- Multiple prediction horizons: 1h, 3h, 24h, and 72h

### Portfolio Management
- Automated trading based on prediction signals
- Real-time portfolio tracking and valuation
- Transaction history with buy/sell decisions
- Configurable trading thresholds

### Performance Monitoring
- Comprehensive metric tracking (MAE, RMSE, MAPE)
- Interactive dashboard with real-time charts
- Historical performance comparison
- Automatic model retraining when performance degrades

### Automation
- Scheduled data fetching from cryptocurrency APIs
- Automatic prediction updates
- Performance evaluation and monitoring
- Intelligent retraining triggers

## 📋 Prerequisites

- Python 3.8 or higher
- pip package manager
- Virtual environment (recommended)

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/finance-forecasting.git
   cd finance-forecasting
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application**
   - Edit `config.py` to set your preferences:
     - API keys (if using external data sources)
     - Trading thresholds
     - Model parameters
     - Metric thresholds for retraining

## 💻 Usage

### Running the Web Application

Start the Flask server:
```bash
python main.py
```

Access the forecast at: `http://localhost:5000`
and the dashboard at `http://localhost:5000/dashboard`

### Dashboard Features

- **Home**: Overview and quick predictions
- **Portfolio**: Current holdings, transactions, and performance
- **Dashboard**: Comprehensive charts and metrics visualization
- **Performance Comparison**: Side-by-side model evaluation

### Training Models

Train ARIMA model:
```bash
python model/arima_model.py
```

Train LSTM model:
```bash
python model/lstm_model.py
```

### Data Collection

Fetch latest cryptocurrency data:
```bash
python data/data_fetcher.py
```

### Running Evaluations

Evaluate model performance:
```bash
python evaluation.py
```

## 📊 Project Structure

```
finance_forecasting/
│
├── main.py                 # Flask application & API endpoints
├── config.py              # Configuration settings
├── evaluation.py          # Model evaluation & metrics
├── portfolio.py           # Portfolio management logic
├── model_manager.py       # Model loading & prediction management
├── requirements.txt       # Python dependencies
│
├── data/
│   ├── data_fetcher.py   # Cryptocurrency data fetching
│   ├── crypto_data.csv   # Historical price data
│   ├── predictions.csv   # Model predictions log
│   └── metrics.csv       # Performance metrics
│
├── model/
│   ├── arima_model.py    # ARIMA training script
│   ├── lstm_model.py     # LSTM training script
│   └── arima_baseline.py # Baseline ARIMA implementation
│
├── models/               # Saved model files
│   ├── arima/
│   ├── lstm/
│   └── metadata.json
│
├── templates/            # HTML templates
│   ├── index.html
│   └── dashboard.html
│
├── static/              # CSS, JS, images
│
└── test/                # Unit tests
    └── test_app.py
```

## ⚙️ Configuration

Key configuration options in `config.py`:

```python
# Model Training
RETRAIN_THRESHOLD = 1  # Number of new data points before retraining

# Trading Strategy
INITIAL_CASH = 10000
BUY_THRESHOLD_PCT = 0.02   # 2% predicted increase
SELL_THRESHOLD_PCT = 0.02  # 2% predicted decrease

# Metric Thresholds (trigger retraining)
MAPE_THRESHOLD = 10.0   # Maximum 10% MAPE
MAE_THRESHOLD = 500.0
RMSE_THRESHOLD = 600.0

# Evaluation
EVALUATION_LOOKBACK_DAYS = 30
```

## 📈 API Endpoints

### Predictions
- `GET /api/predict/<symbol>` - Get predictions for all horizons
- `GET /api/predict/<symbol>/<horizon>` - Get prediction for specific horizon

### Portfolio
- `GET /api/portfolio` - Current portfolio state
- `GET /api/portfolio/history` - Historical portfolio values
- `GET /api/transactions` - Transaction history

### Dashboard
- `GET /api/dashboard/metric_charts` - Metric history for charts
- `GET /api/dashboard/performance_comparison` - Model comparison data
- `GET /api/dashboard/recent_predictions` - Latest predictions

## 🧪 Testing

Run the test suite:
```bash
python -m pytest test/
```

Run specific tests:
```bash
python -m pytest test/test_app.py -v
```

## 📊 Model Performance

Models are evaluated using:
- **MAE (Mean Absolute Error)**: Average magnitude of errors
- **RMSE (Root Mean Squared Error)**: Penalizes larger errors more heavily
- **MAPE (Mean Absolute Percentage Error)**: Percentage-based error metric

Automatic retraining is triggered when any metric exceeds its threshold.

## 🔄 Automated Workflows

The system includes automated jobs:
1. **Data Fetching**: Hourly cryptocurrency price updates
2. **Prediction Generation**: New predictions after each data fetch
3. **Portfolio Updates**: Automatic trading based on signals
4. **Performance Monitoring**: Continuous metric evaluation
5. **Model Retraining**: Triggered when performance degrades

## 🛠️ Technologies Used

- **Backend**: Flask, Python 3.8+
- **ML/AI**: TensorFlow/Keras (LSTM), statsmodels (ARIMA), scikit-learn
- **Data**: pandas, numpy, yfinance
- **Frontend**: HTML5, CSS3, JavaScript, Plotly.js
- **Storage**: CSV files, JSON

## 📝 Data Flow

1. **Data Collection**: Fetch cryptocurrency prices via yfinance
2. **Preprocessing**: Clean and format data for models
3. **Prediction**: Generate forecasts using ARIMA and LSTM
4. **Trading**: Execute buy/sell decisions based on predictions
5. **Evaluation**: Calculate metrics by comparing predictions to actual values
6. **Monitoring**: Track performance and trigger retraining if needed

## 🔍 Troubleshooting

### Models not loading
- Ensure models are trained: Run `python model/arima_model.py` and `python model/lstm_model.py`
- Check `models/` directory for saved model files

### No predictions showing
- Verify data is available in `data/crypto_data.csv`
- Run data fetcher: `python data/data_fetcher.py`

### Dashboard charts not displaying
- Check browser console for errors
- Verify API endpoints are returning data
- Ensure metrics.csv has recent data (within 30 days)

### Permission errors on Windows
- Run terminal as Administrator
- Check file permissions in data/ and models/ directories

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- yfinance for cryptocurrency data
- TensorFlow/Keras for deep learning framework
- statsmodels for statistical modeling
- Flask for web framework
- Plotly for interactive charts

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Contact: your.email@example.com

## 🗺️ Roadmap

- [ ] Add support for multiple cryptocurrencies
- [ ] Implement additional ML models (Prophet, XGBoost)
- [ ] Real-time WebSocket updates
- [ ] Mobile app integration
- [ ] Advanced backtesting features
- [ ] Risk management tools
- [ ] Export reports (PDF/Excel)

---

**Note**: This system is for educational and research purposes. Cryptocurrency trading involves risk. Always do your own research and never invest more than you can afford to lose.
