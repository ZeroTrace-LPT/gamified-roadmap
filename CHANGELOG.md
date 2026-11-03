# Changelog

All notable changes to this project are recorded here.

## [0.2.0] - 2026-11-03

### Added
- Searchable roadmap list containing normalized missions, skills, certifications, projects, and learning objectives.
- Filters for item type, category, phase, local progress status, workbook status, and target year.
- Timeline tree grouped by month, year, phase, or source sheet order.
- Roadmap detail panel showing the original workbook status and notes alongside local progress.
- Local progress editing for status, percentage, dates, and notes, with reset-to-source support.
- Additive SQLite schema v2 migration for user-owned progress records.
- Dashboard mission completion and current mission now reflect local progress.

### Changed
- Workbook status and source values remain unchanged when local progress is edited.
- Roadmap page now includes all normalized workbook records instead of only monthly missions.

### Fixed
- Windows packaging now isolates PyInstaller's DLL search path so unrelated host tools cannot add conflicting Qt dependencies.

### Known limitations
- XP awards, level recalculation, quests, skill tree, analytics, dedicated trackers, and Excel export remain scheduled for later releases.
- The workbook's non-standard status values are preserved and shown separately from the app's local progress statuses.
- Local progress is keyed to an imported workbook snapshot. A changed workbook creates a new snapshot; progress transfer between snapshots is deferred.

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
