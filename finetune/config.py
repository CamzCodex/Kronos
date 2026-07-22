from datetime import date


class Config:
    """
    Configuration class for the entire project.
    """

    def __init__(self):
        # =================================================================
        # Data & Feature Parameters
        # =================================================================
        # TODO: Update this path to your Qlib data directory.
        self.qlib_data_path = "~/.qlib/qlib_data/cn_data"
        self.instrument = 'csi300'

        # Overall time range for data loading from Qlib.
        self.dataset_begin_time = "2011-01-01"
        self.dataset_end_time = '2025-06-05'

        # Sliding window parameters for creating samples.
        self.lookback_window = 90  # Number of past time steps for input.
        self.predict_window = 10  # Number of future time steps for prediction.
        self.max_context = 512  # Maximum context length for the model.

        # Features to be used from the raw data.
        self.feature_list = ['open', 'high', 'low', 'close', 'vol', 'amt']
        # Time-based features to be generated.
        self.time_feature_list = ['minute', 'hour', 'weekday', 'day', 'month']

        # =================================================================
        # Dataset Splitting & Paths
        # =================================================================
        # These target ranges never overlap. Context rows must be handled as
        # explicitly labelled context-only buffers by a future approved source
        # adapter; target membership is never expanded backwards for lookback.
        self.train_time_range = ["2011-01-01", "2022-12-31"]
        self.val_time_range = ["2023-01-01", "2024-06-30"]
        self.test_time_range = ["2024-07-01", "2025-06-05"]
        self.backtest_time_range = ["2024-07-01", "2025-06-05"]

        # TODO: Directory for prepared .kronos.zip datasets.
        self.dataset_path = "./data/processed_datasets"

        # Legacy .pkl compatibility is disabled because pickle loading can execute
        # arbitrary code. Enable this only for verified, trusted local files while
        # migrating them with `python -m finetune.data_io ... --allow-unsafe-pickle`.
        self.allow_unsafe_pickle = False

        # =================================================================
        # Training Hyperparameters
        # =================================================================
        self.clip = 5.0  # Clipping value for normalized data to prevent outliers.

        self.epochs = 30
        self.log_interval = 100  # Log training status every N batches.
        self.batch_size = 50  # Batch size per GPU.

        # Number of samples to draw for one "epoch" of training/validation.
        # This is useful for large datasets where a true epoch is too long.
        self.n_train_iter = 2000 * self.batch_size
        self.n_val_iter = 400 * self.batch_size

        # Learning rates for different model components.
        self.tokenizer_learning_rate = 2e-4
        self.predictor_learning_rate = 4e-5

        # Gradient accumulation to simulate a larger batch size.
        self.accumulation_steps = 1

        # AdamW optimizer parameters.
        self.adam_beta1 = 0.9
        self.adam_beta2 = 0.95
        self.adam_weight_decay = 0.1

        # Miscellaneous
        self.seed = 100  # Global random seed for reproducibility.

        # =================================================================
        # Experiment Logging & Saving
        # =================================================================
        self.use_comet = True # Set to False if you don't want to use Comet ML
        self.comet_config = {
            # It is highly recommended to load secrets from environment variables
            # for security purposes. Example: os.getenv("COMET_API_KEY")
            "api_key": "YOUR_COMET_API_KEY",
            "project_name": "Kronos-Finetune-Demo",
            "workspace": "your_comet_workspace" # TODO: Change to your Comet ML workspace name
        }
        self.comet_tag = 'finetune_demo'
        self.comet_name = 'finetune_demo'

        # Base directory for saving model checkpoints and results.
        # Using a general 'outputs' directory is a common practice.
        self.save_path = "./outputs/models"
        self.tokenizer_save_folder_name = 'finetune_tokenizer_demo'
        self.predictor_save_folder_name = 'finetune_predictor_demo'
        self.backtest_save_folder_name = 'finetune_backtest_demo'

        # Path for backtesting results.
        self.backtest_result_path = "./outputs/backtest_results"

        # =================================================================
        # Model & Checkpoint Paths
        # =================================================================
        # TODO: Update these paths to your pretrained model locations.
        # These can be local paths or Hugging Face Hub model identifiers.
        self.pretrained_tokenizer_path = "path/to/your/Kronos-Tokenizer-base"
        self.pretrained_predictor_path = "path/to/your/Kronos-small"

        # Paths to the fine-tuned models, derived from the save_path.
        # These will be generated automatically during training.
        self.finetuned_tokenizer_path = f"{self.save_path}/{self.tokenizer_save_folder_name}/checkpoints/best_model"
        self.finetuned_predictor_path = f"{self.save_path}/{self.predictor_save_folder_name}/checkpoints/best_model"

        # =================================================================
        # Backtesting Parameters
        # =================================================================
        self.backtest_n_symbol_hold = 50  # Number of symbols to hold in the portfolio.
        self.backtest_n_symbol_drop = 5  # Number of symbols to drop from the pool.
        self.backtest_hold_thresh = 5  # Minimum holding period for a stock.
        self.inference_T = 0.6
        self.inference_top_p = 0.9
        self.inference_top_k = 0
        self.inference_sample_count = 5
        self.backtest_batch_size = 1000
        self.backtest_benchmark = self._set_benchmark(self.instrument)
        self._validate_ranges()

    @staticmethod
    def _range_dates(value, name):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{name} must contain exactly two ISO dates")
        try:
            start, end = (date.fromisoformat(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must contain valid ISO dates") from exc
        if start > end:
            raise ValueError(f"{name} start must not follow its end")
        return start, end

    def _validate_ranges(self):
        """Fail closed when demo target ranges overlap or escape the dataset."""

        dataset_start = date.fromisoformat(self.dataset_begin_time)
        dataset_end = date.fromisoformat(self.dataset_end_time)
        train_start, train_end = self._range_dates(
            self.train_time_range, "train_time_range"
        )
        val_start, val_end = self._range_dates(self.val_time_range, "val_time_range")
        test_start, test_end = self._range_dates(
            self.test_time_range, "test_time_range"
        )
        backtest_start, backtest_end = self._range_dates(
            self.backtest_time_range, "backtest_time_range"
        )
        if not (dataset_start <= train_start and test_end <= dataset_end):
            raise ValueError("target ranges must be contained by the dataset range")
        if not (train_end < val_start and val_end < test_start):
            raise ValueError("train, validation, and test target ranges must not overlap")
        if not (test_start <= backtest_start <= backtest_end <= test_end):
            raise ValueError("backtest_time_range must be contained by test_time_range")

    def _set_benchmark(self, instrument):
        dt_benchmark = {
            'csi800': "SH000906",
            'csi1000': "SH000852",
            'csi300': "SH000300",
        }
        if instrument in dt_benchmark:
            return dt_benchmark[instrument]
        else:
            raise ValueError(f"Benchmark not defined for instrument: {instrument}")
