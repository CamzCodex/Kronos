# Adversarial review — reference data acquisition

Review date: 2026-07-22

Decision boundary: provider selection and contract gate only; no source, dataset, or market result
is approved

The source gate is upgraded to version 1.1 in this phase so a paid source cannot pass without the
SHA-256 of a retained entitlement artifact. The contract remains private; its public digest binds
the exact reviewed bytes.

## What was challenged

- Is the technically richest provider being mistaken for a licensed evidence source?
- Can the project reproduce a result after a subscription or vendor relationship ends?
- Can a current adjusted series insert future corporate actions into earlier folds?
- Are historical index memberships official, inferred, synthetic, or only effective-date records?
- Could delisted coverage still omit failures?
- Can silent vendor corrections change the benchmark after publication?
- Does the Linux repository have a reproducible acquisition path for a Windows-oriented product?
- Would a cheap smoke benchmark create pressure to promote invalid evidence?

## Findings

### Critical — standard Norgate terms destroy durable lineage

The public EULA requires deletion of Data and Derived Data after lapse and removes database access.
That is incompatible with the registry's reconstruction promise and with independent review of a
long-lived benchmark. Personal-use and commercial-use clauses add unresolved scope risk. The
standard subscription is therefore a no-go regardless of technical quality.

### Critical — availability timestamps are not established

Norgate documents effective constituent histories, dividend entitlements, and capital-event
ex-dates, but the reviewed public material does not establish first-known/announcement timestamps
for every historical membership and corporate-action record. Effective-date data can still be
future-known when reconstructing an earlier decision. A custom agreement and trial export must not
be marked passed unless this evidence is supplied or the protocol is conservatively narrowed.

### High — revision drift can change a result

The EULA permits corrections and supplier changes without notice. A freshly downloaded history can
therefore differ from the benchmark snapshot. Immutable raw bytes, acquisition timestamps, product
versions, correction logs, and superseded snapshots are mandatory; vendor access alone is not
reproducibility.

### High — constituent histories contain qualifications

The provider describes US histories as essentially complete and identifies several inferred index
supersets. Its ASX documentation says pre-March-2000 constituent changes are synthetic. The first
benchmark must use an explicitly supported US universe/period and must not generalize one
constituent-history quality claim to every index, country, or era.

### High — delisted does not mean complete outcomes

The US content page says its early delisted database is extensive but does not claim completeness.
The selected period should begin well after the weakest early era, and terminal-return/delisting
treatment must be tested against acquisition files rather than inferred from package marketing.

### High — Windows acquisition is a distinct trust boundary

The supported Python integration is Windows-oriented while repository evaluation and CI are Linux.
Credentials and vendor software must remain on a controlled acquisition host; original exports must
be hashed before transfer. CI must consume only approved private snapshots, never live credentials.
The contract must explicitly permit this architecture.

### Medium — adjusted data can leak later actions

Even when a provider offers adjustment controls, a current fully adjusted series may encode actions
unknown at an earlier forecast time. The adapter should acquire unadjusted/no-padding bars and
reconstruct adjustments from causally available events. Provider-adjusted output is a comparison
diagnostic, not the default evidence path.

### Medium — a smoke benchmark would not reduce the real blocker

Qlib/Yahoo could produce numbers quickly but would leave rights, version stability, adjustments,
membership availability, and delistings unresolved. The repository already tests mechanics on
synthetic fixtures. A smoke score would mostly create false momentum and selection pressure.

## Validation evidence

- 19 source-gate regressions pass when collected independently of the repository's PyTorch-wide
  test conftest, including the new paid-source entitlement hash refusal.
- Ruff, maintained-surface Mypy, Python compilation, and patch hygiene pass locally.
- The local environment has no PyTorch, so the full offline suite is not claimed; GitHub's Python
  3.10/3.12 workflow remains the merge authority.
- No provider credentials, contract bytes, market bytes, manifest, experiment, or metric exists.

## Decision

Norgate US Stocks Platinum is conditionally preferred on technical coverage and price, but no
purchase, source approval, adapter, or benchmark may begin under the standard EULA. The next valid
event is a signed licence/addendum satisfying the acquisition checklist, followed by a trial export
that passes every source-gate field. Failure to obtain either must return the decision to **no source
approved**, not lower the gate.

Unresolved critical findings block fine-tuning, the paper portfolio, and model promotion.
