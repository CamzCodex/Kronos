# Kronos Web UI

Web user interface for Kronos financial prediction model, providing intuitive graphical operation interface.

## ✨ Features

- **Validated CSV input**: Loads bounded local CSV files through a strict market-data contract
- **Smart time window**: Fixed 400+120 data point time window slider selection
- **Real model prediction**: Integrated real Kronos model, supports multiple model sizes
- **Prediction quality control**: Adjustable temperature, nucleus sampling, sample count and other parameters
- **Multi-device support**: Supports CPU, CUDA, MPS and other computing devices
- **Comparison analysis**: Detailed comparison between prediction results and actual data
- **K-line chart display**: Professional financial K-line chart display

## 🚀 Quick Start

Install the declared dependencies from the repository root:

```bash
python -m pip install -e ".[webui]"
```

### Method 1: Start as a module
```bash
kronos-web --data-dir ./data
```

### Method 2: Start with Shell script
```bash
cd webui
chmod +x start.sh
./start.sh
```

### Method 3: Start Flask application directly
```bash
cd webui
python app.py
```

After successful startup, visit http://localhost:7070

All selectable checkpoints are bound to exact model and tokenizer revisions. Use
`kronos-runtime benchmark` before selecting a larger checkpoint for daily local use.

## 🔒 Security Boundary

- The bundled server binds to `127.0.0.1` only, with debug mode and the reloader disabled.
- API writes reject cross-origin requests and JSON bodies larger than 64 KiB.
- Data selection is restricted to regular `.csv` files inside the repository's
  `data/` directory; absolute paths, traversal, and escaping symlinks are refused.
- Forecast parameters, devices, input file size, and loaded row counts are bounded.
- Input data must include exactly one UTC-normalizable timestamp column, strict chronological
  ordering, finite positive prices, valid OHLC relationships, and non-negative activity fields.
  Invalid rows are refused rather than repaired or silently dropped.
- Runtime launchers never install packages or modify the environment.
- Internal exceptions are logged locally and replaced with stable client errors.
- Third-party browser scripts use exact version URLs and Subresource Integrity hashes.

This UI has no authentication, TLS termination, user isolation, or production WSGI server. Do not
bind it to a non-loopback interface, publish it through a tunnel, or expose it through a reverse
proxy. A separately reviewed access-control and deployment design is required for remote use.

The UI is a research demonstration. Its charts and saved predictions are not leakage-audited,
decision-grade benchmark evidence and must not be used to unlock fine-tuning, paper trading, or
live trading.

## 📋 Usage Steps

1. **Load data**: Place and select a supported financial data file from the repository `data/` directory
2. **Load model**: Select Kronos model and computing device
3. **Set parameters**: Adjust prediction quality parameters
4. **Select time window**: Use slider to select 400+120 data point time range
5. **Start prediction**: Click prediction button to generate results
6. **View results**: View prediction results in charts and tables

## 🔧 Prediction Quality Parameters

### Temperature (T)
- **Range**: 0.1 - 2.0
- **Effect**: Controls prediction randomness
- **Recommendation**: 1.2-1.5 for better prediction quality

### Nucleus Sampling (top_p)
- **Range**: 0.1 - 1.0
- **Effect**: Controls prediction diversity
- **Recommendation**: 0.95-1.0 to consider more possibilities

### Sample Count
- **Range**: 1 - 5
- **Effect**: Generate multiple prediction samples
- **Recommendation**: 2-3 samples to improve quality

## 📊 Supported Data Formats

### Required Columns
- Exactly one of `timestamps`, `timestamp`, or `date`: chronological observation time
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price

### Optional Columns
- `volume`: Trading volume
- `amount`: Trading amount (not used for prediction)

## 🤖 Model Support

- **Kronos-mini**: 4.1M parameters, lightweight fast prediction
- **Kronos-small**: 24.7M parameters, balanced performance and speed
- **Kronos-base**: 102.3M parameters, high quality prediction

## 🖥️ GPU Acceleration Support

- **CPU**: General computing, best compatibility
- **CUDA**: NVIDIA GPU acceleration, best performance
- **MPS**: Apple Silicon GPU acceleration, recommended for Mac users

## ⚠️ Notes

- `amount` column is not used for prediction, only for display
- Time window is fixed at 400+120=520 data points
- Ensure data file contains sufficient historical data
- First model loading may require download, please be patient

## 🔍 Comparison Analysis

The system automatically provides comparison analysis between prediction results and actual data, including:
- Price difference statistics
- Error analysis
- Prediction quality assessment

## 🛠️ Technical Architecture

- **Backend**: Flask + Python
- **Frontend**: HTML + CSS + JavaScript
- **Charts**: Plotly.js
- **Data processing**: Pandas + NumPy
- **Model**: Hugging Face Transformers

## 📝 Troubleshooting

### Common Issues
1. **Port occupied**: Modify port number in app.py
2. **Missing dependencies**: Run `python -m pip install -e ".[webui]"` from the repository root
3. **Model loading failed**: Check the model dependency, network access, and model ID
4. **Data format error**: Ensure data column names and format are correct

### Log Viewing
Detailed runtime information will be displayed in the console at startup, including model status and error messages.

## 📄 License

This project follows the license terms of the original Kronos project.

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve this Web UI!

## 📞 Support

If you have questions, please check:
1. Project documentation
2. GitHub Issues
3. Console error messages
