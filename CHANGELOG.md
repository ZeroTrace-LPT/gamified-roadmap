# Changelog

All notable changes to this project are recorded here.

## [0.1.0] - 2026-10-08

### Added
- Modular PySide6 application shell with Dashboard, Roadmap, and Import data navigation.
- Versioned SQLite schema for source workbook records, normalized roadmap items, validation findings, and local settings.
- Excel importer for `.xlsx` and `.xlsm` files that stores populated cell values, formulas, formula caches, coordinates, validation ranges, and chart series references.
- Normalized source-backed records for the core monthly roadmap and supporting skill, certification, project, and learning tracks.
- Import validation for missing key fields, duplicate source keys, malformed `YYYY-MM` values, circular formulas, and known summary range inconsistencies.
- Idempotent behavior when importing the same workbook content again.
- Initial contributor documentation, development roadmap, requirements, and Windows PyInstaller script.
- Built and smoke-launched the Windows PyInstaller onedir application; packaging excludes optional libraries unused by this release.

### Known limitations
- Roadmap and source pages are read-only in this release; progress editing begins in v0.2.0.
- XP is displayed from the workbook's saved summary. The gamification engine is planned for v0.3.0.
- Excel export, backup/restore, skill tree, quests, achievements, analytics, and the dedicated certification/project/lab views are planned for later versions.
- The packaged executable was smoke-launched in the development environment; a fresh-machine installation validation is deferred to the release-candidate stage.
- The Excel importer preserves source formulas and cached values but does not execute formulas.
