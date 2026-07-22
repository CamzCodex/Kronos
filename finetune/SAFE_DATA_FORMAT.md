# Safe data archives

The original fine-tuning pipeline stores prepared datasets and prediction outputs with Python `pickle`. Pickle is convenient, but **loading an untrusted pickle can execute arbitrary Python code**. A file downloaded from a forum, shared drive, issue attachment, or unknown model bundle must not be treated as data-only input.

`finetune/data_io.py` introduces a versioned replacement format:

- ZIP container with deterministic member metadata;
- UTF-8 JSON using pandas' table schema for each DataFrame;
- one SHA-256 checksum and byte count per frame;
- a versioned `manifest.json`;
- rejection of duplicate, encrypted, symbolic-link, path-traversal, oversized, and unreferenced members;
- atomic writes through a temporary file and `os.replace`.

The recommended filename suffix is:

```text
.kronos.zip
```

## Python API

```python
from finetune.data_io import load_frame_mapping, save_frame_mapping

save_frame_mapping(symbol_to_dataframe, "train_data.kronos.zip")
restored = load_frame_mapping("train_data.kronos.zip")
```

Both functions operate on a mapping whose keys are strings and whose values are pandas DataFrames.

## Migrating a trusted legacy pickle

Migration necessarily loads the old pickle once. Only perform it for a file whose origin and integrity you already trust.

```bash
python -m finetune.data_io \
  path/to/train_data.pkl \
  path/to/train_data.kronos.zip \
  --allow-unsafe-pickle
```

Without `--allow-unsafe-pickle`, migration refuses to deserialize the source.

The flag is an acknowledgement, not a sandbox. It does not make a malicious pickle safe.

## Current rollout status

The safe reader/writer, migration command, integrity checks, and offline tests are implemented first. Wiring the Qlib preprocessing, training, and backtest entry points to prefer `.kronos.zip` archives is the next step. Existing scripts should not be described as safe until that wiring lands; they still contain direct pickle calls.

## Format stability

The archive manifest currently uses:

```json
{
  "format": "kronos-frame-map",
  "version": 1,
  "frame_count": 1,
  "entries": [
    {
      "key": "AAPL",
      "path": "frames/00000000.json",
      "sha256": "...",
      "size": 1234
    }
  ]
}
```

Readers reject unknown versions rather than guessing. A future incompatible representation must increment `version` and include an explicit migration path.
