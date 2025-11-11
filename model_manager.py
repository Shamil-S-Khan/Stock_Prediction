import os
import json
import joblib
from datetime import datetime
from tensorflow.keras.models import load_model as keras_load_model

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
METADATA_PATH = os.path.join(MODEL_DIR, 'metadata.json')

def setup_storage():
    """Creates the necessary directories and metadata file if they don't exist."""
    os.makedirs(os.path.join(MODEL_DIR, 'arima'), exist_ok=True)
    os.makedirs(os.path.join(MODEL_DIR, 'lstm'), exist_ok=True)
    if not os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'w') as f:
            json.dump([], f)

def save_model_version(model, model_type, metrics, params, data_range):
    """Saves a model version and its metadata."""
    setup_storage()

    timestamp = datetime.now()
    ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
    model_id = f"{model_type}_{ts_str}"

    if model_type == 'arima':
        ext = 'pkl'
        model_path = os.path.join(MODEL_DIR, 'arima', f"model_{model_id}.{ext}")
        joblib.dump(model, model_path)
    elif model_type == 'lstm':
        ext = 'h5'
        model_path = os.path.join(MODEL_DIR, 'lstm', f"model_{model_id}.{ext}")
        model.save(model_path)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    metadata = {
        'model_id': model_id,
        'model_type': model_type,
        'timestamp': timestamp.isoformat(),
        'model_path': model_path,
        'data_range': data_range,
        'initial_metrics': metrics,
        'hyperparameters': params
    }

    with open(METADATA_PATH, 'r+') as f:
        all_metadata = json.load(f)
        all_metadata.append(metadata)
        f.seek(0)
        json.dump(all_metadata, f, indent=4)
    
    print(f"Saved model version: {model_id}")
    return model_id

def load_metadata():
    """Loads the metadata file."""
    if not os.path.exists(METADATA_PATH):
        return []
    with open(METADATA_PATH, 'r') as f:
        return json.load(f)

def load_latest_model(model_type):
    """Loads the latest model of a given type."""
    all_metadata = load_metadata()
    # Filter by model_type and sort by timestamp descending
    relevant_models = sorted(
        [m for m in all_metadata if m['model_type'] == model_type],
        key=lambda x: x['timestamp'],
        reverse=True
    )

    if not relevant_models:
        print(f"No saved models found for type: {model_type}")
        return None, None

    latest_meta = relevant_models[0]
    model_path = latest_meta['model_path']
    
    # Handle both absolute paths (from metadata) and relative paths (for Docker)
    if not os.path.exists(model_path):
        # Try to construct path relative to current MODEL_DIR
        model_id = latest_meta['model_id']
        ext = 'pkl' if model_type == 'arima' else 'h5'
        model_path = os.path.join(MODEL_DIR, model_type, f"model_{model_id}.{ext}")
        
        if not os.path.exists(model_path):
            print(f"Error: Model file not found at {model_path}")
            return None, None

    print(f"Loading latest model: {latest_meta['model_id']} from {model_path}")
    if model_type == 'arima':
        model = joblib.load(model_path)
    elif model_type == 'lstm':
        model = keras_load_model(model_path)
    else:
        return None, None

    return model, latest_meta

def load_model_by_id(model_id):
    """Loads a model by its specific ID."""
    all_metadata = load_metadata()
    meta = next((m for m in all_metadata if m['model_id'] == model_id), None)

    if not meta:
        print(f"Model with ID {model_id} not found.")
        return None

    model_path = meta['model_path']
    model_type = meta['model_type']
    
    # Handle both absolute paths (from metadata) and relative paths (for Docker)
    if not os.path.exists(model_path):
        # Try to construct path relative to current MODEL_DIR
        ext = 'pkl' if model_type == 'arima' else 'h5'
        model_path = os.path.join(MODEL_DIR, model_type, f"model_{model_id}.{ext}")
        
        if not os.path.exists(model_path):
            print(f"Error: Model file not found at {model_path}")
            return None

    print(f"Loading model: {meta['model_id']} from {model_path}")
    if model_type == 'arima':
        return joblib.load(model_path)
    elif model_type == 'lstm':
        return keras_load_model(model_path)
    return None
