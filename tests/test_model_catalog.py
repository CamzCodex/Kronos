"""Released checkpoint identities must remain explicit and immutable."""

import re

import pytest

from model import DEFAULT_MODEL_KEY, RELEASED_MODELS, get_released_model


def test_released_catalog_pins_every_model_and_tokenizer_revision() -> None:
    assert DEFAULT_MODEL_KEY == "kronos-small"
    assert set(RELEASED_MODELS) == {"kronos-mini", "kronos-small", "kronos-base"}
    for key, definition in RELEASED_MODELS.items():
        assert definition.key == key
        assert re.fullmatch(r"[0-9a-f]{40}", definition.model_revision)
        assert re.fullmatch(r"[0-9a-f]{40}", definition.tokenizer_revision)
        assert definition.context_length > 0


def test_unknown_released_model_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown released model"):
        get_released_model("latest-mutable-checkpoint")
