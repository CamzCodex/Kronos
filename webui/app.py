import datetime
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

# Add project root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from model import RELEASED_MODELS, Kronos, KronosPredictor, KronosTokenizer
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False
    RELEASED_MODELS = {}
    print("Warning: Kronos model cannot be imported")

if __package__:
    from .security import (
        RequestValidationError,
        bounded_float,
        bounded_int,
        require_json_object,
        resolve_data_file,
        validate_device,
        validate_optional_start_date,
    )
else:  # Direct execution from the webui directory.
    from security import (
        RequestValidationError,
        bounded_float,
        bounded_int,
        require_json_object,
        resolve_data_file,
        validate_device,
        validate_optional_start_date,
    )

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=64 * 1024,
    TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
)
app.logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("KRONOS_DATA_DIR", PROJECT_ROOT / "data")).expanduser().resolve()
RESULTS_DIR = Path(__file__).resolve().parent / "prediction_results"
MAX_DATA_FILE_BYTES = 64 * 1024 * 1024
MAX_DATA_ROWS = 250_000
LOCAL_ORIGINS = {"http://localhost:7070", "http://127.0.0.1:7070"}


def _request_json():
    if not request.is_json:
        raise RequestValidationError("Request body must use application/json")
    return require_json_object(request.get_json(silent=True))


@app.before_request
def enforce_local_origin():
    if request.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and origin not in LOCAL_ORIGINS:
            return jsonify({"error": "Cross-origin API requests are not allowed"}), 403
    return None


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.plot.ly https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(RequestValidationError)
def handle_request_validation(error):
    return jsonify({"error": str(error)}), 400


@app.errorhandler(413)
def handle_request_too_large(_error):
    return jsonify({"error": "Request body exceeds the local size limit"}), 413

# Global variables to store models
tokenizer = None
model = None
predictor = None

# Available model configurations
AVAILABLE_MODELS = {
    key: {
        'name': definition.name,
        'model_id': definition.model_id,
        'model_revision': definition.model_revision,
        'tokenizer_id': definition.tokenizer_id,
        'tokenizer_revision': definition.tokenizer_revision,
        'context_length': definition.context_length,
        'params': definition.parameter_count,
        'description': definition.description,
    }
    for key, definition in RELEASED_MODELS.items()
}


def select_prediction_window(df, lookback, pred_len, start_date=None):
    """Select one causal historical window and its immediately following truth."""

    required_rows = lookback + pred_len
    if len(df) < required_rows:
        raise RequestValidationError(
            f"Insufficient data length, need at least {required_rows} rows"
        )
    if start_date:
        start_timestamp = pd.to_datetime(start_date, utc=True)
        matches = np.flatnonzero((df['timestamps'] >= start_timestamp).to_numpy())
        if not len(matches):
            raise RequestValidationError("No data exists at or after start_date")
        start_index = int(matches[0])
        if len(df) - start_index < required_rows:
            raise RequestValidationError(
                f"Insufficient data from start time {start_timestamp.isoformat()}, "
                f"need at least {required_rows} rows"
            )
    else:
        # The latest comparable forecast ends at the final observed row.  Using
        # the first rows while labelling them latest silently evaluated stale data.
        start_index = len(df) - required_rows

    historical = df.iloc[start_index : start_index + lookback].copy()
    realized = df.iloc[
        start_index + lookback : start_index + required_rows
    ].copy()
    return historical, realized, start_index

def load_data_files():
    """Scan data directory and return available data files"""
    data_files = []
    
    if DATA_DIR.is_dir():
        for entry in sorted(DATA_DIR.iterdir(), key=lambda path: path.name):
            try:
                file_path = resolve_data_file(DATA_DIR, entry.name, MAX_DATA_FILE_BYTES)
            except RequestValidationError:
                continue
            file_size = file_path.stat().st_size
            data_files.append({
                'name': entry.name,
                'path': entry.name,
                'size': f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
            })
    
    return data_files

def load_data_file(file_path):
    """Load one strictly validated local market-data file."""
    try:
        file_path = resolve_data_file(DATA_DIR, file_path, MAX_DATA_FILE_BYTES)
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            return None, "Unsupported file format"

        if df.empty:
            return None, "Selected data file contains no rows"
        if len(df) > MAX_DATA_ROWS:
            return None, "Selected data file exceeds the local row limit"
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            return None, f"Missing required columns: {required_cols}"
        
        timestamp_cols = [
            column for column in ('timestamps', 'timestamp', 'date')
            if column in df.columns
        ]
        if not timestamp_cols:
            return None, "Missing required timestamp column"
        if len(timestamp_cols) > 1:
            return None, "Multiple timestamp columns are ambiguous"
        timestamps = pd.to_datetime(
            df[timestamp_cols[0]],
            errors='coerce',
            utc=True,
        )
        if timestamps.isna().any():
            return None, "Timestamp column contains invalid values"
        if timestamps.duplicated().any():
            return None, "Timestamp column contains duplicates"
        if not timestamps.is_monotonic_increasing:
            return None, "Timestamp column must be strictly increasing"
        df['timestamps'] = timestamps

        numeric_cols = ['open', 'high', 'low', 'close']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Process volume column (optional)
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            numeric_cols.append('volume')
        
        # Process amount column (optional, but not used for prediction)
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            numeric_cols.append('amount')

        numeric_values = df[numeric_cols].to_numpy(dtype=float)
        if not np.isfinite(numeric_values).all():
            return None, "Market data contains missing or non-finite numeric values"

        prices = df[['open', 'high', 'low', 'close']]
        if (prices <= 0).to_numpy().any():
            return None, "Market prices must be positive"
        invalid_candle = (
            (df['high'] < df[['open', 'close', 'low']].max(axis=1))
            | (df['low'] > df[['open', 'close', 'high']].min(axis=1))
        )
        if invalid_candle.any():
            return None, "Market data contains invalid OHLC relationships"
        for activity_col in ('volume', 'amount'):
            if activity_col in df.columns and (df[activity_col] < 0).any():
                return None, f"{activity_col} must be non-negative"
        
        return df, None
        
    except RequestValidationError as exc:
        return None, str(exc)
    except Exception:
        app.logger.exception("Unable to load selected data file")
        return None, "Unable to load selected data file"

def save_prediction_results(file_path, prediction_type, prediction_results, actual_data, input_data, prediction_params):
    """Save prediction results to file"""
    try:
        # Create prediction results directory
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S_%f')
        filename = f'prediction_{timestamp}.json'
        filepath = RESULTS_DIR / filename
        
        # Prepare data for saving
        save_data = {
            'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
            'file_path': Path(file_path).name,
            'prediction_type': prediction_type,
            'prediction_params': prediction_params,
            'input_data_summary': {
                'rows': len(input_data),
                'columns': list(input_data.columns),
                'price_range': {
                    'open': {'min': float(input_data['open'].min()), 'max': float(input_data['open'].max())},
                    'high': {'min': float(input_data['high'].min()), 'max': float(input_data['high'].max())},
                    'low': {'min': float(input_data['low'].min()), 'max': float(input_data['low'].max())},
                    'close': {'min': float(input_data['close'].min()), 'max': float(input_data['close'].max())}
                },
                'last_values': {
                    'open': float(input_data['open'].iloc[-1]),
                    'high': float(input_data['high'].iloc[-1]),
                    'low': float(input_data['low'].iloc[-1]),
                    'close': float(input_data['close'].iloc[-1])
                }
            },
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'analysis': {}
        }
        
        # If actual data exists, perform comparison analysis
        if actual_data and len(actual_data) > 0:
            # Calculate continuity analysis
            if len(prediction_results) > 0 and len(actual_data) > 0:
                last_pred = prediction_results[0]  # First prediction point
            first_actual = actual_data[0]      # First actual point
                
            save_data['analysis']['continuity'] = {
                    'last_prediction': {
                        'open': last_pred['open'],
                        'high': last_pred['high'],
                        'low': last_pred['low'],
                        'close': last_pred['close']
                    },
                    'first_actual': {
                        'open': first_actual['open'],
                        'high': first_actual['high'],
                        'low': first_actual['low'],
                        'close': first_actual['close']
                    },
                    'gaps': {
                        'open_gap': abs(last_pred['open'] - first_actual['open']),
                        'high_gap': abs(last_pred['high'] - first_actual['high']),
                        'low_gap': abs(last_pred['low'] - first_actual['low']),
                        'close_gap': abs(last_pred['close'] - first_actual['close'])
                    },
                    'gap_percentages': {
                        'open_gap_pct': (abs(last_pred['open'] - first_actual['open']) / first_actual['open']) * 100,
                        'high_gap_pct': (abs(last_pred['high'] - first_actual['high']) / first_actual['high']) * 100,
                        'low_gap_pct': (abs(last_pred['low'] - first_actual['low']) / first_actual['low']) * 100,
                        'close_gap_pct': (abs(last_pred['close'] - first_actual['close']) / first_actual['close']) * 100
                    }
                }
        
        # Save to file
        with filepath.open('x', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        print(f"Prediction results saved to: {filepath}")
        return filepath
        
    except Exception:
        app.logger.exception("Failed to save prediction results")
        return None

def create_prediction_chart(df, pred_df, lookback, pred_len, actual_df=None, historical_start_idx=0):
    """Create prediction chart"""
    # Use specified historical data start position, not always from the beginning of df
    if historical_start_idx + lookback + pred_len <= len(df):
        # Display lookback historical points + pred_len prediction points starting from specified position
        historical_df = df.iloc[historical_start_idx:historical_start_idx+lookback]
        prediction_range = range(historical_start_idx+lookback, historical_start_idx+lookback+pred_len)
    else:
        # If data is insufficient, adjust to maximum available range
        available_lookback = min(lookback, len(df) - historical_start_idx)
        available_pred_len = min(pred_len, max(0, len(df) - historical_start_idx - available_lookback))
        historical_df = df.iloc[historical_start_idx:historical_start_idx+available_lookback]
        prediction_range = range(historical_start_idx+available_lookback, historical_start_idx+available_lookback+available_pred_len)
    
    # Create chart
    fig = go.Figure()
    
    # Add historical data (candlestick chart)
    fig.add_trace(go.Candlestick(
        x=historical_df['timestamps'] if 'timestamps' in historical_df.columns else historical_df.index,
        open=historical_df['open'],
        high=historical_df['high'],
        low=historical_df['low'],
        close=historical_df['close'],
        name='Historical Data (400 data points)',
        increasing_line_color='#26A69A',
        decreasing_line_color='#EF5350'
    ))
    
    # Add prediction data (candlestick chart)
    if pred_df is not None and len(pred_df) > 0:
        # Calculate prediction data timestamps - ensure continuity with historical data
        if isinstance(pred_df.index, pd.DatetimeIndex):
            pred_timestamps = pred_df.index
        elif 'timestamps' in df.columns and len(historical_df) > 0:
            last_timestamp = historical_df['timestamps'].iloc[-1]
            time_diff = df['timestamps'].iloc[1] - df['timestamps'].iloc[0] if len(df) > 1 else pd.Timedelta(hours=1)
            pred_timestamps = pd.date_range(
                start=last_timestamp + time_diff, periods=len(pred_df), freq=time_diff
            )
        else:
            # If no timestamps, use index
            pred_timestamps = range(len(historical_df), len(historical_df) + len(pred_df))
        
        fig.add_trace(go.Candlestick(
            x=pred_timestamps,
            open=pred_df['open'],
            high=pred_df['high'],
            low=pred_df['low'],
            close=pred_df['close'],
            name='Prediction Data (120 data points)',
            increasing_line_color='#66BB6A',
            decreasing_line_color='#FF7043'
        ))
    
    # Add actual data for comparison (if exists)
    if actual_df is not None and len(actual_df) > 0:
        # Actual data should be in the same time period as prediction data
        if 'timestamps' in actual_df.columns:
            actual_timestamps = actual_df['timestamps']
        elif 'timestamps' in df.columns and 'pred_timestamps' in locals():
            actual_timestamps = pred_timestamps
        else:
            actual_timestamps = range(len(historical_df), len(historical_df) + len(actual_df))
        
        fig.add_trace(go.Candlestick(
            x=actual_timestamps,
            open=actual_df['open'],
            high=actual_df['high'],
            low=actual_df['low'],
            close=actual_df['close'],
            name='Actual Data (120 data points)',
            increasing_line_color='#FF9800',
            decreasing_line_color='#F44336'
        ))
    
    # Update layout
    fig.update_layout(
        title='Kronos Financial Prediction Results - 400 Historical Points + 120 Prediction Points vs 120 Actual Points',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_white',
        height=600,
        showlegend=True
    )
    
    # Ensure x-axis time continuity
    if 'timestamps' in historical_df.columns:
        # Get all timestamps and sort them
        all_timestamps = []
        if len(historical_df) > 0:
            all_timestamps.extend(historical_df['timestamps'])
        if 'pred_timestamps' in locals():
            all_timestamps.extend(pred_timestamps)
        if 'actual_timestamps' in locals():
            all_timestamps.extend(actual_timestamps)
        
        if all_timestamps:
            all_timestamps = sorted(all_timestamps)
            fig.update_xaxes(
                range=[all_timestamps[0], all_timestamps[-1]],
                rangeslider_visible=False,
                type='date'
            )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/data-files')
def get_data_files():
    """Get available data file list"""
    data_files = load_data_files()
    return jsonify(data_files)

@app.route('/api/load-data', methods=['POST'])
def load_data():
    """Load data file"""
    try:
        data = _request_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        # Detect data time frequency
        def detect_timeframe(df):
            if len(df) < 2:
                return "Unknown"
            
            time_diffs = []
            for i in range(1, min(10, len(df))):  # Check first 10 time differences
                diff = df['timestamps'].iloc[i] - df['timestamps'].iloc[i-1]
                time_diffs.append(diff)
            
            if not time_diffs:
                return "Unknown"
            
            # Calculate average time difference
            avg_diff = sum(time_diffs, pd.Timedelta(0)) / len(time_diffs)
            
            # Convert to readable format
            if avg_diff < pd.Timedelta(minutes=1):
                return f"{avg_diff.total_seconds():.0f} seconds"
            elif avg_diff < pd.Timedelta(hours=1):
                return f"{avg_diff.total_seconds() / 60:.0f} minutes"
            elif avg_diff < pd.Timedelta(days=1):
                return f"{avg_diff.total_seconds() / 3600:.0f} hours"
            else:
                return f"{avg_diff.days} days"
        
        # Return data information
        data_info = {
            'rows': len(df),
            'columns': list(df.columns),
            'start_date': df['timestamps'].min().isoformat() if 'timestamps' in df.columns else 'N/A',
            'end_date': df['timestamps'].max().isoformat() if 'timestamps' in df.columns else 'N/A',
            'price_range': {
                'min': float(df[['open', 'high', 'low', 'close']].min().min()),
                'max': float(df[['open', 'high', 'low', 'close']].max().max())
            },
            'prediction_columns': ['open', 'high', 'low', 'close'] + (['volume'] if 'volume' in df.columns else []),
            'timeframe': detect_timeframe(df)
        }
        
        return jsonify({
            'success': True,
            'data_info': data_info,
            'message': f'Successfully loaded data, total {len(df)} rows'
        })
        
    except (RequestValidationError, RequestEntityTooLarge):
        raise
    except Exception:
        app.logger.exception("Failed to process load-data request")
        return jsonify({'error': 'Failed to load selected data'}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    """Perform prediction"""
    try:
        data = _request_json()
        file_path = data.get('file_path')
        lookback = bounded_int(data, 'lookback', 400, 1, 2048)
        pred_len = bounded_int(data, 'pred_len', 120, 1, 512)
        
        # Get prediction quality parameters
        temperature = bounded_float(data, 'temperature', 1.0, 0.1, 2.0)
        top_p = bounded_float(data, 'top_p', 0.9, 0.1, 1.0)
        sample_count = bounded_int(data, 'sample_count', 1, 1, 5)
        start_date = validate_optional_start_date(data.get('start_date'))
        if start_date:
            try:
                pd.to_datetime(start_date, utc=True)
            except (TypeError, ValueError) as exc:
                raise RequestValidationError("Invalid start_date") from exc
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        # Load data
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        historical_df, actual_df, historical_start_idx = select_prediction_window(
            df, lookback, pred_len, start_date
        )
        
        # Perform prediction
        if MODEL_AVAILABLE and predictor is not None:
            try:
                # Use real Kronos model
                # Only use necessary columns: OHLCV, excluding amount
                required_cols = ['open', 'high', 'low', 'close']
                if 'volume' in df.columns:
                    required_cols.append('volume')
                
                x_df = historical_df[required_cols]
                x_timestamp = historical_df['timestamps'].reset_index(drop=True)
                y_timestamp = actual_df['timestamps'].reset_index(drop=True)
                prediction_type = (
                    "Kronos model prediction (selected evaluable window)"
                    if start_date
                    else "Kronos model prediction (latest evaluable window)"
                )
                
                # Ensure timestamps are Series format, not DatetimeIndex, to avoid .dt attribute error in Kronos model
                if isinstance(x_timestamp, pd.DatetimeIndex):
                    x_timestamp = pd.Series(x_timestamp, name='timestamps')
                if isinstance(y_timestamp, pd.DatetimeIndex):
                    y_timestamp = pd.Series(y_timestamp, name='timestamps')
                
                pred_df = predictor.predict(
                    df=x_df,
                    x_timestamp=x_timestamp,
                    y_timestamp=y_timestamp,
                    pred_len=pred_len,
                    T=temperature,
                    top_p=top_p,
                    sample_count=sample_count
                )
                
            except Exception:
                app.logger.exception("Kronos model prediction failed")
                return jsonify({'error': 'Kronos model prediction failed'}), 500
        else:
            return jsonify({'error': 'Kronos model not loaded, please load model first'}), 400
        
        # Prepare actual data for comparison (if exists)
        actual_data = [
            {
                'timestamp': row['timestamps'].isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']) if 'volume' in row else 0,
                'amount': float(row['amount']) if 'amount' in row else 0,
            }
            for _, row in actual_df.iterrows()
        ]
        
        chart_json = create_prediction_chart(df, pred_df, lookback, pred_len, actual_df, historical_start_idx)
        
        future_timestamps = pd.DatetimeIndex(y_timestamp)
        
        prediction_results = []
        for i, (_, row) in enumerate(pred_df.iterrows()):
            prediction_results.append({
                'timestamp': future_timestamps[i].isoformat() if i < len(future_timestamps) else f"T{i}",
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']) if 'volume' in row else 0,
                'amount': float(row['amount']) if 'amount' in row else 0
            })
        
        # Save prediction results to file
        try:
            save_prediction_results(
                file_path=file_path,
                prediction_type=prediction_type,
                prediction_results=prediction_results,
                actual_data=actual_data,
                input_data=x_df,
                prediction_params={
                    'lookback': lookback,
                    'pred_len': pred_len,
                    'temperature': temperature,
                    'top_p': top_p,
                    'sample_count': sample_count,
                    'start_date': start_date if start_date else 'latest'
                }
            )
        except Exception:
            app.logger.exception("Failed to save prediction results")
        
        return jsonify({
            'success': True,
            'prediction_type': prediction_type,
            'chart': chart_json,
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'has_comparison': len(actual_data) > 0,
            'message': f'Prediction completed, generated {pred_len} prediction points' + (f', including {len(actual_data)} actual data points for comparison' if len(actual_data) > 0 else '')
        })
        
    except (RequestValidationError, RequestEntityTooLarge):
        raise
    except Exception:
        app.logger.exception("Prediction request failed")
        return jsonify({'error': 'Prediction failed'}), 500

@app.route('/api/load-model', methods=['POST'])
def load_model():
    """Load Kronos model"""
    global tokenizer, model, predictor
    
    try:
        if not MODEL_AVAILABLE:
            return jsonify({'error': 'Kronos model library not available'}), 400
        
        data = _request_json()
        model_key = data.get('model_key', 'kronos-small')
        device = validate_device(data.get('device', 'cpu'))
        
        if model_key not in AVAILABLE_MODELS:
            return jsonify({'error': f'Unsupported model: {model_key}'}), 400
        
        model_config = AVAILABLE_MODELS[model_key]
        
        # Load tokenizer and model
        tokenizer = KronosTokenizer.from_pretrained(
            model_config['tokenizer_id'],
            revision=model_config['tokenizer_revision'],
        )
        model = Kronos.from_pretrained(
            model_config['model_id'],
            revision=model_config['model_revision'],
        )
        
        # Create predictor
        predictor = KronosPredictor(
            model,
            tokenizer,
            device=device,
            max_context=model_config['context_length'],
            model_version=model_config['model_id'],
            model_revision=model_config['model_revision'],
            tokenizer_revision=model_config['tokenizer_revision'],
        )
        
        return jsonify({
            'success': True,
            'message': f'Model loaded successfully: {model_config["name"]} ({model_config["params"]}) on {device}',
            'model_info': {
                'name': model_config['name'],
                'params': model_config['params'],
                'context_length': model_config['context_length'],
                'description': model_config['description'],
                'model_revision': model_config['model_revision'],
                'tokenizer_revision': model_config['tokenizer_revision'],
            }
        })
        
    except (RequestValidationError, RequestEntityTooLarge):
        raise
    except Exception:
        app.logger.exception("Model loading failed")
        return jsonify({'error': 'Model loading failed'}), 500

@app.route('/api/available-models')
def get_available_models():
    """Get available model list"""
    return jsonify({
        'models': AVAILABLE_MODELS,
        'model_available': MODEL_AVAILABLE
    })

@app.route('/api/model-status')
def get_model_status():
    """Get model status"""
    if MODEL_AVAILABLE:
        if predictor is not None:
            return jsonify({
                'available': True,
                'loaded': True,
                'message': 'Kronos model loaded and available',
                'current_model': {
                    'name': predictor.model.__class__.__name__,
                    'device': str(next(predictor.model.parameters()).device)
                }
            })
        else:
            return jsonify({
                'available': True,
                'loaded': False,
                'message': 'Kronos model available but not loaded'
            })
    else:
        return jsonify({
            'available': False,
            'loaded': False,
            'message': 'Kronos model library not available, please install related dependencies'
        })

if __name__ == '__main__':
    print("Starting Kronos Web UI...")
    print(f"Model availability: {MODEL_AVAILABLE}")
    if MODEL_AVAILABLE:
        print("Tip: You can load Kronos model through /api/load-model endpoint")
    else:
        print("Tip: Install the project model dependencies before loading a checkpoint")
    
    app.run(debug=False, use_reloader=False, host='127.0.0.1', port=7070, threaded=False)
