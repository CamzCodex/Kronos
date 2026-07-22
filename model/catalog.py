"""Immutable identities for the released Kronos checkpoints used by this fork."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleasedModel:
    """One model/tokenizer pair pinned to exact Hugging Face revisions."""

    key: str
    name: str
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    context_length: int
    parameter_count: str
    description: str


RELEASED_MODELS = {
    "kronos-mini": ReleasedModel(
        key="kronos-mini",
        name="Kronos-mini",
        model_id="NeoQuasar/Kronos-mini",
        model_revision="f4e68697d9d5aed55cef5c96aabc3376bcad9f81",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-2k",
        tokenizer_revision="26966d0035065a0cae0ebad7af8ece35bc1fb51c",  # gitleaks:allow -- public Hugging Face commit SHA
        context_length=2048,
        parameter_count="4.1M",
        description="Lightweight checkpoint for the fastest local inference.",
    ),
    "kronos-small": ReleasedModel(
        key="kronos-small",
        name="Kronos-small",
        model_id="NeoQuasar/Kronos-small",
        model_revision="901c26c1332695a2a8f243eb2f37243a37bea320",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="0e0117387f39004a9016484a186a908917e22426",
        context_length=512,
        parameter_count="24.7M",
        description="Validated default checkpoint balancing latency and capacity.",
    ),
    "kronos-base": ReleasedModel(
        key="kronos-base",
        name="Kronos-base",
        model_id="NeoQuasar/Kronos-base",
        model_revision="2b554741eca47781b64468546e77fef3e85130e6",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="0e0117387f39004a9016484a186a908917e22426",
        context_length=512,
        parameter_count="102.3M",
        description="Higher-capacity checkpoint with greater local compute demand.",
    ),
}

DEFAULT_MODEL_KEY = "kronos-small"


def get_released_model(key: str) -> ReleasedModel:
    """Return a pinned model definition or reject an unknown key."""

    try:
        return RELEASED_MODELS[key]
    except KeyError as exc:
        choices = ", ".join(sorted(RELEASED_MODELS))
        raise ValueError(f"unknown released model {key!r}; choose one of: {choices}") from exc


__all__ = [
    "DEFAULT_MODEL_KEY",
    "RELEASED_MODELS",
    "ReleasedModel",
    "get_released_model",
]
