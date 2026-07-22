"""Fine-tuning support utilities for Kronos."""

from . import data_io as _data_io
from .archive_writer import save_frame_mapping

# Keep the historical ``finetune.data_io.save_frame_mapping`` path on the
# memory-bounded writer for package imports. The reader/migration functions in
# data_io resolve this module global at call time as well.
_data_io.save_frame_mapping = save_frame_mapping

from .archive_paths import (
    legacy_pickle_path,
    load_named_frame_mapping,
    safe_archive_path,
    save_named_frame_mapping,
)
from .backtest_io import load_test_data, save_prediction_signals
from .data_io import (
    DataArchiveError,
    UnsafeLegacyFormatError,
    load_frame_mapping,
    load_legacy_pickle,
    load_safe_frame_mapping,
    migrate_legacy_pickle,
)

__all__ = [
    "DataArchiveError",
    "UnsafeLegacyFormatError",
    "legacy_pickle_path",
    "load_frame_mapping",
    "load_legacy_pickle",
    "load_named_frame_mapping",
    "load_safe_frame_mapping",
    "load_test_data",
    "migrate_legacy_pickle",
    "safe_archive_path",
    "save_frame_mapping",
    "save_named_frame_mapping",
    "save_prediction_signals",
]
