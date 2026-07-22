# Dataset card — first daily reference benchmark

Status: **PLANNED / SOURCE NOT SELECTED**  
Dataset ID: Unknown

## Purpose and decision scope

This dataset will support the first released-checkpoint zero-shot comparison at daily frequency and 1, 3, and 5 trading-day horizons. It may be used only for research and paper simulation.

## Current knowns

- Frequency: daily adjusted bars.
- Universe requirement: one liquid equity universe with point-in-time membership evidence.
- Required qualities: accessible licence, adequate history, reproducibility, corporate-action quality, liquidity, and survivorship controls.
- Required storage: Parquet/Arrow for scalable bars plus `.kronos.zip` for bounded audited fixtures and portable artifacts.

## Unknowns that block dataset creation

- Provider and primary-source URL: Unknown.
- Licence and redistribution terms: Unknown.
- Universe and historical membership source: Unknown.
- Exchange calendar source: Unknown.
- Corporate-action methodology and effective-time semantics: Unknown.
- Coverage, instruments, rows, missing bars, and revisions: Unknown.
- Dataset ID, raw hashes, configuration hash, and code commit: Unknown until ingestion.
- Train, validation, calibration, test, and final-holdout boundaries: Unknown until the evaluation specification is approved.

## Approval rule

Do not populate results or claim this dataset exists until the source is selected, licensing is recorded, canonical validation passes, a deterministic manifest is written, and the leakage auditor approves its split and availability semantics.
