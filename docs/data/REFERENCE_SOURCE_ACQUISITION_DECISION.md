# Reference source acquisition decision

Decision date: 2026-07-22

Decision: **Norgate US Stocks Platinum is the preferred conditional technical candidate; the
standard subscription is rejected and must not be purchased for this mission.**

This is a repository evidence-control decision, not legal advice. A provider- or counsel-approved
signed agreement must supply the missing rights before acquisition.

## Why Norgate leads technically

The US Platinum package currently advertises daily history back to 1990, delisted securities,
formerly listed OTC securities, and historical index constituents for USD 346.50 for six months or
USD 630 for twelve months. Its content documentation also identifies:

- historical S&P, Nasdaq, Russell, and exchange-wide constituent histories;
- a daily major-exchange-versus-OTC listing indicator back to January 1995;
- delisted-security last-quoted dates;
- dividends and capital events, including splits and complex reorganizations;
- exchange and currency metadata; and
- irregular exchange closure information.

Those capabilities are materially closer to the source gate than Qlib/Yahoo, Alpha Vantage, or the
reviewed Nasdaq Data Link product. The first acquisition would therefore be the six-month US
Platinum package, not Diamond, **but only after the contract gate below passes**. Six months is
enough to acquire, verify, and register a fixed historical snapshot; a longer subscription adds cost
before the benchmark demonstrates value.

## Why the standard agreement fails

Norgate's standard EULA dated 2026-06-19:

- defines the licensee as one natural person and permits installation for personal use;
- permits data use for a personal purpose and prohibits other commercial purposes;
- makes the database inaccessible after a subscription lapses;
- requires deletion of Data and Derived Data when the relevant subscription lapses;
- permits corrections without notice and supplier changes without notice; and
- says the agreement can be modified only in writing signed by a Norgate Director and the licensee.

The deletion obligation alone conflicts with immutable experiment reconstruction. The personal-use
and publication restrictions are also unresolved for repository-backed research. Buying first and
asking later could leave the project unable to retain its raw snapshot, derived reports, model
artifacts, or audit trail.

Nasdaq Data Link's standard data terms have the same decisive retention problem: on termination the
client must cease use and delete or purge supplied data. It is not a fallback under its standard
terms.

## Contract acceptance checklist

Before payment, retain a signed amendment or separate licence that explicitly permits:

1. this Kronos research project and its actual user/entity class, including any commercial status;
2. automated Python extraction on an approved Windows acquisition host and transfer to the secured
   Linux research environment;
3. immutable raw snapshots, backups, SHA-256 identities, manifests, audit artifacts, derived
   metrics, figures, reports, and model artifacts;
4. indefinite retention and internal reproducibility after subscription expiry or termination;
5. publication of non-reconstructive aggregate metrics, methodology, charts, and model conclusions
   in this repository, while prohibiting redistribution of raw vendor data;
6. the number of authorized people, machines, CI/offline environments, and backup locations;
7. access to unadjusted daily bars, authoritative sessions/closures, delisted securities, stable
   identifiers, exchange/currency metadata, dividends, capital events, and historical constituents;
8. an answer on whether historical constituent and corporate-action records include first-known or
   announcement/availability timestamps, not only effective dates;
9. a documented correction/revision channel and the right to preserve superseded snapshots; and
10. retention of the signed terms and product documentation as private acquisition evidence.

The public source-gate record must include the signed entitlement artifact's SHA-256, not its
confidential bytes. Gate version 1.1 refuses paid access that is authorized only by an unbound human
declaration.

An email assurance is insufficient if it does not satisfy the standard EULA's signed-modification
clause. Any custom price must be approved before payment; USD 346.50 is only the current public
six-month list price and excludes taxes, currency conversion, and custom licensing.

## Acquisition protocol after contract approval

1. Acquire US Stocks Platinum on a controlled Windows host; do not expose credentials to CI.
2. Export no-padding, unadjusted daily bars plus all required metadata/event/universe/session files.
3. Freeze original bytes read-only and hash them before parsing or normalization.
4. Record acquisition time, software/product version, entitlement, machine/environment identity,
   file inventory, and correction state.
5. Run `kronos_data.source_gate`; a signed licence does not override missing technical evidence.
6. Reject or narrow the universe if announcement/availability timestamps cannot be established.
7. Build the source adapter and canonical manifest only from the passed source assessment.
8. Keep vendor bytes private; register only permitted derived evidence and content identities.

## No fallback smoke benchmark

A Qlib/Yahoo smoke run would exercise adapters but could not unlock the benchmark, fine-tuning, or
paper portfolio. The repository already has synthetic engineering coverage. Spending compute on a
known non-decision-grade result is therefore not recommended while the acquisition contract is the
actual blocker.

## Primary sources

- [Norgate standard EULA](https://norgatedata.com/subscribe/eula.php)
- [Norgate stock packages and pricing](https://norgatedata.com/stockmarketpackages.php)
- [Norgate content tables](https://norgatedata.com/data-content-tables.php)
- [Norgate accessibility and Windows/Python integration](https://norgatedata.com/accessibility.php)
- [Nasdaq Data Link data terms](https://data.nasdaq.com/terms)
