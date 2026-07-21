"""Offline unit tests for validated sampling utilities."""

import math

import pytest
import torch

import model.kronos as legacy_kronos
from model.sampling import sample_from_logits, top_k_top_p_filtering


class TestSamplingCompatibility:
    def test_legacy_module_uses_hardened_functions(self):
        assert legacy_kronos.sample_from_logits is sample_from_logits
        assert legacy_kronos.top_k_top_p_filtering is top_k_top_p_filtering


class TestTopKTopPFiltering:
    def test_top_k_1_keeps_only_max(self):
        logits = torch.tensor([[1.0, 3.0, 2.0, 0.5]])

        filtered = top_k_top_p_filtering(logits, top_k=1)

        assert filtered[0, 1] == 3.0
        assert torch.isneginf(filtered[0, [0, 2, 3]]).all()

    def test_top_p_0_keeps_only_max(self):
        logits = torch.tensor([[1.0, 5.0, 2.0, 0.5]])

        filtered = top_k_top_p_filtering(logits, top_p=0.0)

        finite_mask = torch.isfinite(filtered)
        assert finite_mask.sum() == 1
        assert filtered[0, 1].item() == 5.0

    def test_top_k_and_top_p_are_applied_sequentially(self):
        logits = torch.tensor([[4.0, 3.0, 2.0, 1.0]])

        filtered = top_k_top_p_filtering(logits, top_k=3, top_p=0.70)

        assert torch.isfinite(filtered).sum().item() == 2
        assert torch.isfinite(filtered[0, :2]).all()
        assert torch.isneginf(filtered[0, 2:]).all()

    def test_does_not_mutate_input(self):
        logits = torch.tensor([[1.0, 3.0, 2.0, 0.5]])
        original = logits.clone()

        filtered = top_k_top_p_filtering(logits, top_k=2)

        assert torch.equal(logits, original)
        assert filtered.data_ptr() != logits.data_ptr()

    def test_all_same_logits_keeps_at_least_top_k(self):
        logits = torch.tensor([[2.0, 2.0, 2.0, 2.0]])

        filtered = top_k_top_p_filtering(logits, top_k=2)

        assert torch.isfinite(filtered).sum() >= 2

    def test_single_token(self):
        logits = torch.tensor([[5.0]])

        filtered = top_k_top_p_filtering(logits, top_k=1)

        assert filtered[0, 0] == 5.0

    def test_top_k_preserves_batch_shape(self):
        logits = torch.randn(4, 10)

        filtered = top_k_top_p_filtering(logits, top_k=3)

        assert filtered.shape == logits.shape
        for row in filtered:
            assert torch.isfinite(row).sum() == 3

    def test_no_filtering_returns_equal_clone(self):
        logits = torch.tensor([[1.0, 2.0, 3.0]])

        filtered = top_k_top_p_filtering(logits, top_k=0, top_p=1.0)

        torch.testing.assert_close(filtered, logits)
        assert filtered.data_ptr() != logits.data_ptr()

    def test_supports_more_than_two_dimensions(self):
        logits = torch.randn(2, 3, 10)

        filtered = top_k_top_p_filtering(logits, top_k=2)

        assert filtered.shape == logits.shape
        assert torch.equal(torch.isfinite(filtered).sum(dim=-1), torch.full((2, 3), 2))

    @pytest.mark.parametrize("top_k", [-1, -100])
    def test_negative_top_k_is_rejected(self, top_k):
        with pytest.raises(ValueError, match="top_k"):
            top_k_top_p_filtering(torch.randn(1, 4), top_k=top_k)

    @pytest.mark.parametrize("top_k", [1.5, True, "2"])
    def test_non_integer_top_k_is_rejected(self, top_k):
        with pytest.raises(TypeError, match="top_k"):
            top_k_top_p_filtering(torch.randn(1, 4), top_k=top_k)

    @pytest.mark.parametrize("top_p", [-0.1, 1.1, math.inf, math.nan])
    def test_invalid_top_p_is_rejected(self, top_p):
        with pytest.raises(ValueError, match="top_p"):
            top_k_top_p_filtering(torch.randn(1, 4), top_p=top_p)

    @pytest.mark.parametrize("top_p", [True, "0.9"])
    def test_non_numeric_top_p_is_rejected(self, top_p):
        with pytest.raises(TypeError, match="top_p"):
            top_k_top_p_filtering(torch.randn(1, 4), top_p=top_p)

    @pytest.mark.parametrize("minimum", [0, -1])
    def test_invalid_minimum_token_count_is_rejected(self, minimum):
        with pytest.raises(ValueError, match="min_tokens_to_keep"):
            top_k_top_p_filtering(
                torch.randn(1, 4), min_tokens_to_keep=minimum
            )

    def test_integer_logits_are_rejected(self):
        with pytest.raises(TypeError, match="floating-point"):
            top_k_top_p_filtering(torch.tensor([[1, 2, 3]]), top_k=1)

    def test_nan_logits_are_rejected(self):
        with pytest.raises(ValueError, match="NaN"):
            top_k_top_p_filtering(torch.tensor([[1.0, float("nan")]]))

    def test_rows_with_no_finite_value_are_rejected(self):
        with pytest.raises(ValueError, match="at least one finite"):
            top_k_top_p_filtering(
                torch.tensor([[float("-inf"), float("-inf")]])
            )


class TestSampleFromLogits:
    def test_very_low_temperature_is_effectively_deterministic(self):
        torch.manual_seed(42)
        logits = torch.tensor([[0.1, 0.2, 10.0, 0.3]])

        results = {
            sample_from_logits(
                logits, temperature=0.001, sample_logits=True
            ).item()
            for _ in range(10)
        }

        assert results == {2}

    def test_greedy_sampling_picks_argmax(self):
        logits = torch.tensor([[0.1, 0.2, 10.0, 0.3]])

        index = sample_from_logits(
            logits, temperature=1.0, sample_logits=False
        )

        assert index.item() == 2

    @pytest.mark.parametrize(
        ("top_k", "top_p"),
        [(None, 0.9), (1, None), (None, None)],
    )
    def test_optional_filter_arguments_are_supported(self, top_k, top_p):
        logits = torch.tensor([[1.0, 2.0, 3.0]])

        index = sample_from_logits(
            logits,
            temperature=1.0,
            top_k=top_k,
            top_p=top_p,
            sample_logits=False,
        )

        assert index.shape == (1, 1)
        assert index.item() == 2

    def test_output_is_valid_index(self):
        torch.manual_seed(42)
        vocab_size = 50
        logits = torch.randn(1, vocab_size)

        index = sample_from_logits(
            logits, temperature=1.0, sample_logits=True
        )

        assert 0 <= index.item() < vocab_size

    def test_output_shape_preserves_batch(self):
        logits = torch.randn(4, 20)

        index = sample_from_logits(
            logits, temperature=1.0, sample_logits=True
        )

        assert index.shape == (4, 1)

    def test_with_top_k(self):
        torch.manual_seed(42)
        logits = torch.randn(1, 100)

        index = sample_from_logits(
            logits, temperature=1.0, top_k=5, sample_logits=True
        )

        assert 0 <= index.item() < 100

    def test_with_top_p(self):
        torch.manual_seed(42)
        logits = torch.randn(1, 100)

        index = sample_from_logits(
            logits,
            temperature=1.0,
            top_k=0,
            top_p=0.9,
            sample_logits=True,
        )

        assert 0 <= index.item() < 100

    @pytest.mark.parametrize("temperature", [0.0, -1.0, math.inf, math.nan])
    def test_invalid_temperature_is_rejected(self, temperature):
        with pytest.raises(ValueError, match="temperature"):
            sample_from_logits(torch.randn(1, 4), temperature=temperature)

    @pytest.mark.parametrize("temperature", [True, "1.0"])
    def test_non_numeric_temperature_is_rejected(self, temperature):
        with pytest.raises(TypeError, match="temperature"):
            sample_from_logits(torch.randn(1, 4), temperature=temperature)

    def test_non_boolean_sampling_mode_is_rejected(self):
        with pytest.raises(TypeError, match="sample_logits"):
            sample_from_logits(torch.randn(1, 4), sample_logits=1)

    def test_filter_validation_is_applied_during_sampling(self):
        with pytest.raises(ValueError, match="top_k"):
            sample_from_logits(torch.randn(1, 4), top_k=-1)
        with pytest.raises(ValueError, match="top_p"):
            sample_from_logits(torch.randn(1, 4), top_p=1.5)
