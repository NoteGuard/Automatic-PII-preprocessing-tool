# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com);
the project uses [semantic versioning](https://semver.org).

## [1.0.0] — 2026-06-20

Gold-RAP restructure ("analysis as a product").

### Added
- Standard RAP directory layout: `src/` (package), `tests/` (unit tests + `run_eval.py`),
  `docs/`, `data/` (inputs), `output/` (generated artifacts).
- `pyproject.toml` — the project is now pip-installable (`pip install -e .`).
- Continuous integration (`.github/workflows/ci.yml`) running `ruff` + `pytest` on every push/PR.
- `ruff` lint configuration and `logging` in the evaluation entry point.
- This changelog.

### Changed
- Renamed the package `noteguard/` → `src/`; all imports updated to `src.*`.
- Generated outputs (metrics, two-Trust artifacts) now write to `output/` instead of `data/out/`.
- `run_eval.py` moved under `tests/` as the evaluation entry point.

### Removed
- Decluttered `experiments/` (failure log moved to `docs/failed_experiments.md`).
- Removed the committed `results.json` artifact (now regenerated into `output/`, gitignored).
