# Safe data archives

The original fine-tuning pipeline stored prepared datasets and prediction outputs with Python `pickle`. Pickle is convenient, but **loading an untrusted pickle can execute arbitrary Python code**. A file downloaded from a forum, shared drive, issue attachment, or unknown model bundle must not be treated as data-only input.

`finetune/data_io.py` provides a versioned replacement format:

- ZIP container with deterministic member metadata;
- UTF-8 JSON using pandas' table schema for each DataFrame;
- one SHA-256 checksum and byte count per frame;
- a versioned `manifest.json`;
- rejection of duplicate, encrypted, symbolic-link, path-traversal, oversized, and unreferenced members;
- atomic writes through a temporary file and `os.replace`.

The filename suffix is:

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

For canonical prepared-dataset names, use the path helpers:

```python
from finetune.archive_paths import (
    load_named_frame_mapping,
    save_named_frame_mapping,
)

save_named_frame_mapping(symbol_to_dataframe, "./data/processed_datasets", "train_data")
restored = load_named_frame_mapping("./data/processed_datasets", "train_data")
```

This creates or loads `train_data.kronos.zip`.

## Prepared Qlib datasets

`finetune/qlib_data_preprocess.py` now writes:

```text
train_data.kronos.zip
val_data.kronos.zip
test_data.kronos.zip
```

`finetune/dataset.py` loads the training and validation archives through the safe resolver. When both safe and legacy files are present, the safe archive wins.

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

### Temporary compatibility mode

`finetune/config.py` contains:

```python
self.allow_unsafe_pickle = False
```

The default is deliberately `False`. Setting it to `True` permits the training dataset loader to open a legacy local `.pkl` when no safe archive exists. Use that mode only for a verified file and migrate it promptly; do not use it for downloaded or shared pickles.

When compatibility remains disabled and a legacy file is found, the loader raises an error containing the exact migration command rather than silently deserializing it.

## Current rollout status

Implemented:

- safe reader and writer;
- explicit migration command;
- integrity and archive-structure checks;
- packaged APIs and cross-version tests;
- safe Qlib preprocessing output;
- safe training and validation dataset loading;
- default refusal of legacy pickle.

Still pending:

- replacing direct pickle usage in `finetune/qlib_test.py` for test data and saved prediction signals.

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
