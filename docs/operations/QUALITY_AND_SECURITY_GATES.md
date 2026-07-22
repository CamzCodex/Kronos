# Quality and security gates

The required `Quality and security gates` workflow fails closed on four independent control
families:

1. Ruff linting across the hardened data, evaluation, typed forecast, and safe-archive surfaces.
2. Mypy checking across `kronos_data`, `kronos_eval`, and `model/forecast.py`.
3. `pip-audit` checks of the core and Web UI dependency declarations.
4. Full-history Gitleaks scanning plus explicit archive, leakage, and evaluation smoke tests.

The toolchain used directly by CI is pinned in `requirements-quality.txt`. The Gitleaks action is
pinned to an exact upstream commit rather than a mutable tag.

## Scope boundary

The upstream examples, legacy `finetune_csv` scripts, Web UI application source, and older model
internals are not yet part of the zero-warning Ruff or mypy surface. They remain research-only and
must not be represented as fully statically verified. New hardened modules must join the maintained
gate before their PR can merge.

GitHub branch protection must require the four jobs if repository settings permit. A workflow file
cannot itself prove that administrators have configured branch protection or GitHub-native secret
scanning.
