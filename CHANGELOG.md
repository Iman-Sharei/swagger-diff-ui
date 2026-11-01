# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-11-01

### Added

- Sample Django project under `examples/sample_project/`
- GitHub Actions CI workflow (pytest on Python 3.10–3.12)
- This changelog

### Fixed

- Exclude library helper views from OpenAPI generation so `drf-spectacular` no longer warns about unguessable serializers during CLI / schema export
- Package `authors` metadata now lists Iman Sharei instead of a generic contributors label
- Sample project includes `django.contrib.auth` so `/api/docs/` loads without a 500
- Baseline worktree runs nested `manage.py` (e.g. `examples/sample_project/`) instead of only repo-root
- Ignore local `db.sqlite3` files created by the sample project

## [0.1.1] - 2026-11-01

### Added

- CI-oriented management command: `manage.py swagger_diff --ci` / `--fail-on-breaking`
- Relative git refs for baselines (`HEAD~1`, `main~3`, `HEAD^`, …)
- README coverage for schema URL name wiring (`SWAGGER_DIFF_SCHEMA_URL_NAME`)

### Fixed

- Nested schema `$ref` changes correctly mark parent operations as UPDATE

## [0.1.0] - 2026-09-17

### Added

- Initial Django + DRF drop-in Swagger UI with git baseline schema diff
- HTTP helpers for git refs, baseline schema, and diff reports
- PyPI package metadata and README

[Unreleased]: https://github.com/Iman-Sharei/swagger-diff-ui/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Iman-Sharei/swagger-diff-ui/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Iman-Sharei/swagger-diff-ui/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Iman-Sharei/swagger-diff-ui/releases/tag/v0.1.0
