"""Validated, side-effect-free token sampling utilities.

The original implementation lives in :mod:`model.kronos` because released
checkpoints and downstream code import that module directly.  The package
initialiser installs these functions into that module at import time so both
legacy imports and internal autoregressive generation use this implementation.
"""

from __future__ import annotations

import math
from numbers import Integral, Real

import torch
import torch.nn.functional as F


def _validate_top_k(top_k: int) -> int:
    if isinstance(top_k, bool) or not isinstance(top_k, Integral):
        raise TypeError("top_k must be an integer")
    top_k = int(top_k)
    if top_k < 0:
        raise ValueError("top_k must be greater than or equal to 0")
    return top_k


def _validate_top_p(top_p: float) -> float:
    if isinstance(top_p, bool) or not isinstance(top_p, Real):
        raise TypeError("top_p must be a real number")
    top_p = float(top_p)
    if not math.isfinite(top_p) or not 0.0 <= top_p <= 1.0:
        raise ValueError("top_p must be finite and between 0 and 1 inclusive")
    return top_p


def _validate_min_tokens(min_tokens_to_keep: int) -> int:
    if isinstance(min_tokens_to_keep, bool) or not isinstance(
        min_tokens_to_keep, Integral
    ):
        raise TypeError("min_tokens_to_keep must be an integer")
    min_tokens_to_keep = int(min_tokens_to_keep)
    if min_tokens_to_keep < 1:
        raise ValueError("min_tokens_to_keep must be at least 1")
    return min_tokens_to_keep


def _validate_logits(logits: torch.Tensor) -> None:
    if not isinstance(logits, torch.Tensor):
        raise TypeError("logits must be a torch.Tensor")
    if not torch.is_floating_point(logits):
        raise TypeError("logits must use a floating-point dtype")
    if logits.ndim < 1 or logits.shape[-1] == 0:
        raise ValueError("logits must have a non-empty vocabulary dimension")
    if torch.isnan(logits).any():
        raise ValueError("logits must not contain NaN values")
    if torch.isposinf(logits).any():
        raise ValueError("logits must not contain positive infinity")
    if not torch.isfinite(logits).any(dim=-1).all():
        raise ValueError("each logits row must contain at least one finite value")


def top_k_top_p_filtering(
    logits: torch.Tensor,
    top_k: int = 0,
    top_p: float = 1.0,
    filter_value: float = -float("inf"),
    min_tokens_to_keep: int = 1,
) -> torch.Tensor:
    """Filter logits using top-k and/or nucleus sampling.

    Filtering is applied to a clone.  The caller's tensor is never mutated.
    Top-k is applied first, followed by top-p over the remaining distribution.

    Args:
        logits: Floating-point tensor whose final dimension is the vocabulary.
        top_k: Keep the ``top_k`` highest-scoring tokens. ``0`` disables it.
        top_p: Keep the smallest high-probability set whose cumulative mass
            reaches ``top_p``. ``1`` disables it.
        filter_value: Value assigned to filtered logits.
        min_tokens_to_keep: Minimum number of tokens retained by nucleus
            filtering.

    Returns:
        A filtered clone with the same shape, dtype, and device as ``logits``.
    """

    _validate_logits(logits)
    top_k = _validate_top_k(top_k)
    top_p = _validate_top_p(top_p)
    min_tokens_to_keep = _validate_min_tokens(min_tokens_to_keep)

    filtered = logits.clone()
    vocabulary_size = filtered.shape[-1]

    if top_k > 0:
        keep_count = min(max(top_k, min_tokens_to_keep), vocabulary_size)
        threshold = torch.topk(filtered, keep_count, dim=-1).values[..., -1, None]
        filtered.masked_fill_(filtered < threshold, filter_value)

    if top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(filtered, descending=True, dim=-1)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        sorted_indices_to_remove = cumulative_probs > top_p
        if min_tokens_to_keep > 1:
            sorted_indices_to_remove[..., :min_tokens_to_keep] = False

        # Retain the first token that crosses the threshold as well as the
        # highest-scoring token. This matches standard nucleus filtering.
        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[
            ..., :-1
        ].clone()
        sorted_indices_to_remove[..., 0] = False

        indices_to_remove = torch.zeros_like(
            sorted_indices_to_remove, dtype=torch.bool
        ).scatter(-1, sorted_indices, sorted_indices_to_remove)
        filtered.masked_fill_(indices_to_remove, filter_value)

    return filtered


def sample_from_logits(
    logits: torch.Tensor,
    temperature: float = 1.0,
    top_k: int | None = None,
    top_p: float | None = None,
    sample_logits: bool = True,
) -> torch.Tensor:
    """Select one token per logits row with validated sampling controls."""

    _validate_logits(logits)
    if isinstance(temperature, bool) or not isinstance(temperature, Real):
        raise TypeError("temperature must be a real number")
    temperature = float(temperature)
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and greater than 0")
    if not isinstance(sample_logits, bool):
        raise TypeError("sample_logits must be a boolean")

    normalized_top_k = 0 if top_k is None else _validate_top_k(top_k)
    normalized_top_p = 1.0 if top_p is None else _validate_top_p(top_p)

    scaled_logits = logits / temperature
    if normalized_top_k > 0 or normalized_top_p < 1.0:
        scaled_logits = top_k_top_p_filtering(
            scaled_logits,
            top_k=normalized_top_k,
            top_p=normalized_top_p,
        )

    probabilities = F.softmax(scaled_logits, dim=-1)
    if not torch.isfinite(probabilities).all():
        raise ValueError("sampling probabilities are not finite")

    if sample_logits:
        return torch.multinomial(probabilities, num_samples=1)
    return torch.argmax(probabilities, dim=-1, keepdim=True)
