# Installation Guide

This guide will help you set up the Finance Forecasting System on your local machine.

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.14+, or Linux (Ubuntu 20.04+)
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 2GB free space
- **Internet**: Required for data fetching

### Recommended Requirements
- **Python**: 3.10+
- **RAM**: 8GB or more
- **GPU**: NVIDIA GPU with CUDA support (for faster LSTM training)

## Step-by-Step Installation

### 1. Install Python

If you don't have Python installed:

**Windows:**
- Download from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"

**macOS:**
```bash
brew install python@3.10
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.10 python3-pip python3-venv
```

Verify installation:
```bash
python --version  # Should show 3.8 or higher
```

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/finance-forecasting.git
cd finance-forecasting
```

Or download as ZIP and extract:
- Click "Code" → "Download ZIP"
- Extract to your desired location
- Open terminal/command prompt in that folder

### 3. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This may take 5-10 minutes depending on your internet connection.

**Note for Windows users:** If you encounter errors with TensorFlow:
```bash
pip install tensorflow-cpu  # For CPU-only version
```

### 5. Set Up Configuration

Edit `config.py` to customize settings:

```python
# Trading Strategy
INITIAL_CASH = 10000  # Starting portfolio value
BUY_THRESHOLD_PCT = 0.02  # 2% prediction threshold
SELL_THRESHOLD_PCT = 0.02

# Metric Thresholds
MAPE_THRESHOLD = 10.0
MAE_THRESHOLD = 500.0
RMSE_THRESHOLD = 600.0
```

### 6. Initialize Data Directories

The system will auto-create directories, but you can do it manually:

```bash
mkdir -p data models/arima models/lstm static templates
```

### 7. Fetch Initial Data

```bash
python data/data_fetcher.py
```

This downloads historical cryptocurrency price data.

### 8. Train Models

**Train ARIMA model:**
```bash
python model/arima_model.py
```

**Train LSTM model:**
```bash
python model/lstm_model.py
```

Training may take 5-30 minutes depending on your hardware.

### 9. Run the Application

```bash
python main.py
```

You should see:
```
* Running on http://127.0.0.1:5000
* Press CTRL+C to quit
```

### 10. Access the Dashboard

Open your web browser and navigate to:
```
http://localhost:5000
```

## Troubleshooting

### Common Issues

#### ImportError: No module named 'xyz'
**Solution:** Ensure virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

#### TensorFlow installation fails
**Solution:** Use CPU-only version:
```bash
pip uninstall tensorflow
pip install tensorflow-cpu
```

#### Permission denied errors (Windows)
**Solution:** Run Command Prompt as Administrator

#### Port 5000 already in use
**Solution:** Stop other applications using port 5000, or change port in `main.py`:
```python
app.run(debug=True, port=5001)  # Use port 5001 instead
```

#### Models not found
**Solution:** Train the models first:
```bash
python model/arima_model.py
python model/lstm_model.py
```

#### No data fetched
**Solution:** Check internet connection and run:
```bash
python data/data_fetcher.py
```

### Platform-Specific Issues

**Windows:**
- If activation script fails, try: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Use `python` instead of `python3`

**macOS:**
- Install Xcode Command Line Tools: `xcode-select --install`
- May need to use `python3` explicitly

**Linux:**
- Install python3-dev: `sudo apt install python3-dev`
- May need to install build essentials: `sudo apt install build-essential`

## Updating

To update to the latest version:

```bash
git pull origin master
pip install -r requirements.txt --upgrade
```

## Uninstalling

1. Deactivate virtual environment:
   ```bash
   deactivate
   ```

2. Delete project folder:
   ```bash
   cd ..
   rm -rf finance-forecasting  # Linux/macOS
   # Or manually delete folder on Windows
   ```

## Docker Installation (Alternative)

If you prefer Docker:

```bash
docker-compose up --build
```

Access at `http://localhost:5000`

## Verification

After installation, verify everything works:

```bash
# Run tests
python -m pytest test/ -v

# Check models exist
ls models/arima/
ls models/lstm/

# Check data exists
ls data/*.csv
```

## Next Steps

1. Read the [README.md](README.md) for usage instructions
2. Review [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
3. Check the dashboard at http://localhost:5000

## Getting Help

- Check [GitHub Issues](https://github.com/yourusername/finance-forecasting/issues)
- Read the [FAQ](docs/FAQ.md)
- Contact: your.email@example.com

---

**Congratulations! 🎉** Your Finance Forecasting System is now ready to use.
