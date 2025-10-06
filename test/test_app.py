import types
import pytest
import pandas as pd
from datetime import datetime, timezone


def load_app_module(monkeypatch, tmp_path, csv_exists=True):
    """Load the Flask app module with patched DB and CSV handling for tests."""
    csv_path = tmp_path / "arima_hourly.csv"
    if csv_exists:
        ts_base = pd.Timestamp(datetime.now(tz=timezone.utc)).floor('h')
        df = pd.DataFrame({
            'timestamp': [ts_base - pd.Timedelta(hours=2), ts_base - pd.Timedelta(hours=1), ts_base],
            'open': [1, 2, 3],
            'high': [2, 3, 4],
            'low': [0, 1, 2],
            'close': [10.0, 11.0, 12.0],
        })
        df.to_csv(csv_path, index=False)

    class FakeCursor(list):
        def sort(self, *_args, **_kwargs):
            return self
        def limit(self, _n):
            return self

    class FakeCollection:
        def __init__(self, docs):
            self._docs = docs
        def find(self, query):
            docs = self._docs
            ts_filter = query.get('timestamp')
            if ts_filter and '$gt' in ts_filter:
                cutoff = pd.to_datetime(ts_filter['$gt'])
                docs = [d for d in docs if pd.to_datetime(d['timestamp']) > cutoff]
            return FakeCursor(sorted(docs, key=lambda d: d['timestamp']))

    class FakeDB(dict):
        def __getitem__(self, name):
            return super().get(name)

    now_utc = pd.Timestamp(datetime.now(tz=timezone.utc)).floor('h')
    preds = [
        {'timestamp': now_utc + pd.Timedelta(hours=1), 'predicted_close': 123.4, 'model': 'ARIMA', 'symbol': 'BTC-USD'},
        {'timestamp': now_utc + pd.Timedelta(hours=2), 'predicted_close': 125.6, 'model': 'ARIMA', 'symbol': 'BTC-USD'},
    ]
    db = FakeDB({
        'candlestick_data': FakeCollection([
            {'timestamp': pd.Timestamp(datetime.now(tz=timezone.utc)).floor('h'), 'open': 1, 'high': 2, 'low': 0, 'close': 1.5, 'volume': 10},
        ]),
        'predictions': FakeCollection(preds),
    })

    import finance_forecasting.app as app_mod
    monkeypatch.setattr(app_mod, 'db', db)
    monkeypatch.setattr(app_mod, 'CANDLES_COLLECTION', 'candlestick_data')
    monkeypatch.setattr(app_mod, 'PRED_COLLECTION', 'predictions')
    monkeypatch.setattr(app_mod, 'pd', pd)
    # Patch only the exists function to avoid breaking pytest internals
    monkeypatch.setattr(app_mod.os.path, 'exists', lambda p: csv_exists and str(p) == str(csv_path), raising=False)

    def _read_csv(_path, parse_dates=None):
        return pd.read_csv(csv_path, parse_dates=parse_dates)
    monkeypatch.setattr(app_mod.pd, 'read_csv', _read_csv)
    return app_mod


@pytest.fixture
def client(monkeypatch, tmp_path):
    app_mod = load_app_module(monkeypatch, tmp_path, csv_exists=True)
    app = app_mod.app
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_to_utc_timestamp_naive(monkeypatch, tmp_path):
    app_mod = load_app_module(monkeypatch, tmp_path)
    ts = datetime(2025, 1, 1, 12, 0, 0)  # naive
    out = app_mod._to_utc_timestamp(ts)
    assert out.tz is not None and str(out.tz) == 'UTC'


def test_to_utc_timestamp_aware(monkeypatch, tmp_path):
    app_mod = load_app_module(monkeypatch, tmp_path)
    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    out = app_mod._to_utc_timestamp(ts)
    assert out.tz is not None and str(out.tz) == 'UTC'


def test_predictions_arima_future_only(client):
    resp = client.get('/api/predictions?model=ARIMA&horizon=3h&symbol=BTC-USD')
    assert resp.status_code == 200
    data = resp.get_json()
    preds = data['predictions']
    assert 1 <= len(preds) <= 3
    for p in preds:
        assert isinstance(p['timestamp'], str)
        assert 'T' in p['timestamp']


def test_ma_missing_csv_returns_404(monkeypatch, tmp_path):
    app_mod = load_app_module(monkeypatch, tmp_path, csv_exists=False)
    app = app_mod.app
    app.config.update(TESTING=True)
    with app.test_client() as c:
        resp = c.get('/api/predictions?model=MA&horizon=3h')
        assert resp.status_code == 404


def test_unknown_model_returns_400(client):
    resp = client.get('/api/predictions?model=XYZ&horizon=1h')
    assert resp.status_code == 400


def test_candles_returns_iso(client):
    resp = client.get('/api/candles?minutes=60')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    if data:
        row = data[0]
        assert isinstance(row['timestamp'], str)
        assert 'T' in row['timestamp']


