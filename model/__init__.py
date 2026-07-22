"""Public package exports for Kronos."""

__version__ = "0.1.0.dev0"

from . import kronos as _kronos
from .catalog import DEFAULT_MODEL_KEY, RELEASED_MODELS, ReleasedModel, get_released_model
from .forecast import (
    CandleIssue,
    CandleRepair,
    ForecastRequest,
    ForecastRequestError,
    ForecastResult,
    ForecastValidityReport,
    SamplePathValidity,
)
from .sampling import sample_from_logits, top_k_top_p_filtering

# Keep legacy ``model.kronos`` imports and the autoregressive generator's
# runtime global lookups on the hardened implementation without changing the
# released checkpoint module layout.
_kronos.sample_from_logits = sample_from_logits
_kronos.top_k_top_p_filtering = top_k_top_p_filtering

Kronos = _kronos.Kronos
KronosPredictor = _kronos.KronosPredictor
KronosTokenizer = _kronos.KronosTokenizer

__all__ = [
    "Kronos",
    "KronosPredictor",
    "KronosTokenizer",
    "CandleIssue",
    "CandleRepair",
    "ForecastRequest",
    "ForecastRequestError",
    "ForecastResult",
    "ForecastValidityReport",
    "SamplePathValidity",
    "DEFAULT_MODEL_KEY",
    "RELEASED_MODELS",
    "ReleasedModel",
    "get_released_model",
    "sample_from_logits",
    "top_k_top_p_filtering",
    "__version__",
    "get_model_class",
]

model_dict = {
    "kronos_tokenizer": KronosTokenizer,
    "kronos": Kronos,
    "kronos_predictor": KronosPredictor,
}


def get_model_class(model_name):
    """Return a public model class by its registry name."""
    if model_name in model_dict:
        return model_dict[model_name]
    raise NotImplementedError(f"Model {model_name} not found in model_dict")
