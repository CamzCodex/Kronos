"""Causal paper-return cost accounting for evaluation; never broker execution."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import Any, cast

import numpy as np
import pandas as pd

from kronos_data.hashing import canonical_json, hash_configuration

COST_MODEL_VERSION = "1.0.0"
REQUIRED_PAPER_RETURN_COLUMNS = (
    "decision_timestamp",
    "realization_timestamp",
    "dollar_volume_as_of_timestamp",
    "instrument_id",
    "target_weight",
    "realized_return",
    "dollar_volume",
)


class CostModelError(ValueError):
    """Raised when paper-return or cost inputs are invalid."""


@dataclass(frozen=True)
class CostAssumptions:
    """Explicit one-way costs in basis points plus a liquidity impact rule."""

    commission_bps: float
    half_spread_bps: float
    slippage_bps: float
    impact_coefficient_bps: float
    impact_exponent: float = 0.5
    maximum_participation_rate: float = 0.1
    periods_per_year: int = 252

    def __post_init__(self) -> None:
        for name in (
            "commission_bps",
            "half_spread_bps",
            "slippage_bps",
            "impact_coefficient_bps",
        ):
            _finite_non_negative(getattr(self, name), name)
        if not isinstance(self.impact_exponent, Real) or isinstance(
            self.impact_exponent, bool
        ):
            raise CostModelError("impact_exponent must be a real number")
        if not math.isfinite(float(self.impact_exponent)) or self.impact_exponent <= 0:
            raise CostModelError("impact_exponent must be finite and positive")
        if not isinstance(self.maximum_participation_rate, Real) or isinstance(
            self.maximum_participation_rate, bool
        ):
            raise CostModelError("maximum_participation_rate must be a real number")
        if not 0 < float(self.maximum_participation_rate) <= 1:
            raise CostModelError(
                "maximum_participation_rate must be greater than zero and at most one"
            )
        if (
            isinstance(self.periods_per_year, bool)
            or not isinstance(self.periods_per_year, Integral)
            or int(self.periods_per_year) <= 0
        ):
            raise CostModelError("periods_per_year must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "commission_bps": float(self.commission_bps),
            "half_spread_bps": float(self.half_spread_bps),
            "slippage_bps": float(self.slippage_bps),
            "impact_coefficient_bps": float(self.impact_coefficient_bps),
            "impact_exponent": float(self.impact_exponent),
            "maximum_participation_rate": float(self.maximum_participation_rate),
            "periods_per_year": int(self.periods_per_year),
        }


@dataclass(frozen=True)
class CostEvaluationRequest:
    """Precomputed paper targets and later outcomes for one fold."""

    strategy_name: str
    dataset_id: str
    fold_id: str
    code_commit: str
    decisions: pd.DataFrame = field(repr=False, compare=False)
    assumptions: CostAssumptions
    portfolio_notional: float

    def __post_init__(self) -> None:
        for name in ("strategy_name", "dataset_id", "fold_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CostModelError(f"{name} must be a non-empty string")
        if not isinstance(self.code_commit, str) or re.fullmatch(
            r"[0-9a-f]{7,64}", self.code_commit
        ) is None:
            raise CostModelError(
                "code_commit must be a lowercase hexadecimal Git SHA"
            )
        if not isinstance(self.assumptions, CostAssumptions):
            raise TypeError("assumptions must be CostAssumptions")
        if not isinstance(self.portfolio_notional, Real) or isinstance(
            self.portfolio_notional, bool
        ):
            raise CostModelError("portfolio_notional must be a real number")
        if not math.isfinite(float(self.portfolio_notional)) or self.portfolio_notional <= 0:
            raise CostModelError("portfolio_notional must be finite and positive")


@dataclass(frozen=True)
class CostEvaluationResult:
    cost_model_version: str
    strategy_name: str
    dataset_id: str
    fold_id: str
    code_commit: str
    input_hash: str
    assumptions_hash: str
    trade_ledger: pd.DataFrame
    period_ledger: pd.DataFrame
    sector_exposure: pd.DataFrame
    metrics: dict[str, Any]
    warnings: tuple[str, ...]


def evaluate_paper_returns(request: CostEvaluationRequest) -> CostEvaluationResult:
    """Apply costs to causally timed paper targets and realized returns."""

    decisions = _validated_decisions(request)
    previous = {instrument: 0.0 for instrument in decisions["instrument_id"].unique()}
    trade_rows = []
    sector_rows = []
    period_rows = []
    assumptions = request.assumptions

    for realization_timestamp, group in decisions.groupby(
        "realization_timestamp", sort=True, observed=True
    ):
        group = group.sort_values("instrument_id", kind="mergesort")
        decision_timestamp = group["decision_timestamp"].iloc[0]
        gross_return = 0.0
        commission_cost = 0.0
        spread_cost = 0.0
        slippage_cost = 0.0
        impact_cost = 0.0
        turnover = 0.0
        for row in group.itertuples(index=False):
            prior_weight = previous[row.instrument_id]
            delta_weight = float(row.target_weight) - prior_weight
            absolute_trade = abs(delta_weight)
            trade_notional = absolute_trade * float(request.portfolio_notional)
            participation = trade_notional / float(row.dollar_volume)
            if participation > assumptions.maximum_participation_rate + 1e-15:
                raise CostModelError(
                    f"trade participation {participation:.6g} exceeds declared maximum "
                    f"for {row.instrument_id} at {realization_timestamp.isoformat()}"
                )
            impact_bps = float(assumptions.impact_coefficient_bps) * participation ** float(
                assumptions.impact_exponent
            )
            row_commission = absolute_trade * float(assumptions.commission_bps) / 10_000
            row_spread = absolute_trade * float(assumptions.half_spread_bps) / 10_000
            row_slippage = absolute_trade * float(assumptions.slippage_bps) / 10_000
            row_impact = absolute_trade * impact_bps / 10_000
            trade_rows.append(
                {
                    "decision_timestamp": decision_timestamp,
                    "realization_timestamp": realization_timestamp,
                    "dollar_volume_as_of_timestamp": row.dollar_volume_as_of_timestamp,
                    "instrument_id": row.instrument_id,
                    "previous_weight": prior_weight,
                    "target_weight": float(row.target_weight),
                    "delta_weight": delta_weight,
                    "absolute_trade_weight": absolute_trade,
                    "trade_notional": trade_notional,
                    "dollar_volume": float(row.dollar_volume),
                    "participation_rate": participation,
                    "commission_cost_return": row_commission,
                    "spread_cost_return": row_spread,
                    "slippage_cost_return": row_slippage,
                    "impact_bps": impact_bps,
                    "impact_cost_return": row_impact,
                    "total_cost_return": (
                        row_commission + row_spread + row_slippage + row_impact
                    ),
                }
            )
            previous[row.instrument_id] = float(row.target_weight)
            gross_return += float(row.target_weight) * float(row.realized_return)
            turnover += absolute_trade
            commission_cost += row_commission
            spread_cost += row_spread
            slippage_cost += row_slippage
            impact_cost += row_impact

        if "sector" in group.columns:
            for sector, sector_group in group.groupby("sector", sort=True, observed=True):
                sector_rows.append(
                    {
                        "realization_timestamp": realization_timestamp,
                        "sector": sector,
                        "net_exposure": float(sector_group["target_weight"].sum()),
                        "gross_exposure": float(sector_group["target_weight"].abs().sum()),
                    }
                )
        total_cost = commission_cost + spread_cost + slippage_cost + impact_cost
        period_rows.append(
            {
                "decision_timestamp": decision_timestamp,
                "realization_timestamp": realization_timestamp,
                "gross_return": gross_return,
                "commission_cost_return": commission_cost,
                "spread_cost_return": spread_cost,
                "slippage_cost_return": slippage_cost,
                "impact_cost_return": impact_cost,
                "total_cost_return": total_cost,
                "net_return": gross_return - total_cost,
                "turnover": turnover,
                "gross_exposure": float(group["target_weight"].abs().sum()),
                "net_exposure": float(group["target_weight"].sum()),
                "maximum_absolute_position": float(group["target_weight"].abs().max()),
                "concentration_hhi": float(np.sum(group["target_weight"].to_numpy() ** 2)),
                "minimum_dollar_volume": float(group["dollar_volume"].min()),
            }
        )

    trade_ledger = pd.DataFrame(trade_rows)
    period_ledger = pd.DataFrame(period_rows)
    sector_exposure = pd.DataFrame(
        sector_rows,
        columns=["realization_timestamp", "sector", "net_exposure", "gross_exposure"],
    )
    metrics, warnings = _economic_metrics(
        trade_ledger,
        period_ledger,
        sector_exposure,
        periods_per_year=assumptions.periods_per_year,
    )
    return CostEvaluationResult(
        cost_model_version=COST_MODEL_VERSION,
        strategy_name=request.strategy_name.strip(),
        dataset_id=request.dataset_id.strip(),
        fold_id=request.fold_id.strip(),
        code_commit=request.code_commit,
        input_hash=_decision_hash(decisions),
        assumptions_hash=hash_configuration(
            {
                "cost_model_version": COST_MODEL_VERSION,
                "portfolio_notional": float(request.portfolio_notional),
                **assumptions.to_dict(),
            }
        ),
        trade_ledger=trade_ledger,
        period_ledger=period_ledger,
        sector_exposure=sector_exposure,
        metrics=metrics,
        warnings=warnings,
    )


def evaluate_cost_scenarios(
    request: CostEvaluationRequest,
    scenarios: dict[str, CostAssumptions],
) -> dict[str, CostEvaluationResult]:
    """Evaluate predeclared cost perturbations against one unchanged paper path."""

    if not isinstance(scenarios, dict) or not scenarios:
        raise CostModelError("scenarios must be a non-empty mapping")
    results = {}
    for name in sorted(scenarios):
        if not isinstance(name, str) or not name.strip():
            raise CostModelError("scenario names must be non-empty strings")
        assumptions = scenarios[name]
        if not isinstance(assumptions, CostAssumptions):
            raise TypeError("every scenario must contain CostAssumptions")
        results[name] = evaluate_paper_returns(
            CostEvaluationRequest(
                strategy_name=request.strategy_name,
                dataset_id=request.dataset_id,
                fold_id=request.fold_id,
                code_commit=request.code_commit,
                decisions=request.decisions,
                assumptions=assumptions,
                portfolio_notional=request.portfolio_notional,
            )
        )
    return results


def _validated_decisions(request: CostEvaluationRequest) -> pd.DataFrame:
    if not isinstance(request, CostEvaluationRequest):
        raise TypeError("request must be a CostEvaluationRequest")
    if not isinstance(request.decisions, pd.DataFrame):
        raise CostModelError("decisions must be a pandas DataFrame")
    missing = [
        column
        for column in REQUIRED_PAPER_RETURN_COLUMNS
        if column not in request.decisions.columns
    ]
    if missing:
        raise CostModelError(f"decisions are missing required columns: {missing}")
    columns = list(REQUIRED_PAPER_RETURN_COLUMNS)
    if "sector" in request.decisions.columns:
        columns.append("sector")
    frame = request.decisions.loc[:, columns].copy(deep=True)
    if frame.empty:
        raise CostModelError("decisions must not be empty")
    for column in (
        "decision_timestamp",
        "realization_timestamp",
        "dollar_volume_as_of_timestamp",
    ):
        frame[column] = _aware_utc_index(frame[column], column)
    if (frame["realization_timestamp"] <= frame["decision_timestamp"]).any():
        raise CostModelError(
            "every realization_timestamp must be later than its decision_timestamp"
        )
    if (frame["dollar_volume_as_of_timestamp"] > frame["decision_timestamp"]).any():
        raise CostModelError(
            "dollar_volume_as_of_timestamp cannot be later than decision_timestamp"
        )
    frame["instrument_id"] = frame["instrument_id"].astype("string")
    if frame["instrument_id"].isna().any() or (
        frame["instrument_id"].astype(str).str.strip() == ""
    ).any():
        raise CostModelError("instrument_id must contain non-empty labels")
    if frame.duplicated(["realization_timestamp", "instrument_id"]).any():
        raise CostModelError("each realization/instrument decision must be unique")
    numeric = ("target_weight", "realized_return", "dollar_volume")
    for column in numeric:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise CostModelError(f"{column} must be numeric") from exc
    if not np.isfinite(frame.loc[:, numeric].to_numpy(dtype=float)).all():
        raise CostModelError("decision numeric values must be finite")
    if (frame["dollar_volume"] <= 0).any():
        raise CostModelError("dollar_volume must be positive")
    if (frame["realized_return"] <= -1.0).any():
        raise CostModelError("instrument realized_return must be greater than -1")
    if "sector" in frame.columns:
        if frame["sector"].isna().any() or (frame["sector"].astype(str).str.strip() == "").any():
            raise CostModelError("sector must contain non-empty labels when supplied")
        frame["sector"] = frame["sector"].astype("string")
    decision_counts = frame.groupby("realization_timestamp")["decision_timestamp"].nunique()
    if (decision_counts != 1).any():
        raise CostModelError("one realization period cannot mix decision timestamps")
    period_times = (
        frame.groupby("realization_timestamp", sort=True, observed=True)["decision_timestamp"]
        .first()
    )
    if len(period_times) > 1 and np.any(
        period_times.to_numpy()[1:] < period_times.index.to_numpy()[:-1]
    ):
        raise CostModelError(
            "paper return intervals must not overlap a prior realization period"
        )
    universe = None
    for _, group in frame.groupby("realization_timestamp", sort=True, observed=True):
        instruments = tuple(sorted(group["instrument_id"].astype(str)))
        if universe is None:
            universe = instruments
        elif instruments != universe:
            raise CostModelError(
                "every rebalance must contain the same complete instrument universe, "
                "including explicit zero targets"
            )
    return frame.sort_values(
        ["realization_timestamp", "instrument_id"], kind="mergesort"
    ).reset_index(drop=True)


def _economic_metrics(
    trades: pd.DataFrame,
    periods: pd.DataFrame,
    sectors: pd.DataFrame,
    *,
    periods_per_year: int,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    gross = periods["gross_return"].to_numpy()
    net = periods["net_return"].to_numpy()
    if (net <= -1.0).any():
        raise CostModelError("net paper return reaches or exceeds total portfolio loss")
    wealth: np.ndarray = np.cumprod(1.0 + net)
    peak = np.maximum.accumulate(np.concatenate([[1.0], wealth]))[1:]
    drawdown = wealth / peak - 1.0
    volatility = float(np.std(net, ddof=1) * math.sqrt(periods_per_year)) if len(net) > 1 else None
    standard_deviation = float(np.std(net, ddof=1)) if len(net) > 1 else None
    sharpe_like = (
        float(np.mean(net) / standard_deviation * math.sqrt(periods_per_year))
        if standard_deviation is not None and standard_deviation > 0
        else None
    )
    maximum_sector_gross = (
        float(sectors["gross_exposure"].max()) if not sectors.empty else None
    )
    metrics = {
        "period_count": len(periods),
        "gross_compounded_return": float(np.prod(1.0 + gross) - 1.0),
        "net_compounded_return": float(wealth[-1] - 1.0),
        "total_turnover": float(periods["turnover"].sum()),
        "average_turnover": float(periods["turnover"].mean()),
        "commission_cost_return": float(periods["commission_cost_return"].sum()),
        "spread_cost_return": float(periods["spread_cost_return"].sum()),
        "slippage_cost_return": float(periods["slippage_cost_return"].sum()),
        "impact_cost_return": float(periods["impact_cost_return"].sum()),
        "total_cost_return": float(periods["total_cost_return"].sum()),
        "maximum_drawdown": float(drawdown.min()),
        "annualized_volatility": volatility,
        "sharpe_like": sharpe_like,
        "maximum_gross_exposure": float(periods["gross_exposure"].max()),
        "maximum_absolute_net_exposure": float(periods["net_exposure"].abs().max()),
        "maximum_absolute_position": float(periods["maximum_absolute_position"].max()),
        "maximum_concentration_hhi": float(periods["concentration_hhi"].max()),
        "maximum_participation_rate": float(trades["participation_rate"].max()),
        "minimum_dollar_volume": float(periods["minimum_dollar_volume"].min()),
        "maximum_sector_gross_exposure": maximum_sector_gross,
    }
    warnings = (
        "paper-return cost accounting is a deterministic simulation, not evidence of fills",
        "Sharpe-like statistic is unadjusted for autocorrelation, non-normality, risk-free rate, and multiple testing",
        "fixed spread/slippage plus square-root participation impact are assumptions requiring sensitivity analysis",
        "dollar_volume must be a causally available capacity estimate as of its declared timestamp",
        "target weights are externally supplied; this module creates no order and applies no risk approval",
    )
    return metrics, warnings


def _decision_hash(frame: pd.DataFrame) -> str:
    records = []
    for row in frame.itertuples(index=False, name=None):
        converted = []
        for value in row:
            if isinstance(value, pd.Timestamp):
                converted.append(value.tz_convert("UTC").isoformat())
            elif isinstance(value, (np.floating, float)):
                converted.append(float(value))
            else:
                converted.append(str(value))
        records.append(converted)
    return hashlib.sha256(
        canonical_json({"columns": list(frame.columns), "records": records}).encode("utf-8")
    ).hexdigest()


def _finite_non_negative(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise CostModelError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise CostModelError(f"{name} must be finite and non-negative")


def _aware_utc_index(values: object, name: str) -> pd.DatetimeIndex:
    converted = []
    try:
        iterator = iter(cast(Iterable[object], values))
    except TypeError as exc:
        raise CostModelError(f"{name} must be an iterable of timestamps") from exc
    for value in iterator:
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError) as exc:
            raise CostModelError(f"{name} must contain valid timestamps") from exc
        if pd.isna(timestamp):
            raise CostModelError(f"{name} must not contain missing values")
        if timestamp.tzinfo is None:
            raise CostModelError(f"{name} must be timezone-aware")
        converted.append(timestamp.tz_convert("UTC"))
    return pd.DatetimeIndex(converted)


__all__ = [
    "COST_MODEL_VERSION",
    "REQUIRED_PAPER_RETURN_COLUMNS",
    "CostAssumptions",
    "CostEvaluationRequest",
    "CostEvaluationResult",
    "CostModelError",
    "evaluate_cost_scenarios",
    "evaluate_paper_returns",
]
