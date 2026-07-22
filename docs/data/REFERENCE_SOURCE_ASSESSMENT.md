# Reference daily-equity source assessment

Assessment date: 2026-07-22  
Decision: **NO SOURCE APPROVED FOR DECISION-GRADE BENCHMARKING**  
Permitted use: source-adapter engineering and explicitly labelled smoke research only

Acquisition recommendation: **Norgate US Stocks Platinum is the preferred conditional technical
candidate, but its standard subscription must not be purchased for this mission. A signed custom
retention/research licence and successful trial evidence review are required first.** See
`docs/data/REFERENCE_SOURCE_ACQUISITION_DECISION.md`.

## Required gate

The first reference source must establish all of the following before raw bars can produce a
decision-grade dataset manifest:

- confirmed usage rights and any required access authorization;
- for paid access, SHA-256 identity of the retained confidential entitlement/contract artifact;
- retained raw snapshot bytes and SHA-256 identity;
- at least eight years of daily history for the declared universe;
- retained authoritative exchange sessions;
- corporate-action events with availability timestamps;
- point-in-time membership intervals with availability timestamps;
- delisted instruments and outcomes;
- stable instrument identifiers, exchange, and currency metadata;
- a documented provider revision policy; and
- at least two primary evidence references.

`kronos_data.source_gate` now enforces that contract and persists an immutable structured result.
It does not approve a provider from prose or a URL alone.

## Candidate review

| Candidate | Accessible/licensed | History | Adjustments | Survivorship/universe | Reproducibility | Decision |
|---|---|---|---|---|---|---|
| Norgate US Stocks Platinum | Public list price is USD 346.50/6 months or USD 630/12 months, but the standard EULA is personal-use oriented, prohibits other commercial use, and requires deletion of Data and Derived Data after lapse | Back to 1990 | Dividends, capital events, adjustment choices, and unadjusted export appear technically suitable; historical first-known timestamps remain unproved | Delisted securities, former major-exchange OTC listings, daily listing state, and historical index constituents are offered; completeness and availability timing retain qualifications | Standard terms remove access after lapse, require deletion, permit corrections/supplier changes without notice, and the supported Python path is Windows-oriented | **Preferred conditional candidate; standard purchase rejected** pending a signed retention/research amendment and trial export that passes the source gate |
| Microsoft Qlib public China daily data derived from Yahoo Finance | Usage/redistribution rights for the underlying market data are not established in this repository; current Qlib README availability is not a pinned local snapshot | Historical depth appears adequate for old v1/v2 data | Qlib explicitly warns that data may be imperfect, identifies abnormal series, and says some adjusted series remain abnormal | Qlib supports dynamic CSI300 instruments, but source publication/availability timestamps and complete delisting evidence have not been established | Qlib documents differences between v1 and v2 caused by unstable Yahoo history; no raw archive was acquired and hashed here | **Not approved**; possible low-confidence engineering smoke source after terms and bytes are pinned |
| Alpha Vantage Daily Adjusted | Requires an API key and is labelled premium | Advertises 20+ years | Provides adjusted close plus split/dividend events, but no acquired snapshot has been checked for point-in-time availability semantics | Per-symbol endpoint does not itself supply the required point-in-time liquid-equity universe or delisting history | No exact response bytes or hash acquired | **Not approved**; inferior technical fit for the reference universe |
| Nasdaq Data Link QuoteMedia EOD | Official documentation classifies the EOD product as premium; standard Nasdaq terms require deletion/purge on termination | Not evaluated without entitlement | Not evaluated without entitlement | Not evaluated without entitlement | No exact snapshot acquired; standard termination terms conflict with durable lineage | **Not approved** under standard terms |

## Primary evidence

- Microsoft Qlib’s [Yahoo collector documentation](https://github.com/microsoft/qlib/blob/main/scripts/data_collector/yahoo/README.md) says the data may be imperfect, calls out abnormal series, states that some adjusted series remain abnormal, and records v1/v2 differences due to unstable Yahoo history.
- The Qlib [repository data section](https://github.com/microsoft/qlib#data-preparation) describes the public dataset as Yahoo-derived, recommends higher-quality user data, and exposes dynamic acquisition rather than a repository-committed immutable snapshot.
- Qlib’s [data API documentation](https://github.com/microsoft/qlib/blob/main/docs/start/getdata.rst) demonstrates dynamic market instruments, including CSI300, but does not establish membership publication timestamps or licensing for the underlying data.
- Yahoo’s [developer API terms](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html) describe a revocable API licence; this assessment found no repository evidence that those terms grant the required rights for the Qlib-derived benchmark snapshot.
- Alpha Vantage’s [official API documentation](https://www.alphavantage.co/documentation/) labels `TIME_SERIES_DAILY_ADJUSTED` premium and describes its API-key requirement and split/dividend fields.
- Nasdaq Data Link’s [official data-product documentation](https://docs.data.nasdaq.com/docs/data-organization) classifies QuoteMedia End of Day US Prices as premium.
- Norgate's [stock-package page](https://norgatedata.com/stockmarketpackages.php) lists current prices, history depth, delisted securities, and historical constituents.
- Norgate's [content tables](https://norgatedata.com/data-content-tables.php) document daily listing state, constituent-history qualifications, dividends, capital events, delisted coverage, exchange/currency metadata, and irregular closures.
- Norgate's [standard EULA](https://norgatedata.com/subscribe/eula.php) limits standard usage, permits silent corrections, removes access after lapse, and requires deletion of Data and Derived Data after lapse.
- Norgate's [accessibility page](https://norgatedata.com/accessibility.php) describes survivorship-bias controls, ASCII price/volume export, and the Windows Python integration.
- Nasdaq Data Link's [data terms](https://data.nasdaq.com/terms) require data use to cease and supplied data to be deleted or purged on termination.

## Why no synthetic structured result is committed

The structured gate requires a real source locator, actual retained snapshot SHA-256, coverage,
terms evidence, calendar, adjustment events, universe history, and delisting evidence. Supplying
placeholder values would create a plausible-looking but false provenance artifact. Therefore no
`SourceGateResult`, dataset manifest, data card approval, experiment entry, or benchmark metric is
created in this phase.

## Exact unblock

Obtain a provider- or counsel-approved signed Norgate amendment satisfying
`REFERENCE_SOURCE_ACQUISITION_DECISION.md`, then acquire the six-month US Platinum product and run a
trial export through the source gate. If the agreement or availability-timestamp evidence fails,
return to supplier selection; do not purchase standard access and do not substitute a smoke result.

Until the signed terms and real gate result exist, the released-checkpoint benchmark, fine-tuning,
and paper-portfolio gates remain closed.
