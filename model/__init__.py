"""Public package exports for Kronos."""

__version__ = "0.1.0.dev0"

from .kronos import Kronos, KronosPredictor, KronosTokenizer

__all__ = [
    "Kronos",
    "KronosPredictor",
    "KronosTokenizer",
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
